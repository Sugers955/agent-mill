"""Skill execution helpers extracted from agent_runner.py.

This module contains pure functions for:
- Executing atomic/composite skills
- Loading skill bundles (path-based skills)
- Running skill scripts in subprocess sandboxes
- Saving output files and registering downloads
- Extracting fallback files from model output

All functions take explicit parameters (no self).
"""
from __future__ import annotations

import asyncio
import json
import re as _re
from typing import Any

from ..db.models import Skill
from .dag_executor import DAGExecutor

# Allowed callable modules for skills (dotted paths)
ALLOWED_SKILL_CALLABLES: set[str] = {
    # Add safe callable modules here, e.g.:
    # "app.services.my_safe_service",
}


async def run_atomic_skill(skill: Skill, input_data: dict[str, Any]) -> dict[str, Any]:
    """Invoke an atomic skill out-of-band (used by composite DAG only)."""
    src = skill.source_json or {}
    if "callable" in src:
        import importlib
        mod_path, _, func_name = src["callable"].partition(":")
        if ALLOWED_SKILL_CALLABLES and mod_path not in ALLOWED_SKILL_CALLABLES:
            return {"error": f"callable '{mod_path}' not in whitelist"}
        mod = importlib.import_module(mod_path)
        func = getattr(mod, func_name)
        result = func(**input_data) if not asyncio.iscoroutinefunction(func) else await func(**input_data)
        if not isinstance(result, dict):
            result = {"value": result}
        return result
    return {"note": "atomic skill executed via SDK", "skill": skill.code, "input": input_data}


async def run_skill_by_code(
    skills: list[Skill], skill_code: str, input_data: dict[str, Any]
) -> dict[str, Any]:
    """Look up a skill by code and execute it."""
    skill = next((s for s in skills if s.code == skill_code), None)
    if not skill:
        return {"error": f"skill not found: {skill_code}"}
    if skill.type == "atomic":
        return await run_atomic_skill(skill, input_data)
    # composite (nested)
    import yaml
    definition = yaml.safe_load(skill.source_json.get("yaml", "")) or {}
    executor = DAGExecutor(run_skill_by_code)
    return await executor.execute(definition, input_data)


async def load_skill_bundle(skill: Skill) -> dict[str, Any]:
    """Read SKILL.md + file listing for a path-based skill."""
    from pathlib import Path as _Path
    root = _Path(skill.source_json["path"])
    if not root.exists() or not root.is_dir():
        return {"error": f"skill directory missing: {root}"}
    skill_md_path = root / "SKILL.md"
    instructions = ""
    if skill_md_path.exists():
        try:
            instructions = skill_md_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:  # noqa: BLE001
            instructions = f"(failed to read SKILL.md: {e})"
    files: list[str] = []
    for p in root.rglob("*"):
        if p.is_file() and p.name != "SKILL.md":
            files.append(str(p.relative_to(root)))
            if len(files) >= 200:
                break
    return {
        "skill": skill.code,
        "instructions": instructions,
        "files": files,
        "hint": ("阅读 instructions 中的 SKILL.md 指令并按要求继续执行任务。"
                 "如需读取其它文件,调用 _read_skill_file(skill, path)。"),
    }


async def read_skill_file(
    skills: list[Skill], skill_code: str, rel_path: str
) -> dict[str, Any]:
    """Read a specific resource file inside a skill's directory."""
    from pathlib import Path as _Path
    skill = next((s for s in skills if s.code == skill_code), None)
    if not skill or skill.type != "atomic":
        return {"error": f"unknown skill: {skill_code}"}
    root = _Path((skill.source_json or {}).get("path", ""))
    if not root.exists():
        return {"error": "skill root missing"}
    target = (root / rel_path).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        return {"error": "path escape rejected"}
    if not target.exists() or not target.is_file():
        return {"error": "file not found"}
    if target.stat().st_size > 512 * 1024:
        return {"error": "file too large (>512KB)"}
    try:
        content = target.read_text(encoding="utf-8")
        return {"path": rel_path, "content": content}
    except UnicodeDecodeError:
        return {"path": rel_path, "content": "(binary file)", "binary": True}


async def run_skill_script(
    skills: list[Skill],
    skill_code: str,
    script: str,
    kwargs: dict[str, Any],
    output_filename: str,
    user_id: int | None,
) -> dict[str, Any]:
    """Run a skill script in an isolated subprocess with resource limits.

    Contract: the script receives JSON on stdin and must output JSON on stdout.
    The script can write output files to the directory specified by the
    SKILL_OUTPUT_DIR environment variable.
    """
    from pathlib import Path as _Path
    import sys as _sys
    import uuid as _uuid
    import asyncio as _asyncio
    import json as _json
    import os as _os
    import mimetypes as _mt
    import logging as _logging
    from ..core.config import settings
    from ..db.session import SessionLocal
    from ..services.downloads import register_file

    _log = _logging.getLogger(__name__)

    skill_row = next((s for s in skills if s.code == skill_code), None)
    if not skill_row or skill_row.type != "atomic":
        return {"error": f"unknown or non-atomic skill: {skill_code}"}
    root = _Path((skill_row.source_json or {}).get("path", ""))
    if not root.exists():
        return {"error": "skill root missing"}
    script_path = (root / script).resolve()
    try:
        script_path.relative_to(root.resolve())
    except ValueError:
        return {"error": "script path escape rejected"}
    if not script_path.exists() or script_path.suffix.lower() != ".py":
        return {"error": f"script not found or not .py: {script}"}

    # Prepare output target (force into outputs/<user_id>/)
    safe = _re.sub(r"[^\w\.\-]+", "_", output_filename).strip("._-") or "output"
    if len(safe) > 120:
        safe = safe[-120:]
    outputs_root = _Path(settings.STORAGE_ROOT) / "outputs" / str(user_id or "anon")
    outputs_root.mkdir(parents=True, exist_ok=True)
    target_path = outputs_root / f"{_uuid.uuid4().hex[:8]}-{safe}"

    # Filter kwargs to only safe types
    accepted = {}
    for k, v in (kwargs or {}).items():
        if isinstance(v, (str, int, float, bool, list, dict)):
            accepted[k] = v

    # Add output path hints
    for k in ("output", "output_path", "out", "outfile"):
        accepted.setdefault(k, str(target_path))

    try:
        proc = await asyncio.create_subprocess_exec(
            _sys.executable, "-u", str(script_path),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**_os.environ, "SKILL_OUTPUT_DIR": str(outputs_root)},
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=_json.dumps(accepted).encode()),
            timeout=300,
        )
        if proc.returncode != 0:
            return {"error": f"script failed (exit {proc.returncode}): {stderr.decode()[:500]}"}
        result = _json.loads(stdout.decode()) if stdout else {"status": "done"}
    except asyncio.TimeoutError:
        proc.kill()
        return {"error": "script timeout (>5min)"}
    except Exception as e:
        return {"error": f"subprocess error: {e}"}

    # Resolve which path actually got the output
    produced: _Path | None = None
    if isinstance(result, dict) and "output_path" in result:
        candidate = _Path(result["output_path"])
        if candidate.exists():
            produced = candidate.resolve()
    if produced is None and target_path.exists():
        produced = target_path

    if produced is None or not produced.exists():
        return {"error": "script ran but no output file produced"}

    if produced != target_path:
        try:
            produced.replace(target_path)
            produced = target_path
        except OSError:
            import shutil as _sh
            _sh.copy2(str(produced), str(target_path))
            produced = target_path

    mime = _mt.guess_type(safe)[0] or "application/octet-stream"
    size = produced.stat().st_size
    async with SessionLocal() as db:
        tok = await register_file(
            db, file_path=str(produced), file_name=safe,
            user_id=user_id, mime=mime,
        )
        await db.commit()
        download_url = f"/api/downloads/{tok.token}"

    try:
        output_path = str(produced.relative_to(_Path(settings.STORAGE_ROOT) / "outputs"))
    except ValueError:
        output_path = None

    info = {
        "name": safe, "size": size, "mime": mime,
        "ext": _Path(safe).suffix.lower(),
        "download_url": download_url, "preview_url": download_url,
    }
    if output_path:
        info["output_path"] = output_path
    return {"ok": True, "file": info, "message": f"已生成 {safe} ({size} bytes)。前端会显示文件卡片。"}


async def save_output_file(
    filename: str,
    content: str,
    user_id: int | None,
    saved_files: list[dict[str, Any]],
    mime: str | None = None,
    encoding: str = "utf-8",
) -> dict[str, Any]:
    """Persist an artifact and return a download URL.

    File goes to storage/outputs/<user_id>/<uuid>-<safe_name>.
    Side effect: appends to saved_files so the SSE layer can emit a `file` event.
    """
    from pathlib import Path as _Path
    import uuid as _uuid
    import base64 as _base64
    import mimetypes as _mt
    from ..core.config import settings
    from ..db.session import SessionLocal
    from ..services.downloads import register_file

    # Unwrap widget JSON envelope
    try:
        stripped = (content or "").lstrip()
        if stripped.startswith("{") and '"widget_code"' in stripped[:500]:
            parsed = json.loads(stripped)
            inner = parsed.get("widget_code")
            if isinstance(inner, str) and inner.strip():
                content = inner
                sniff = inner.lstrip()[:200].lower()
                if sniff.startswith("<svg"):
                    new_ext = ".svg"
                elif sniff.startswith("<!doctype html") or sniff.startswith("<html"):
                    new_ext = ".html"
                elif "<style" in sniff or "<div" in sniff or "<canvas" in sniff:
                    new_ext = ".html"
                else:
                    new_ext = None
                if new_ext and not (filename or "").lower().endswith(new_ext):
                    base = _Path(filename or "output").stem or "output"
                    filename = base + new_ext
                    if new_ext == ".html":
                        mime = "text/html"
                    elif new_ext == ".svg":
                        mime = "image/svg+xml"
                if new_ext == ".svg":
                    pass
                elif new_ext == ".html" and "<!doctype" not in sniff and "<html" not in sniff:
                    content = (
                        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
                        "<title>" + (parsed.get("title") or "widget") + "</title>"
                        "</head><body style='margin:0'>" + content + "</body></html>"
                    )
                if new_ext == ".html":
                    content = _move_scripts_to_end(content)
    except (json.JSONDecodeError, KeyError, TypeError):
        pass

    if not filename or not content:
        return {"error": "filename and content are required"}

    safe = _re.sub(r"[^\w\.\-]+", "_", filename).strip("._-") or "output"
    if len(safe) > 120:
        safe = safe[-120:]
    ext = _Path(safe).suffix.lower()
    if not mime:
        mime = _mt.guess_type(safe)[0] or "application/octet-stream"

    outputs_root = _Path(settings.STORAGE_ROOT) / "outputs" / str(user_id or "anon")
    outputs_root.mkdir(parents=True, exist_ok=True)
    target = outputs_root / f"{_uuid.uuid4().hex[:8]}-{safe}"

    try:
        if encoding == "base64":
            target.write_bytes(_base64.b64decode(content))
        else:
            target.write_text(content, encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        return {"error": f"write failed: {e}"}

    size = target.stat().st_size
    if size > 20 * 1024 * 1024:
        target.unlink(missing_ok=True)
        return {"error": "file too large (>20MB)"}

    async with SessionLocal() as db:
        tok = await register_file(
            db, file_path=str(target), file_name=safe,
            user_id=user_id, mime=mime,
        )
        await db.commit()
        download_url = f"/api/downloads/{tok.token}"

    try:
        output_path = str(target.relative_to(_Path(settings.STORAGE_ROOT) / "outputs"))
    except ValueError:
        output_path = None

    info = {
        "name": safe, "size": size, "mime": mime, "ext": ext,
        "download_url": download_url, "preview_url": download_url,
    }
    if output_path:
        info["output_path"] = output_path
    saved_files.append(info)
    return {
        "ok": True,
        "file": {"name": safe, "size": size, "mime": mime},
        "message": f"已保存 {safe} ({size} bytes)。前端会显示文件卡片,无需把内容再粘贴给用户。",
    }


def extract_fallback_files(
    full_text: str,
    user_id: int | None,
    saved_files: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Stream-tail safety net: extract large code blocks as downloadable files.

    Only triggers for blocks >= MIN_BYTES and when no files were already saved.
    """
    import asyncio
    if not full_text or not user_id:
        return []
    if saved_files:
        return []
    MIN_BYTES = 2048
    pattern = _re.compile(r"```([a-zA-Z0-9+\-]*)\s*\n(.*?)\n```", _re.DOTALL)
    results = []
    idx = 0
    for m in pattern.finditer(full_text):
        lang = (m.group(1) or "").lower()
        body = m.group(2) or ""
        if len(body.encode("utf-8")) < MIN_BYTES:
            continue
        ext = {
            "html": "html", "htm": "html",
            "markdown": "md", "md": "md",
            "json": "json", "yaml": "yaml", "yml": "yaml",
            "python": "py", "py": "py",
            "javascript": "js", "js": "js", "typescript": "ts", "ts": "ts",
            "css": "css", "sql": "sql", "xml": "xml",
            "svg": "svg",
        }.get(lang, "txt")
        idx += 1
        # Note: caller should await save_output_file in an async context
        # This function is sync; we return the data for the caller to save
        results.append({
            "filename": f"output-{idx}.{ext}",
            "content": body,
        })
    return results


async def extract_fallback_files_async(
    full_text: str,
    user_id: int | None,
    saved_files: list[dict[str, Any]],
) -> None:
    """Async version: extract large code blocks and save them."""
    import asyncio
    if not full_text or not user_id:
        return
    if saved_files:
        return
    MIN_BYTES = 2048
    pattern = _re.compile(r"```([a-zA-Z0-9+\-]*)\s*\n(.*?)\n```", _re.DOTALL)
    idx = 0
    for m in pattern.finditer(full_text):
        lang = (m.group(1) or "").lower()
        body = m.group(2) or ""
        if len(body.encode("utf-8")) < MIN_BYTES:
            continue
        ext = {
            "html": "html", "htm": "html",
            "markdown": "md", "md": "md",
            "json": "json", "yaml": "yaml", "yml": "yaml",
            "python": "py", "py": "py",
            "javascript": "js", "js": "js", "typescript": "ts", "ts": "ts",
            "css": "css", "sql": "sql", "xml": "xml",
            "svg": "svg",
        }.get(lang, "txt")
        idx += 1
        await save_output_file(
            filename=f"output-{idx}.{ext}",
            content=body,
            user_id=user_id,
            saved_files=saved_files,
        )


async def register_skill_files(
    result: dict[str, Any],
    user_id: int | None,
) -> dict[str, Any]:
    """Register files in result['_files'] as downloadable."""
    if not isinstance(result, dict):
        return result
    files = result.get("_files")
    if not isinstance(files, list) or not files:
        return result
    from pathlib import Path as _P
    from ..core.config import settings
    from ..db.session import SessionLocal
    from ..services.downloads import register_file
    outputs_root = (_P(settings.STORAGE_ROOT) / "outputs").resolve()
    registered = []
    async with SessionLocal() as db:
        for f in files:
            try:
                fp = f.get("path") or ""
                tok = await register_file(
                    db,
                    file_path=fp,
                    file_name=f.get("name") or "",
                    user_id=user_id,
                    mime=f.get("mime") or "application/octet-stream",
                )
                await db.commit()
                item = {
                    "name": tok.file_name, "size": tok.size, "mime": tok.mime,
                    "download_url": f"/api/downloads/{tok.token}",
                }
                try:
                    rp = _P(fp).resolve().relative_to(outputs_root)
                    item["output_path"] = str(rp)
                except (ValueError, OSError):
                    pass
                registered.append(item)
            except Exception as e:  # noqa: BLE001
                registered.append({"error": f"register failed: {e}"})
    result.pop("_files", None)
    result["files"] = [
        {k: v for k, v in item.items() if k not in ("download_url",)}
        for item in registered
    ]
    return result


# ---------- internal helpers ----------

def _move_scripts_to_end(html: str) -> str:
    """Move every <script>...</script> block to just before </body>."""
    import re as _re_mod
    if "<body" not in html.lower():
        return html
    script_pattern = _re_mod.compile(r"<script\b[^>]*>[\s\S]*?</script>", _re_mod.IGNORECASE)
    scripts = script_pattern.findall(html)
    if not scripts:
        return html
    stripped = script_pattern.sub("", html)
    body_close = _re_mod.search(r"</body\s*>", stripped, _re_mod.IGNORECASE)
    block = "\n" + "\n".join(scripts) + "\n"
    if body_close:
        i = body_close.start()
        return stripped[:i] + block + stripped[i:]
    return stripped + block
