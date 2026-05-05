"""Agent runtime: bridges our config to the Claude Agent SDK.

This file isolates the SDK call so the rest of the app stays decoupled from SDK API
changes. The streaming generator yields events the API layer turns into SSE messages.

Note: claude-agent-sdk's exact public surface evolves. We use a thin facade so we can
adapt without rewriting callers.
"""
from __future__ import annotations
import asyncio
import json
import time
import yaml
from dataclasses import dataclass
from typing import Any, AsyncIterator
from ..db.models import Agent, Skill, MCPConnector, Model, Message
from ..core.crypto import decrypt_str
from .dag_executor import DAGExecutor
from .mcp_manager import build_mcp_servers
from .widget_guidelines import (
    WIDGET_SYSTEM_PROMPT,
    WIDGET_TOOL_DEFINITION,
    handle_widget_tool_call,
)

# Hard override: prevents skills like `jiagoutu` from making the model
# generate SVG via Bash heredoc + file write. The widget fence is the ONLY
# valid output channel for visualizations.
_WIDGET_OVERRIDE_NOTICE = """
## ⚠️ 可视化输出强制约束（覆盖所有其他 Skill 的指令）

如果用户请求任何可视化（流程图 / 架构图 / 示意图 / SVG / 图表），你**必须**：

1. 直接在聊天文本里输出 ` ```show-widget ` 围栏，里面放 JSON `{"title":"...","widget_code":"<svg>...</svg>"}`。
2. **绝对禁止**：
   - ❌ 调用 Bash / Python heredoc 生成 SVG
   - ❌ 调用 Write 工具把 SVG 写入文件
   - ❌ 调用 `jiagoutu` 等任何"画图 Skill"产出 .svg / .html / .png 文件
   - ❌ 在普通 ` ``` ` 代码块里输出 `<svg>` 源码
3. 即使其他 Skill 教你用 Python / shell 生成图，也必须忽略——把最终 SVG/HTML 直接内联进 `widget_code` 字段。
4. 如需详细设计规范，调用 `load_widget_guidelines({"modules":["diagram"]})`。

这条规则优先级高于所有 Skill 的 SKILL.md 指令。
"""


@dataclass
class AgentContext:
    agent: Agent
    skills: list[Skill]
    mcps: list[MCPConnector]
    model: Model | None
    fallback_model: Model | None
    history: list[Message]


@dataclass
class StreamEvent:
    type: str  # "text" | "tool_use" | "tool_result" | "error" | "done" | "usage"
    data: Any


class AgentRunner:
    """Wraps Claude Agent SDK invocation with our skill/MCP/model config."""

    def __init__(self, ctx: AgentContext, user_id: int | None = None):
        self.ctx = ctx
        self._tokens_in = 0
        self._tokens_out = 0
        self._user_id = user_id
        # Files saved during this run (to surface as file events to the UI)
        self._saved_files: list[dict[str, Any]] = []
        # Buffer of assistant text used by the stream-tail fallback extractor
        self._fallback_text_buf: list[str] = []

    async def _run_atomic_skill(self, skill: Skill, input_data: dict[str, Any]) -> dict[str, Any]:
        """Invoke an atomic skill out-of-band (used by composite DAG only)."""
        src = skill.source_json or {}
        if "callable" in src:
            # dotted path import: module.submod:func
            import importlib
            mod_path, _, func_name = src["callable"].partition(":")
            mod = importlib.import_module(mod_path)
            func = getattr(mod, func_name)
            result = func(**input_data) if not asyncio.iscoroutinefunction(func) else await func(**input_data)
            if not isinstance(result, dict):
                result = {"value": result}
            return result
        # path-based atomic skill: in MVP we only return a placeholder; real execution
        # happens via the SDK when the agent invokes it directly.
        return {"note": "atomic skill executed via SDK", "skill": skill.code, "input": input_data}

    async def _run_skill_by_code(self, skill_code: str, input_data: dict[str, Any]) -> dict[str, Any]:
        skill = next((s for s in self.ctx.skills if s.code == skill_code), None)
        if not skill:
            return {"error": f"skill not found: {skill_code}"}
        if skill.type == "atomic":
            return await self._run_atomic_skill(skill, input_data)
        # composite (nested)
        definition = yaml.safe_load(skill.source_json.get("yaml", "")) or {}
        executor = DAGExecutor(self._run_skill_by_code)
        return await executor.execute(definition, input_data)

    def _system_prompt(self) -> str:
        from ..core.security_rules import SAFETY_PREFIX
        # SAFETY_PREFIX is mandatory and comes first — per-agent prompts cannot weaken it.
        # Widget capability + override notice next, then per-agent + skill descriptions.
        parts = [SAFETY_PREFIX, WIDGET_SYSTEM_PROMPT, _WIDGET_OVERRIDE_NOTICE]
        if self.ctx.agent.system_prompt:
            parts.append(self.ctx.agent.system_prompt)
        if self.ctx.skills:
            parts.append("\n## 你可使用的 Skills\n")
            for s in self.ctx.skills:
                tag = "组合" if s.type == "composite" else "原子"
                parts.append(f"- **{s.code}** ({tag}): {s.description or '(无描述)'}")
        return "\n".join(parts).strip()

    def _build_openai_tools(self) -> list[dict[str, Any]]:
        """Expose every enabled skill as an OpenAI function-calling tool.

        - composite           → executes the YAML DAG
        - atomic.callable     → invokes the Python function
        - atomic.path         → returns SKILL.md content + directory file listing,
                                so the model learns the skill's instructions and can
                                follow them in the same conversation. (mirrors Anthropic
                                Skill's "load-on-demand" semantics for OpenAI providers)
        """
        tools: list[dict[str, Any]] = []
        for s in self.ctx.skills:
            tools.append({
                "type": "function",
                "function": {
                    "name": s.code,
                    "description": s.description or s.name,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "input": {
                                "type": "object",
                                "description": "Skill 输入。对于路径式 atomic Skill,首次调用通常无需参数即可加载指令;之后再次调用可携带具体参数",
                            },
                        },
                        "additionalProperties": True,
                    },
                },
            })
        # Helper tool for reading additional files inside a path-based skill bundle
        if any(s.type == "atomic" and (s.source_json or {}).get("path") for s in self.ctx.skills):
            tools.append({
                "type": "function",
                "function": {
                    "name": "_read_skill_file",
                    "description": "读取已加载 Skill 目录下的具体资源文件(模板、脚本、参考资料等)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "skill": {"type": "string", "description": "Skill 的 code"},
                            "path": {"type": "string", "description": "相对 Skill 根目录的路径,如 templates/foo.html"},
                        },
                        "required": ["skill", "path"],
                    },
                },
            })
        # Universal output-file save tool. Always available, so any skill (or the model
        # itself) can persist a generated artifact and surface it to the user with a
        # download URL. The model MUST call this instead of pasting large code blobs
        # to the user.
        tools.append({
            "type": "function",
            "function": {
                "name": "save_output_file",
                "description": (
                    "保存生成的文件并返回下载链接。"
                    "适用于 PPT(.html)、文档(.md/.docx)、PDF、代码、报告等任何需要交付给用户的产物。"
                    "调用本工具后,前端会显示一张文件卡片,用户可下载或在右侧分屏预览。"
                    "禁止把大段 HTML/Markdown/代码直接打字给用户 —— 一律改为调用本工具保存。"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "文件名,带扩展名。如 'agent-intro.html'、'report.md'、'output.pdf'",
                        },
                        "content": {
                            "type": "string",
                            "description": "完整文件内容(文本)。二进制请用 base64 编码并将 mime 设置正确。",
                        },
                        "mime": {
                            "type": "string",
                            "description": "可选,MIME 类型。留空自动按扩展名推断",
                        },
                        "encoding": {
                            "type": "string",
                            "description": "content 编码: 'utf-8' (默认) 或 'base64'",
                        },
                    },
                    "required": ["filename", "content"],
                },
            },
        })
        # Run a python script that's bundled inside a path-based atomic skill.
        # We call it as an in-process function (no Bash needed). The script must
        # expose a callable named `generate` (preferred) or be importable; we run
        # it inside a sandboxed namespace so we don't pollute the parent process.
        if any(s.type == "atomic" and (s.source_json or {}).get("path") for s in self.ctx.skills):
            tools.append({
                "type": "function",
                "function": {
                    "name": "run_skill_script",
                    "description": (
                        "运行已加载 Skill 目录下的 Python 脚本(如 scripts/generate_docx.py)生成产物。"
                        "脚本必须导出名为 generate 的函数;调用后我们会自动把 output_filename 指向的产物文件登记为可下载文件。"
                        "用例:公文生成、表格导出、PDF 渲染等需要执行 Python 的场景。"
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "skill": {"type": "string", "description": "Skill 的 code"},
                            "script": {"type": "string",
                                        "description": "相对 Skill 根目录的脚本路径,如 scripts/generate_docx.py"},
                            "kwargs": {"type": "object",
                                        "description": "传给脚本 generate(**kwargs) 的参数字典"},
                            "output_filename": {"type": "string",
                                        "description": "希望最终交付给用户的文件名,如 '关于xx的通知.docx'。会自动落到隔离目录"},
                        },
                        "required": ["skill", "script", "kwargs", "output_filename"],
                    },
                },
            })
        # Generative-UI widget guidelines loader (always available)
        tools.append(WIDGET_TOOL_DEFINITION)
        return tools

    async def _exec_skill(self, skill_code: str, args: dict[str, Any]) -> dict[str, Any]:
        # built-in helper for reading skill bundle files
        if skill_code == "_read_skill_file":
            return await self._read_skill_file(args.get("skill", ""), args.get("path", ""))

        # Universal output saver
        if skill_code == "save_output_file":
            return await self._save_output_file(
                filename=str(args.get("filename") or "output"),
                content=args.get("content") or "",
                mime=args.get("mime") or None,
                encoding=args.get("encoding") or "utf-8",
            )

        # Run a bundled Skill python script
        if skill_code == "run_skill_script":
            return await self._run_skill_script(
                skill=str(args.get("skill") or ""),
                script=str(args.get("script") or ""),
                kwargs=args.get("kwargs") or {},
                output_filename=str(args.get("output_filename") or "output.bin"),
            )

        # generative-UI widget guidelines loader
        if skill_code == "load_widget_guidelines":
            return {"guidelines": handle_widget_tool_call(args)}

        skill = next((s for s in self.ctx.skills if s.code == skill_code), None)
        if not skill:
            return {"error": f"unknown skill: {skill_code}"}

        # path-based atomic skill: return SKILL.md + file listing so the model can follow instructions
        if skill.type == "atomic" and (skill.source_json or {}).get("path"):
            return await self._load_skill_bundle(skill)

        # callable / composite: actually execute
        trigger = args.get("input") if isinstance(args, dict) and "input" in args else args
        if not isinstance(trigger, dict):
            trigger = {"value": trigger}
        result = await self._run_skill_by_code(skill_code, trigger)
        # If the skill produced files, register them as downloadable URLs so the model
        # (and the user) can reference them. Convention: result may include
        #   "_files": [{"path": "/abs/path", "name": "report.docx", "mime": "..."}]
        result = await self._register_skill_files(result)
        return result

    async def _register_skill_files(self, result: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(result, dict):
            return result
        files = result.get("_files")
        if not isinstance(files, list) or not files:
            return result
        from ..db.session import SessionLocal
        from ..services.downloads import register_file
        registered = []
        async with SessionLocal() as db:
            for f in files:
                try:
                    tok = await register_file(
                        db,
                        file_path=f.get("path"),
                        file_name=f.get("name") or "",
                        user_id=self._user_id,
                        mime=f.get("mime") or "application/octet-stream",
                    )
                    await db.commit()
                    registered.append({
                        "name": tok.file_name, "size": tok.size, "mime": tok.mime,
                        "download_url": f"/api/downloads/{tok.token}",
                    })
                except Exception as e:  # noqa: BLE001
                    registered.append({"error": f"register failed: {e}"})
        result.pop("_files", None)
        result["files"] = registered
        return result

    async def _load_skill_bundle(self, skill) -> dict[str, Any]:
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

    async def _save_output_file(
        self, filename: str, content: str, mime: str | None = None,
        encoding: str = "utf-8",
    ) -> dict[str, Any]:
        """Persist an artifact and return a download URL.

        File goes to storage/outputs/<user_id>/<uuid>-<safe_name>.
        Side effect: appends to self._saved_files so the SSE layer can emit a `file` event.
        """
        from pathlib import Path as _Path
        import re as _re
        import uuid as _uuid
        import base64 as _base64
        import mimetypes as _mt
        from ..core.config import settings
        from ..db.session import SessionLocal
        from ..services.downloads import register_file

        if not filename or not content:
            return {"error": "filename and content are required"}

        # Sanitize filename
        safe = _re.sub(r"[^\w\.\-]+", "_", filename).strip("._-") or "output"
        if len(safe) > 120:
            safe = safe[-120:]
        ext = _Path(safe).suffix.lower()
        if not mime:
            mime = _mt.guess_type(safe)[0] or "application/octet-stream"

        outputs_root = _Path(settings.STORAGE_ROOT) / "outputs" / str(self._user_id or "anon")
        outputs_root.mkdir(parents=True, exist_ok=True)
        target = outputs_root / f"{_uuid.uuid4().hex[:8]}-{safe}"

        # Decode content
        try:
            if encoding == "base64":
                target.write_bytes(_base64.b64decode(content))
            else:
                target.write_text(content, encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            return {"error": f"write failed: {e}"}

        # Cap individual file size to 20 MB (best-effort post-write check)
        size = target.stat().st_size
        if size > 20 * 1024 * 1024:
            target.unlink(missing_ok=True)
            return {"error": "file too large (>20MB)"}

        # Register download token
        async with SessionLocal() as db:
            tok = await register_file(
                db, file_path=str(target), file_name=safe,
                user_id=self._user_id, mime=mime,
            )
            await db.commit()
            download_url = f"/api/downloads/{tok.token}"

        info = {
            "name": safe, "size": size, "mime": mime, "ext": ext,
            "download_url": download_url, "preview_url": download_url,
        }
        self._saved_files.append(info)
        return {
            "ok": True,
            "file": info,
            "message": f"已保存 {safe} ({size} bytes)。前端会显示文件卡片,无需把内容再粘贴给用户。",
        }

    async def _extract_fallback_files(self, full_text: str) -> None:
        """Stream-tail safety net: if the model pasted a large code block to text
        instead of calling save_output_file, persist it ourselves so the user can
        download it. Only triggers for blocks >= MIN_BYTES."""
        import re as _re
        if not full_text or not self._user_id:
            return
        # If the model already saved files this turn, don't double-extract
        if self._saved_files:
            return
        MIN_BYTES = 2048
        # Match fenced code blocks: ```lang\n...\n```
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
            await self._save_output_file(filename=f"output-{idx}.{ext}", content=body)

    async def _run_skill_script(
        self, skill: str, script: str, kwargs: dict[str, Any], output_filename: str,
    ) -> dict[str, Any]:
        """Execute a bundled Skill python script as an in-process function call.

        Contract: the script must define `generate(**kwargs) -> str` returning the
        path of the file it produced (or accept an `output` kwarg with the target path).
        We pass the safe target path automatically and the script is expected to
        write to that exact location.

        Security:
        - Script must live inside the skill directory (no escapes).
        - Skill must be enabled and bound to this agent.
        - Output is forced into outputs/<user_id>/, then registered as a download token.
        - Runs in the parent process (no Bash). For untrusted code use a separate
          subprocess sandbox in a future iteration.
        """
        from pathlib import Path as _Path
        import importlib.util as _ilu
        import sys as _sys
        import uuid as _uuid
        import re as _re
        import asyncio as _asyncio
        import inspect as _inspect
        import mimetypes as _mt
        from ..core.config import settings
        from ..db.session import SessionLocal
        from ..services.downloads import register_file

        skill_row = next((s for s in self.ctx.skills if s.code == skill), None)
        if not skill_row or skill_row.type != "atomic":
            return {"error": f"unknown or non-atomic skill: {skill}"}
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
        outputs_root = _Path(settings.STORAGE_ROOT) / "outputs" / str(self._user_id or "anon")
        outputs_root.mkdir(parents=True, exist_ok=True)
        target_path = outputs_root / f"{_uuid.uuid4().hex[:8]}-{safe}"

        # Inject the target path into kwargs under a few common parameter names
        # The script can use whichever it likes.
        if isinstance(kwargs, dict):
            call_kwargs = dict(kwargs)
        else:
            return {"error": "kwargs must be an object"}
        for k in ("output", "output_path", "out", "outfile"):
            call_kwargs.setdefault(k, str(target_path))

        # Dynamically import the script as a fresh module
        mod_name = f"_h3c_skill_{skill}_{script_path.stem}_{_uuid.uuid4().hex[:6]}"
        spec = _ilu.spec_from_file_location(mod_name, script_path)
        if spec is None or spec.loader is None:
            return {"error": "failed to load script spec"}
        mod = _ilu.module_from_spec(spec)
        # Allow the script to import sibling modules from its directory
        _sys.path.insert(0, str(script_path.parent))
        try:
            try:
                spec.loader.exec_module(mod)
            except Exception as e:  # noqa: BLE001
                return {"error": f"script import failed: {e}"}
            fn = getattr(mod, "generate", None)
            if not callable(fn):
                return {"error": "script must define a callable `generate(**kwargs)`"}
            # Filter kwargs to only those accepted by `generate`
            try:
                sig = _inspect.signature(fn)
                if not any(p.kind == _inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                    accepted = {n: v for n, v in call_kwargs.items() if n in sig.parameters}
                else:
                    accepted = call_kwargs
            except (TypeError, ValueError):
                accepted = call_kwargs
            try:
                if _asyncio.iscoroutinefunction(fn):
                    result = await fn(**accepted)
                else:
                    result = await _asyncio.to_thread(lambda: fn(**accepted))
            except TypeError as e:
                return {"error": f"argument mismatch: {e}", "expected_kwargs": list(sig.parameters.keys()) if 'sig' in dir() else None}
            except Exception as e:  # noqa: BLE001
                return {"error": f"script execution failed: {e}"}
        finally:
            try:
                _sys.path.remove(str(script_path.parent))
            except ValueError:
                pass

        # Resolve which path actually got the output
        produced: _Path | None = None
        if isinstance(result, str) and _Path(result).exists():
            produced = _Path(result).resolve()
        elif target_path.exists():
            produced = target_path

        if produced is None or not produced.exists():
            return {"error": "script ran but no output file produced"}

        # If script wrote elsewhere (e.g. inside skill dir), move/copy to target_path
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
                user_id=self._user_id, mime=mime,
            )
            await db.commit()
            download_url = f"/api/downloads/{tok.token}"

        info = {
            "name": safe, "size": size, "mime": mime,
            "ext": _Path(safe).suffix.lower(),
            "download_url": download_url, "preview_url": download_url,
        }
        self._saved_files.append(info)
        return {"ok": True, "file": info, "message": f"已生成 {safe} ({size} bytes)。前端会显示文件卡片。"}

    async def _read_skill_file(self, skill_code: str, rel_path: str) -> dict[str, Any]:
        from pathlib import Path as _Path
        skill = next((s for s in self.ctx.skills if s.code == skill_code), None)
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

    async def stream(self, user_text: str, files: list[dict[str, Any]] | None = None) -> AsyncIterator[StreamEvent]:
        """Yield streaming events.

        Routes by provider:
        - anthropic                         → Claude Agent SDK (full Skills/MCP support)
        - deepseek/qwen/glm/openai/openai-compatible → OpenAI-compatible chat-completions stream
        """
        start = time.time()
        # Always emit a meta event first so the frontend knows which agent/model is being used
        if self.ctx.model:
            yield StreamEvent("meta", {
                "agent_name": self.ctx.agent.name,
                "agent_code": self.ctx.agent.code,
                "model_code": self.ctx.model.code,
                "model_id": self.ctx.model.model_id,
                "provider": self.ctx.model.provider,
            })
        provider = (self.ctx.model.provider if self.ctx.model else "anthropic").lower()
        try:
            inner = (self._stream_via_sdk(user_text, files or []) if provider == "anthropic"
                     else self._stream_via_openai(user_text, files or []))
            async for ev in inner:
                # Accumulate text for the fallback extractor (runs in finally)
                if ev.type == "text":
                    self._fallback_text_buf.append(ev.data.get("text", "") if isinstance(ev.data, dict) else "")
                yield ev
        except ImportError as e:
            yield StreamEvent("error", {"message": f"SDK 未安装: {e}"})
        except Exception as e:  # noqa: BLE001
            yield StreamEvent("error", {"message": f"agent 执行错误: {e}"})
        finally:
            # If the model dumped a large code block to text instead of calling
            # save_output_file, extract & persist it as a fallback.
            if self._fallback_text_buf:
                await self._extract_fallback_files("".join(self._fallback_text_buf))
            # Emit any saved files BEFORE done so the UI gets file cards in order
            for f in self._saved_files:
                yield StreamEvent("file", f)
            yield StreamEvent("done", {
                "tokens_in": self._tokens_in,
                "tokens_out": self._tokens_out,
                "latency_ms": int((time.time() - start) * 1000),
                "files": list(self._saved_files),
            })

    PROVIDER_BASE_URL: dict[str, str] = {
        "deepseek": "https://api.deepseek.com/v1",
        "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "glm": "https://open.bigmodel.cn/api/paas/v4",
    }

    @staticmethod
    def _render_attachments(files: list[dict[str, Any]]) -> str:
        """Render uploaded files as a structured attachment block for the model.

        Includes the parsed markdown when available, otherwise a status note.
        """
        if not files:
            return ""
        sections: list[str] = []
        for f in files:
            name = f.get("name") or "file"
            status = f.get("parse_status") or "unknown"
            md = f.get("parsed_markdown")
            chars = len(md) if isinstance(md, str) else 0
            head = f"### 📎 {name}"
            if chars:
                head += f"  · {chars} 字符"
            if status == "done" and md:
                sections.append(f"{head}\n\n```\n{md}\n```")
            elif status == "parsing":
                sections.append(f"{head}\n\n(文件正在解析中,本轮无法读取内容)")
            elif status == "failed":
                err = f.get("parse_error") or "未知错误"
                sections.append(f"{head}\n\n(文件解析失败: {err})")
            else:
                sections.append(f"{head}\n\n(文件未解析,可向用户说明)")
        body = "\n\n".join(sections)
        return ("\n\n---\n\n# 用户上传的附件(已解析为文本,你可以直接引用其中内容)\n\n"
                f"{body}\n\n---\n")

    @staticmethod
    def normalize_base_url(url: str | None) -> str | None:
        """Append /v1 if base_url has no version suffix (common user mistake)."""
        if not url:
            return url
        import re
        u = url.rstrip("/")
        # already has /vN or a known API path -> leave alone
        if re.search(r"/v\d+$", u) or "/api/" in u or "/compatible-mode" in u:
            return u
        return u + "/v1"

    async def _stream_via_openai(self, user_text: str, files: list[dict[str, Any]]) -> AsyncIterator[StreamEvent]:
        from openai import AsyncOpenAI
        from contextlib import AsyncExitStack
        import json as _json

        model = self.ctx.model
        if not model:
            yield StreamEvent("error", {"message": "未配置默认模型"})
            return
        api_key = decrypt_str(model.api_key_enc) if model.api_key_enc else ""
        if not api_key:
            yield StreamEvent("error", {"message": "模型 API Key 未配置"})
            return
        base_url = model.base_url or self.PROVIDER_BASE_URL.get(model.provider.lower())
        base_url = self.normalize_base_url(base_url)
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)

        system = self._system_prompt() or "You are a helpful assistant."
        prompt = user_text
        if files:
            prompt += self._render_attachments(files)

        tools = self._build_openai_tools()
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        # Replay prior turns so the model has conversation context
        for h in (self.ctx.history or []):
            text = (h.content_json or {}).get("text") if isinstance(h.content_json, dict) else None
            if not text:
                continue
            messages.append({"role": h.role, "content": text})
        messages.append({"role": "user", "content": prompt})

        # ---- Open MCP sessions for the duration of this stream call ----
        mcp_stack = AsyncExitStack()
        mcp_sessions: dict[str, Any] = {}      # server_name -> ClientSession
        mcp_tool_routes: dict[str, tuple[str, str]] = {}  # exposed_tool_name -> (server, raw_tool)
        for mcp in self.ctx.mcps:
            try:
                session = await self._open_mcp_session(mcp_stack, mcp)
                mcp_sessions[mcp.name] = session
                tools_resp = await session.list_tools()
                for t in tools_resp.tools:
                    exposed = self._mcp_tool_name(mcp.name, t.name)
                    mcp_tool_routes[exposed] = (mcp.name, t.name)
                    tools.append({
                        "type": "function",
                        "function": {
                            "name": exposed,
                            "description": f"[MCP:{mcp.name}] {t.description or t.name}",
                            "parameters": getattr(t, "inputSchema", None) or {"type": "object"},
                        },
                    })
            except Exception as e:  # noqa: BLE001
                yield StreamEvent("error", {"message": f"MCP 服务器 {mcp.name} 连接失败: {e}"})

        try:
            # multi-turn loop: model may call skill / mcp tools, we execute and feed results back
            MAX_ITER = 8
            for _ in range(MAX_ITER):
                create_kwargs: dict[str, Any] = {
                    "model": model.model_id,
                    "messages": messages,
                    "stream": True,
                    "stream_options": {"include_usage": True},
                }
                if tools:
                    create_kwargs["tools"] = tools
                if model.extra_params_json:
                    create_kwargs["extra_body"] = model.extra_params_json

                stream = await client.chat.completions.create(**create_kwargs)

                # accumulate this turn
                text_buf = ""
                reasoning_buf = ""
                tool_calls_acc: dict[int, dict[str, Any]] = {}
                emitted_starts: set[str] = set()
                finish_reason: str | None = None

                async for chunk in stream:
                    if chunk.usage:
                        self._tokens_in += chunk.usage.prompt_tokens or 0
                        self._tokens_out += chunk.usage.completion_tokens or 0
                    for choice in chunk.choices or []:
                        delta = getattr(choice, "delta", None)
                        if delta:
                            reasoning = getattr(delta, "reasoning_content", None)
                            if reasoning:
                                reasoning_buf += reasoning
                                yield StreamEvent("thinking", {"text": reasoning})
                            if delta.content:
                                text_buf += delta.content
                                yield StreamEvent("text", {"text": delta.content})
                            for tc in getattr(delta, "tool_calls", None) or []:
                                idx = tc.index if tc.index is not None else 0
                                slot = tool_calls_acc.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                                if tc.id:
                                    slot["id"] = tc.id
                                fn = getattr(tc, "function", None)
                                if fn:
                                    if fn.name:
                                        slot["name"] = fn.name
                                    if fn.arguments:
                                        slot["arguments"] += fn.arguments
                                if slot["id"] and slot["name"] and slot["id"] not in emitted_starts:
                                    yield StreamEvent("tool_use", {
                                        "id": slot["id"], "name": slot["name"], "input": {},
                                    })
                                    emitted_starts.add(slot["id"])
                        if choice.finish_reason:
                            finish_reason = choice.finish_reason

                if not tool_calls_acc:
                    return

                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": text_buf or None,
                    "tool_calls": [
                        {
                            "id": s["id"], "type": "function",
                            "function": {"name": s["name"], "arguments": s["arguments"] or "{}"},
                        }
                        for s in sorted(tool_calls_acc.values(), key=lambda x: x.get("id", ""))
                        if s.get("id") and s.get("name")
                    ],
                }
                if reasoning_buf:
                    assistant_msg["reasoning_content"] = reasoning_buf
                messages.append(assistant_msg)

                # execute each tool call (route MCP tools to MCP server, others to skill executor)
                for slot in tool_calls_acc.values():
                    if not (slot.get("id") and slot.get("name")):
                        continue
                    try:
                        args = _json.loads(slot["arguments"] or "{}")
                    except Exception:
                        args = {"raw": slot["arguments"]}
                    yield StreamEvent("tool_use", {"id": slot["id"], "name": slot["name"], "input": args})
                    try:
                        if slot["name"] in mcp_tool_routes:
                            server_name, raw_tool = mcp_tool_routes[slot["name"]]
                            result = await self._call_mcp_tool(mcp_sessions[server_name], raw_tool, args)
                        else:
                            result = await self._exec_skill(slot["name"], args)
                    except Exception as e:  # noqa: BLE001
                        result = {"error": str(e)}
                    result_str = _json.dumps(result, ensure_ascii=False, default=str)
                    yield StreamEvent("tool_result", {"tool_use_id": slot["id"], "content": result_str})
                    messages.append({
                        "role": "tool", "tool_call_id": slot["id"],
                        "content": result_str,
                    })

            yield StreamEvent("error", {"message": f"工具调用循环超过 {MAX_ITER} 轮,已强制中断"})
        finally:
            await mcp_stack.aclose()

    @staticmethod
    def _mcp_tool_name(server: str, tool: str) -> str:
        # OpenAI function names allow [a-zA-Z0-9_-], must be <= 64 chars.
        import re as _re
        clean = _re.sub(r"[^a-zA-Z0-9_-]", "_", f"mcp__{server}__{tool}")
        return clean[:64]

    async def _open_mcp_session(self, stack, mcp):
        """Open an MCP ClientSession for the given MCPConnector row."""
        from mcp import ClientSession
        cfg = mcp.config_json or {}
        if mcp.transport == "stdio":
            from mcp import StdioServerParameters
            from mcp.client.stdio import stdio_client
            params = StdioServerParameters(
                command=cfg.get("command") or "",
                args=cfg.get("args", []) or [],
                env=cfg.get("env") or None,
            )
            read, write = await stack.enter_async_context(stdio_client(params))
        elif mcp.transport == "sse":
            from mcp.client.sse import sse_client
            read, write = await stack.enter_async_context(
                sse_client(cfg.get("url"), headers=cfg.get("headers") or None)
            )
        elif mcp.transport == "http":
            from mcp.client.streamable_http import streamablehttp_client
            ctx = await stack.enter_async_context(
                streamablehttp_client(cfg.get("url"), headers=cfg.get("headers") or None)
            )
            read, write = ctx[0], ctx[1]
        else:
            raise ValueError(f"unsupported transport: {mcp.transport}")
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        return session

    @staticmethod
    async def _call_mcp_tool(session, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        # Drop the OpenAI-style {"input": {...}} wrapper if the model added one
        call_args = args.get("input") if isinstance(args, dict) and "input" in args and len(args) == 1 else args
        if not isinstance(call_args, dict):
            call_args = {"value": call_args}
        result = await session.call_tool(tool_name, call_args)
        # Convert MCP CallToolResult → JSON-serialisable dict
        out_parts: list[str] = []
        for c in (result.content or []):
            text = getattr(c, "text", None)
            if text is not None:
                out_parts.append(text)
            else:
                out_parts.append(str(c))
        return {
            "isError": bool(getattr(result, "isError", False)),
            "content": "\n".join(out_parts),
        }


    def _build_skill_sandbox(self) -> "Path | None":
        """Per-Agent Skill sandbox for the Anthropic SDK path.

        Per the official docs (https://code.claude.com/docs/en/agent-sdk/skills) the
        SDK discovers skills via filesystem scanning of `<cwd>/.claude/skills/` (when
        `setting_sources` includes `"project"`). To isolate skills per-agent we build
        a temporary cwd whose `.claude/skills/` only contains symlinks to the skills
        selected for THIS agent. Other agents' skill directories are NOT linked, so
        the model has no path to reach them — even via Read/Bash.

        Composite/callable skills are not filesystem-based; they're surfaced via the
        system prompt only on the Anthropic path.

        Returns the sandbox root, or None if there are no path-based skills (caller
        will skip the cwd/setting_sources options entirely).
        Caller must rmtree the returned path when the SDK call completes.
        """
        from pathlib import Path as _Path
        import tempfile
        path_skills = [s for s in self.ctx.skills
                       if s.type == "atomic" and (s.source_json or {}).get("path")]
        if not path_skills:
            return None
        sandbox = _Path(tempfile.mkdtemp(prefix=f"h3c-agent-{self.ctx.agent.id}-"))
        skills_root = sandbox / ".claude" / "skills"
        skills_root.mkdir(parents=True, exist_ok=True)
        for s in path_skills:
            src = _Path(s.source_json["path"]).resolve()
            if not src.exists() or not src.is_dir():
                continue
            link = skills_root / src.name
            try:
                link.symlink_to(src)
            except FileExistsError:
                pass
            except OSError:
                # Fallback: filesystem doesn't allow symlinks → copy
                import shutil as _sh
                _sh.copytree(src, link, symlinks=False, dirs_exist_ok=True)
        return sandbox

    async def _stream_via_sdk(self, user_text: str, files: list[dict[str, Any]]) -> AsyncIterator[StreamEvent]:
        from claude_agent_sdk import query, ClaudeAgentOptions  # type: ignore
        import shutil as _shutil

        model = self.ctx.model
        if not model:
            yield StreamEvent("error", {"message": "未配置默认模型"})
            return

        # Build SDK options
        mcp_servers = build_mcp_servers(self.ctx.mcps)

        # Per-Agent Skill sandbox (filesystem isolation per official SDK docs).
        sandbox = self._build_skill_sandbox()

        # === Tool whitelist (security hardening) ===
        # Read-only + Skill + WebSearch are safe defaults. Bash/Write/Edit/NotebookEdit/
        # WebFetch are GLOBALLY DENIED — even if a SKILL.md instructs the model to
        # `bash xxx`, the SDK will refuse because Bash is not in allowed_tools.
        # MCP tools are added per-server: `mcp__<server>` allows all that server's tools.
        allowed_tools: list[str] = ["Read", "Glob", "Grep", "Skill", "WebSearch"]
        for mcp in self.ctx.mcps:
            if mcp.enabled:
                allowed_tools.append(f"mcp__{mcp.name}")

        options_kwargs: dict[str, Any] = {
            "model": model.model_id,
            "system_prompt": self._system_prompt(),
            "include_partial_messages": True,
            # Auto-approve tools that ARE in allowed_tools (no CLI prompt) — anything not
            # in allowed_tools is denied entirely, regardless of permission_mode.
            "permission_mode": "bypassPermissions",
            "allowed_tools": allowed_tools,
            # Belt-and-suspenders: explicitly disallow the dangerous trio in case some
            # SDK version honors disallowed_tools as an extra deny list.
            "disallowed_tools": ["Bash", "Write", "Edit", "NotebookEdit", "WebFetch"],
        }
        if mcp_servers:
            options_kwargs["mcp_servers"] = mcp_servers
        if sandbox is not None:
            options_kwargs["cwd"] = str(sandbox)
            options_kwargs["setting_sources"] = ["project"]
        if model.api_key_enc:
            options_kwargs["api_key"] = decrypt_str(model.api_key_enc)
        if model.base_url:
            options_kwargs["base_url"] = model.base_url

        # Filter to only kwargs the installed SDK actually accepts
        sdk_arg_names = ClaudeAgentOptions.__init__.__code__.co_varnames
        options = ClaudeAgentOptions(**{k: v for k, v in options_kwargs.items() if k in sdk_arg_names})

        prompt = user_text
        if files:
            prompt += self._render_attachments(files)

        # Prepend prior conversation as a transcript so the model has context.
        # (Claude Agent SDK's query() takes a single prompt; we concatenate.)
        if self.ctx.history:
            transcript_parts = []
            for h in self.ctx.history:
                txt = (h.content_json or {}).get("text") if isinstance(h.content_json, dict) else None
                if not txt:
                    continue
                role = "用户" if h.role == "user" else "助手"
                transcript_parts.append(f"{role}: {txt}")
            if transcript_parts:
                transcript = "\n\n".join(transcript_parts)
                prompt = (
                    "以下是此前的对话历史(供你理解上下文,不要在回答里重复):\n\n"
                    f"{transcript}\n\n---\n\n用户: {prompt}"
                )

        # Track current streaming tool_use block (id-keyed input JSON accumulator)
        current_tool_id: str | None = None
        current_tool_name: str | None = None
        current_tool_input_buf: str = ""

        try:
            async for msg in query(prompt=prompt, options=options):
                mtype = type(msg).__name__

                # ---- partial streaming events (token-level) ----
                if mtype == "StreamEvent" or mtype == "SDKPartialAssistantMessage":
                    event = getattr(msg, "event", None) or {}
                    et = event.get("type")
                    if et == "content_block_start":
                        cb = event.get("content_block", {}) or {}
                        if cb.get("type") == "tool_use":
                            current_tool_id = cb.get("id")
                            current_tool_name = cb.get("name")
                            current_tool_input_buf = ""
                            yield StreamEvent("tool_use", {
                                "id": current_tool_id, "name": current_tool_name, "input": {},
                            })
                        elif cb.get("type") == "thinking":
                            # thinking block start - nothing to emit yet
                            pass
                    elif et == "content_block_delta":
                        delta = event.get("delta", {}) or {}
                        dt = delta.get("type")
                        if dt == "text_delta":
                            chunk = delta.get("text", "")
                            if chunk:
                                yield StreamEvent("text", {"text": chunk})
                        elif dt == "thinking_delta":
                            chunk = delta.get("thinking", "")
                            if chunk:
                                yield StreamEvent("thinking", {"text": chunk})
                        elif dt == "input_json_delta":
                            current_tool_input_buf += delta.get("partial_json", "")
                    elif et == "content_block_stop":
                        if current_tool_id is not None:
                            try:
                                import json as _json
                                parsed = _json.loads(current_tool_input_buf) if current_tool_input_buf else {}
                            except Exception:
                                parsed = {"raw": current_tool_input_buf}
                            # update step with final input
                            yield StreamEvent("tool_use", {
                                "id": current_tool_id, "name": current_tool_name, "input": parsed,
                            })
                            current_tool_id = None
                            current_tool_name = None
                            current_tool_input_buf = ""
                    # message_start / message_delta / message_stop ignored

                # ---- user-side messages carry tool results from SDK's tool execution loop ----
                elif mtype == "UserMessage":
                    for block in getattr(msg, "content", []) or []:
                        btype = type(block).__name__
                        if btype == "ToolResultBlock":
                            yield StreamEvent("tool_result", {
                                "tool_use_id": getattr(block, "tool_use_id", ""),
                                "content": str(getattr(block, "content", "")),
                            })

                # ---- complete assistant message: only used as a fallback if partials were skipped ----
                elif mtype == "AssistantMessage":
                    # If partials are working, we already streamed text. Skip text re-emit.
                    # We still surface tool_result blocks here defensively (some SDK versions place them here).
                    for block in getattr(msg, "content", []) or []:
                        btype = type(block).__name__
                        if btype == "ToolResultBlock":
                            yield StreamEvent("tool_result", {
                                "tool_use_id": getattr(block, "tool_use_id", ""),
                                "content": str(getattr(block, "content", "")),
                            })

                elif mtype == "ResultMessage":
                    usage = getattr(msg, "usage", None) or {}
                    if isinstance(usage, dict):
                        self._tokens_in = usage.get("input_tokens", 0)
                        self._tokens_out = usage.get("output_tokens", 0)
        finally:
            if sandbox is not None:
                _shutil.rmtree(sandbox, ignore_errors=True)
