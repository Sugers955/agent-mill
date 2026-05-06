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

# Widget guidance — Skills take priority. Only injected when the user is
# asking for a visualization AND the agent has no skills loaded that might
# already handle it (e.g. `jiagoutu`). When skills are present, the model
# follows the skill's own SKILL.md instructions; widgets are the fallback
# path for agents that have no drawing skill configured.
_WIDGET_GUIDANCE = """
## 可视化输出指引（在没有更合适的 Skill 时使用）

当用户请求可视化（可视化 / 流程图 / 架构图 / 示意图 / SVG / 图表 / HTML / 网页 / 表单），
且你**没有更合适的 Skill** 来完成此任务时，请使用 `show-widget` 围栏在聊天里直接渲染：

```show-widget
{"title":"标题","widget_code":"<svg ...>...</svg>"}
```

widget_code 是 JSON 字符串：所有引号转义为 `\\"`，换行转义为 `\\n`，不要 DOCTYPE/html/head/body。

### 使用 widget 时的要求
- **首要任务**：调用 `load_widget_guidelines` 后，必须使用 `show-widget` 围栏在聊天里直接渲染——这是用户看到的"动态生图过程"
- 不要在普通 ` ``` ` 代码块里输出 `<svg>` 源码（前端不会渲染）
- 渲染完成后，请在围栏外补充 2-4 句中文文字说明图的要点，让回答有完整闭环
- **可选**：渲染完成后，如果用户后续可能下载，可以再调用 `save_output_file` 把同一份代码存成 .html / .svg 文件（系统会自动识别 widget JSON 包裹并解出真实的 HTML / SVG，不会保存成不可预览的 .txt）；不需要下载时不必调用
- 顺序：调用 `load_widget_guidelines` → 输出 ` ```show-widget ` 围栏 → 围栏闭合后再写文字 → （可选）调用 `save_output_file` 提供下载

### 何时该走 Skill 而不是 widget
- 当智能体命中或者已加载了画图相关的 Skill（如 `jiagoutu`），按 Skill 自身的 SKILL.md 指令执行，此时Skill是主导，widget是辅助手段（比如 Skill 产出图的源码，交给 widget 渲染）
- 当用户明确要求"生成文件 / 下载 / .svg / .html 文件"时，按文件产出走 Skill 工作流
"""


# Keywords that indicate the user wants a visualization / widget. When a recent
# user turn matches, we inject WIDGET_SYSTEM_PROMPT + override into the system
# message. Otherwise we skip them — saves tokens and avoids biasing the model
# toward widgets on non-viz turns.
_VIZ_KEYWORDS_GENERAL = (
    "可视化", "visualize", "visualization",
    "图表", "chart", "graph", "plot",
    "流程图", "flowchart", "diagram", "时序图", "sequence",
    "架构图", "architecture",
    "示意图", "illustration",
    "曲线图", "折线图", "柱状图", "bar chart", "pie chart",
    "svg", "饼图",
    "widget", "interactive",
    "画一个", "画个", "draw", "create a chart", "render",
)
_VIZ_KEYWORDS_HTML = (
    "html", "html文件", "网页", "页面",
    "表单", "form",
    "标签页", "tabs", "accordion",
    "表格", "table", "grid",
    "交互", "interactive ui",
    "浏览器页面", "系统界面",
    "页面 demo", "页面demo",
)


def _wants_widget(text: str) -> bool:
    if not text:
        return False
    low = text.lower()
    return any(k.lower() in low for k in _VIZ_KEYWORDS_GENERAL + _VIZ_KEYWORDS_HTML)


# Keywords in a Skill's name / code / description that indicate it already
# handles SVG/HTML diagram generation and would conflict with the widget
# pipeline. When matched, we DON'T inject the widget guidance — the model
# follows that Skill's own instructions instead.
#
# Keep this list narrow! Generic terms like "ppt" or "report" or the single
# character "画" are too aggressive — a PPT generator doesn't conflict with
# diagram rendering; they're different output categories. Only list things
# that are TRULY about drawing diagrams to disk.
_DRAWING_SKILL_HINTS = (
    "画图", "绘图", "架构图", "流程图", "时序图",
    "示意图", "可视化生成", "diagram generator", "svg generator",
)


def _agent_has_drawing_skill(skills: list[Skill]) -> bool:
    for s in skills or []:
        haystack = " ".join(filter(None, [s.code, s.name, s.description])).lower()
        if any(h.lower() in haystack for h in _DRAWING_SKILL_HINTS):
            return True
    return False


def _move_scripts_to_end(html: str) -> str:
    """Move every <script>...</script> block to just before </body>.

    Mirrors the widget iframe receiver's "DOM first, scripts last" strategy.
    Without this, a saved standalone .html file breaks when the model wrote
    its <script> at the top of the body — DOM elements referenced via
    document.getElementById are not yet in the tree, and onclick handlers
    can fire before the script's let/const declarations finish.

    Idempotent: if there's no <body>, returns html unchanged.
    """
    import re as _re
    if "<body" not in html.lower():
        return html
    # Extract all <script>...</script> blocks (with their attrs)
    script_pattern = _re.compile(r"<script\b[^>]*>[\s\S]*?</script>", _re.IGNORECASE)
    scripts = script_pattern.findall(html)
    if not scripts:
        return html
    stripped = script_pattern.sub("", html)
    # Insert scripts just before </body>; if no </body>, append at end.
    body_close = _re.search(r"</body\s*>", stripped, _re.IGNORECASE)
    block = "\n" + "\n".join(scripts) + "\n"
    if body_close:
        i = body_close.start()
        return stripped[:i] + block + stripped[i:]
    return stripped + block


def _prefix_mcp_actions(ui_schema: dict[str, Any], mcp_name: str) -> None:
    """Rewrite `action.tool` entries from bare names to `mcp__<server>__<tool>`.

    MCP authors often write `tool: "init_booking"` in their UI Schema actions
    without knowing about our `mcp__<server>__` namespacing. We rewrite in-place
    so the [UI_ACTION] router resolves back to THIS MCP, not a same-named tool
    elsewhere. Already-prefixed tool names (any `mcp__...`) are left alone.
    """
    prefix = f"mcp__{mcp_name}__"
    for a in (ui_schema.get("actions") or []):
        if not isinstance(a, dict):
            continue
        t = a.get("tool")
        if isinstance(t, str) and t and not t.startswith("mcp__"):
            a["tool"] = prefix + t


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
        # UI Schemas emitted during this run (for chat.py to persist into history)
        self._saved_ui: list[dict[str, Any]] = []
        # Buffer of assistant text used by the stream-tail fallback extractor
        self._fallback_text_buf: list[str] = []
        # Set to True the moment the model calls `load_widget_guidelines` —
        # signals "I'm rendering via widget pipeline this turn", so any later
        # save_output_file with widget-shaped content is rejected to avoid
        # the duplicated output-1.txt file card next to the rendered widget.
        self._widget_pipeline_active: bool = False

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

    def _system_prompt(self, user_text: str | None = None) -> str:
        from ..core.security_rules import SAFETY_PREFIX
        # SAFETY_PREFIX is mandatory and comes first — per-agent prompts cannot weaken it.
        parts = [SAFETY_PREFIX]
        # Skills come first. We only inject the widget capability + guidance
        # when (1) the user is asking for a visualization AND (2) the agent
        # has no drawing-related Skill loaded. If a drawing Skill exists,
        # the model follows that Skill's own SKILL.md — widget is the
        # fallback path for skill-less agents.
        wants_viz = _wants_widget(user_text or "")
        has_drawing_skill = _agent_has_drawing_skill(self.ctx.skills)
        if wants_viz and not has_drawing_skill:
            parts.append(WIDGET_SYSTEM_PROMPT)
            parts.append(_WIDGET_GUIDANCE)
        if self.ctx.agent.system_prompt:
            parts.append(self.ctx.agent.system_prompt)
        if self.ctx.skills:
            parts.append("\n## 你可使用的 Skills\n")
            for s in self.ctx.skills:
                tag = "组合" if s.type == "composite" else "原子"
                parts.append(f"- **{s.code}** ({tag}): {s.description or '(无描述)'}")
        return "\n".join(parts).strip()

    def _build_openai_tools(self, user_text: str | None = None) -> list[dict[str, Any]]:
        """Expose every enabled skill as an OpenAI function-calling tool.

        - composite           → executes the YAML DAG
        - atomic.callable     → invokes the Python function
        - atomic.path         → returns SKILL.md content + directory file listing,
                                so the model learns the skill's instructions and can
                                follow them in the same conversation. (mirrors Anthropic
                                Skill's "load-on-demand" semantics for OpenAI providers)

        `save_output_file` and `run_skill_script` are always registered so the
        user gets a downloadable file card whenever the model calls them. The
        widget pipeline still owns the in-chat rendering — for widget content
        the save handler unwraps the JSON envelope into a real .html/.svg.
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
        # Universal output-file save tool — always available so the user gets
        # a downloadable file card whenever the model calls it. For widget JSON
        # content the save handler unwraps to a real .html/.svg automatically.
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
            # Lock this turn into the widget pipeline — any later attempt to
            # save widget-shaped content via save_output_file is rejected so
            # the user doesn't see a stray output-1.txt next to the rendered
            # widget.
            self._widget_pipeline_active = True
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
        # Unwrap widget JSON: if the model passed `{"title":"...","widget_code":"..."}`
        # as content (it does this when it wants both render + download), extract
        # the inner widget_code, sniff its type, and save THAT as the file. The
        # raw JSON envelope is just a chat-rendering wrapper — saving it produces
        # an unpreviewable .txt file with escaped HTML inside.
        try:
            stripped = (content or "").lstrip()
            if stripped.startswith("{") and '"widget_code"' in stripped[:500]:
                parsed = json.loads(stripped)
                inner = parsed.get("widget_code")
                if isinstance(inner, str) and inner.strip():
                    content = inner
                    # Re-derive extension from the inner content
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
                        # If the model named it foo.txt, rename to foo.html / foo.svg
                        from pathlib import Path as _P
                        base = _P(filename or "output").stem or "output"
                        filename = base + new_ext
                        if new_ext == ".html":
                            mime = "text/html"
                        elif new_ext == ".svg":
                            mime = "image/svg+xml"
                    # If it's a bare SVG, wrap in a tiny HTML harness so it
                    # opens nicely in the browser preview.
                    if new_ext == ".svg":
                        # keep raw SVG — browsers preview SVG natively
                        pass
                    elif new_ext == ".html" and "<!doctype" not in sniff and "<html" not in sniff:
                        content = (
                            "<!DOCTYPE html><html><head><meta charset='utf-8'>"
                            "<title>" + (parsed.get("title") or "widget") + "</title>"
                            "</head><body style='margin:0'>" + content + "</body></html>"
                        )
                    # Reorder scripts: move every <script>...</script> to
                    # just before </body>. The widget iframe receiver does
                    # this implicitly (DOM first, scripts appended last).
                    # Without reordering, models that put a <script> at the
                    # top of the body (typical pattern) will fail in a saved
                    # standalone file because onclick="foo()" handlers fire
                    # before `foo` is defined OR `let`/`const` vars are in TDZ.
                    if new_ext == ".html":
                        content = _move_scripts_to_end(content)
        except (json.JSONDecodeError, KeyError, TypeError):
            pass  # fall through to normal save

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

    async def exec_ui_action(self, tool: str, params: dict[str, Any]) -> AsyncIterator[StreamEvent]:
        """Execute a single tool call directly (no LLM), used for [UI_ACTION] routing.

        Streams tool_use → tool_result/ui → done. Cheap: no model tokens spent.
        Caller MUST validate `tool` against the agent's whitelist before calling.
        """
        import json as _json
        import time as _t
        start = _t.time()
        if self.ctx.model:
            yield StreamEvent("meta", {
                "agent_name": self.ctx.agent.name,
                "agent_code": self.ctx.agent.code,
                "model_code": self.ctx.model.code,
                "model_id": self.ctx.model.model_id,
                "provider": self.ctx.model.provider,
                "ui_action": True,
            })
        call_id = f"ui_{int(_t.time()*1000)}"
        yield StreamEvent("tool_use", {"id": call_id, "name": tool, "input": params})
        try:
            # Resolve MCP tool first (UI may target an MCP-exposed tool)
            mcp_match = None
            for m in self.ctx.mcps:
                # Names like mcp__<server>__<raw>
                if tool.startswith(f"mcp__{m.name}__"):
                    raw = tool[len(f"mcp__{m.name}__"):]
                    mcp_match = (m, raw)
                    break
            if mcp_match:
                m, raw = mcp_match
                result = await self._call_mcp_tool_once(m, raw, params)
            else:
                result = await self._exec_skill(tool, params)
        except Exception as e:  # noqa: BLE001
            result = {"error": str(e)}

        from ..ui_schema.types import extract_ui_schema, strip_ui_for_model
        ui_schema = extract_ui_schema(result, tool_name=tool)
        if ui_schema:
            yield StreamEvent("ui", ui_schema)
            self._saved_ui.append(ui_schema)
            result = strip_ui_for_model(result)
        yield StreamEvent("tool_result", {"tool_use_id": call_id, "content": _json.dumps(result, ensure_ascii=False, default=str)})
        # Surface any saved files registered during execution
        for f in self._saved_files:
            yield StreamEvent("file", f)
        yield StreamEvent("done", {
            "tokens_in": 0, "tokens_out": 0,
            "latency_ms": int((_t.time() - start) * 1000),
            "ui_action": True,
        })

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

        system = self._system_prompt(user_text) or "You are a helpful assistant."
        prompt = user_text
        if files:
            prompt += self._render_attachments(files)

        tools = self._build_openai_tools(user_text)
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        # Replay prior turns so the model has conversation context
        for h in (self.ctx.history or []):
            text = (h.content_json or {}).get("text") if isinstance(h.content_json, dict) else None
            if not text:
                continue
            messages.append({"role": h.role, "content": text})
        messages.append({"role": "user", "content": prompt})

        # ---- MCP integration: short-lived connections only ----
        # Long-lived sessions held across an async generator's lifetime trigger
        # anyio cancel-scope errors when FastAPI streams switch tasks. So we:
        # 1) Connect once up front *just* to enumerate tools, then disconnect.
        # 2) On each tool call, open a fresh connection, call, close.
        # Connect+close are always in the same task, no scope leakage.
        mcp_tool_routes: dict[str, tuple[str, "MCPConnector"]] = {}  # exposed -> (raw_tool, mcp row)
        for mcp in self.ctx.mcps:
            try:
                tools_list = await self._list_mcp_tools_once(mcp)
                for t in tools_list:
                    exposed = self._mcp_tool_name(mcp.name, t["name"])
                    mcp_tool_routes[exposed] = (t["name"], mcp)
                    tools.append({
                        "type": "function",
                        "function": {
                            "name": exposed,
                            "description": f"[MCP:{mcp.name}] {t.get('description') or t['name']}",
                            "parameters": t.get("input_schema") or {"type": "object"},
                        },
                    })
            except Exception as e:  # noqa: BLE001
                # Silently skip a broken MCP — don't pollute the user-facing transcript.
                # The model just won't see this server's tools this turn.
                import logging as _lg
                _lg.getLogger(__name__).warning(
                    "MCP %s tool enumeration failed: %s", mcp.name, e
                )

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
                            raw_tool, mcp_row = mcp_tool_routes[slot["name"]]
                            result = await self._call_mcp_tool_once(mcp_row, raw_tool, args)
                        else:
                            result = await self._exec_skill(slot["name"], args)
                    except Exception as e:  # noqa: BLE001
                        result = {"error": str(e)}
                    # If the tool result carries a UI Schema, surface it directly to the
                    # frontend ComponentRegistry. The model still sees a small summary
                    # so it knows a UI was rendered; we don't feed back the whole schema.
                    from ..ui_schema.types import extract_ui_schema, strip_ui_for_model
                    ui_schema = extract_ui_schema(result, tool_name=slot["name"])
                    if ui_schema:
                        yield StreamEvent("ui", ui_schema)
                        self._saved_ui.append(ui_schema)
                        result = strip_ui_for_model(result)
                    result_str = _json.dumps(result, ensure_ascii=False, default=str)
                    yield StreamEvent("tool_result", {"tool_use_id": slot["id"], "content": result_str})
                    messages.append({
                        "role": "tool", "tool_call_id": slot["id"],
                        "content": result_str,
                    })

        yield StreamEvent("error", {"message": f"工具调用循环超过 {MAX_ITER} 轮,已强制中断"})

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


    @staticmethod
    async def _with_mcp_session(mcp, fn):
        """Open + initialize an MCP session, run `fn(session)`, close. All in one task.

        Avoids the anyio "cancel scope in different task" error that occurs when an
        AsyncExitStack is held across an async generator's lifetime in FastAPI streams.
        """
        from contextlib import AsyncExitStack
        from mcp import ClientSession
        cfg = mcp.config_json or {}
        async with AsyncExitStack() as stack:
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
            return await fn(session)

    @classmethod
    async def _list_mcp_tools_once(cls, mcp) -> list[dict[str, Any]]:
        """One-shot: connect, list tools, disconnect."""
        async def _do(session):
            tools_resp = await session.list_tools()
            return [
                {
                    "name": t.name,
                    "description": t.description or "",
                    "input_schema": getattr(t, "inputSchema", None) or {},
                }
                for t in tools_resp.tools
            ]
        return await cls._with_mcp_session(mcp, _do)

    @classmethod
    async def _call_mcp_tool_once(cls, mcp, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        """One-shot: connect, call tool, disconnect."""
        # Drop the OpenAI-style {"input": {...}} wrapper if the model added one
        call_args = args.get("input") if isinstance(args, dict) and "input" in args and len(args) == 1 else args
        if not isinstance(call_args, dict):
            call_args = {"value": call_args}

        async def _do(session):
            import json as _json
            result = await session.call_tool(tool_name, call_args)
            out_parts: list[str] = []
            for c in (result.content or []):
                text = getattr(c, "text", None)
                if text is not None:
                    out_parts.append(text)
                else:
                    out_parts.append(str(c))
            content_str = "\n".join(out_parts)
            wrapped: dict[str, Any] = {
                "isError": bool(getattr(result, "isError", False)),
                "content": content_str,
            }
            # If the tool returned JSON whose top-level dict contains __ui__,
            # lift the schema (and surface fields) so the runtime's
            # extract_ui_schema() sees it. Tools may return JSON or plain text.
            stripped = content_str.strip()
            if stripped.startswith("{") and stripped.endswith("}"):
                try:
                    parsed = _json.loads(stripped)
                    if isinstance(parsed, dict):
                        if "__ui__" in parsed:
                            ui = parsed["__ui__"]
                            # Auto-prefix bare tool names in actions with mcp__<server>__
                            # so the [UI_ACTION] route resolves to THIS server, not a
                            # same-named tool from another MCP / Skill.
                            if isinstance(ui, dict):
                                _prefix_mcp_actions(ui, mcp.name)
                            wrapped["__ui__"] = ui
                        wrapped["data"] = {k: v for k, v in parsed.items() if k != "__ui__"}
                except Exception:
                    pass
            return wrapped
        return await cls._with_mcp_session(mcp, _do)


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
            "system_prompt": self._system_prompt(user_text),
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
