"""Prompt building utilities extracted from agent_runner.py.

This module contains constants and helper functions used to construct
system prompts and render attachments for the LLM.
"""
from __future__ import annotations
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..db.models import Skill

# Widget guidance — Skills take priority. Only injected when the user is
# asking for a visualization AND the agent has no skills loaded that might
# already handle it (e.g. `jiagoutu`). When skills are present, the model
# follows the skill's own SKILL.md instructions; widgets are the fallback
# path for agents that have no drawing skill configured.
_WIDGET_GUIDANCE = """
## 可视化输出指引（在没有更合适的 Skill 时使用）

当用户请求可视化（可视化 / 流程图 / 架构图 / 示意图 / SVG / 图表 / HTML / 网页 / 表单），
且你**没有更合适的 Skill** 来完成此任务时，且判断用户该任务的的预期答案是否更合适用可视化展示更清晰，更容易让人理解，上述这些情况下请使用 `show-widget` 围栏在聊天里直接渲染：

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
    "解释下","说明下","讲解下","分析下",
)


def wants_widget(text: str) -> bool:
    if not text:
        return False
    low = text.lower()
    return any(k.lower() in low for k in _VIZ_KEYWORDS_GENERAL + _VIZ_KEYWORDS_HTML)


# Short hint describing the two built-in user-interaction tools so the model
# knows they exist. The tool schemas carry the full description; this block
# exists so the model reaches for them at the right time.
_USER_INTERACTION_GUIDANCE = """
## 需要用户参与决策时或者需要澄清一些需求（重要 · 强制规则）

`ask_user_pick` 和 `ask_user_form` 是平台**内置的用户交互工具**，**不是 Skill 也不是业务工具**。
即便用户说"不要使用 Skill / 不要使用工具"，你**仍然必须**调用这两个内置工具来向用户收集信息——
它们只是把"问问题"换成更友好的卡片/表单 UI，本质上等同于你"开口提问"，不属于 skill 范畴。

### 强制触发规则
- 需要用户从 ≥2 个候选里挑选 → **必须**调用 `ask_user_pick`；**禁止**让用户回复数字或文字。
- 需要用户补充 ≥2 个结构化字段（如：场景 / 目标用户 / 覆盖范围）才能继续 → **必须**调用
  `ask_user_form`；**禁止**用 Markdown 表格、有序列表或文字罗列问题让用户挨个回答。
- 只问 1 个简单字段时（如"您叫什么名字"），可以用文字问，不必动用工具。

### 调用后的行为
工具调用本身就是这一轮的输出。调用完**立即停止说话**（不要在 tool_call 之后继续追问文字）。
等用户在 UI 上提交，你会收到一条经过模板渲染的用户消息（包含字段值），再基于此继续推理。

### 反例（绝对不要这样做）
> 「在开始编写前，请先告诉我以下几个关键信息：
> | 问题 | 您的答案 |
> | --- | --- |
> | 应用场景 | … |
> | 目标用户 | … |」
（出现这种"列若干问题让用户回填"的形态时，**应当改为调用 `ask_user_form`**）

### 正例
调用 `ask_user_form(title="政务智能体方案 · 基础信息", fields=[
  {"id":"scenario", "label":"应用场景", "type":"Textarea", "required":true,
   "placeholder":"如：面向市民的社保咨询服务"},
  {"id":"target_user", "label":"目标用户", "type":"Input", "required":true},
  {"id":"scope", "label":"覆盖范围", "type":"Input"},
  {"id":"pain_point", "label":"核心痛点", "type":"Textarea"},
])`
"""

# Effort level → per-provider tuning.
# Canonical levels: low / medium / high / xhigh / max.
# For Anthropic (Claude Agent SDK): mapped to extended-thinking token budget.
# For OpenAI-compatible providers: mapped to `reasoning_effort`.
EFFORT_THINKING_BUDGET: dict[str, int] = {
    "low": 2000,
    "medium": 8000,
    "high": 16000,
    "xhigh": 32000,
    "max": 64000,
}

EFFORT_OPENAI_REASONING: dict[str, str] = {
    "low": "low",
    "medium": "medium",
    "high": "high",
    "xhigh": "high",
    "max": "high",
}


def effort_to_thinking_budget(effort: str) -> int | None:
    return EFFORT_THINKING_BUDGET.get((effort or "medium").lower())


def effort_to_openai_reasoning(effort: str) -> str | None:
    return EFFORT_OPENAI_REASONING.get((effort or "medium").lower())


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


def agent_has_drawing_skill(skills: list[Skill]) -> bool:
    for s in skills or []:
        haystack = " ".join(filter(None, [s.code, s.name, s.description])).lower()
        if any(h.lower() in haystack for h in _DRAWING_SKILL_HINTS):
            return True
    return False


def build_system_prompt(
    agent: Any,
    skills: list[Skill],
    model: Any,
    user_text: str | None = None,
    has_files: bool = False,
    memory_context: str = "",
    knowledge_context: str = "",
) -> str:
    from ..core.security_rules import SAFETY_PREFIX
    # SAFETY_PREFIX is mandatory and comes first — per-agent prompts cannot weaken it.
    parts = [SAFETY_PREFIX]
    # Skills come first. We only inject the widget capability + guidance
    # when (1) the user is asking for a visualization AND (2) the agent
    # has no drawing-related Skill loaded. If a drawing Skill exists,
    # the model follows that Skill's own SKILL.md — widget is the
    # fallback path for skill-less agents.
    wants_viz = wants_widget(user_text or "")
    has_drawing_skill = agent_has_drawing_skill(skills)
    if wants_viz and not has_drawing_skill:
        from .widget_guidelines import WIDGET_SYSTEM_PROMPT
        parts.append(WIDGET_SYSTEM_PROMPT)
        parts.append(_WIDGET_GUIDANCE)
    if agent.system_prompt:
        parts.append(agent.system_prompt)
    # 记忆上下文
    if memory_context:
        parts.append(f"\n## 关于该用户的记忆\n\n{memory_context}")
    # 知识库上下文
    if knowledge_context:
        parts.append(f"\n## 知识库参考信息\n\n{knowledge_context}")
    if skills:
        parts.append("\n## 你可使用的 Skills\n")
        for s in skills:
            tag = "组合" if s.type == "composite" else "原子"
            parts.append(f"- **{s.code}** ({tag}): {s.description or '(无描述)'}")
    # Built-in user-interaction guidance — always available, low overhead.
    parts.append(_USER_INTERACTION_GUIDANCE)
    return "\n".join(parts).strip()


def render_attachments(
    files: list[dict[str, Any]],
    parsed_limit: int | None = None,
) -> str:
    """Render uploaded files as a structured attachment block for the model.

    Per-Agent length cap:
      * parsed_limit  — explicit override (None = use global)
      * settings.PARSED_MARKDOWN_HARD_LIMIT — global default
      * limit == 0  → no truncation (inject full markdown verbatim)
    """
    if not files:
        return ""
    from ..core.config import settings as _settings
    if parsed_limit is None:
        cap = int(_settings.PARSED_MARKDOWN_HARD_LIMIT or 0)
    else:
        cap = int(parsed_limit)
    sections: list[str] = []
    for f in files:
        name = f.get("name") or "file"
        status = f.get("parse_status") or "unknown"
        md = f.get("parsed_markdown")
        chars = len(md) if isinstance(md, str) else 0
        head = f"### 📎 {name}"
        if chars:
            head += f"  · {chars} 字符"
        if status == "skipped":
            # Raw passthrough: do not extract; expose path + signed URL so
            # the model can forward them to skill / MCP tools as arguments.
            lp = f.get("path") or ""
            # Resolve to an absolute path — UPLOADS_DIR can be relative
            # ("../storage/uploads"), which would be meaningless to MCP
            # tools running in a different cwd.
            if lp:
                from pathlib import Path as _P
                try:
                    lp = str(_P(lp).resolve())
                except Exception:
                    pass
            ru = f.get("raw_url") or ""
            mime = f.get("mime") or ""
            size = f.get("size") or 0
            parts = [f"{head}  · 原始文件直传 (mime={mime}, size={size}B)"]
            if ru:
                parts.append(f"- 下载 URL(**推荐**,MCP / 远程工具均可拉取): `{ru}`")
            if lp:
                parts.append(f"- 本地绝对路径(仅当工具与后端在同一文件系统时可用): `{lp}`")
            parts.append("- 调用工具时优先把 URL 作为参数;只有确认工具能直接读本地磁盘时才用 path。不要尝试在对话中读取该文件内容。")
            sections.append("\n".join(parts))
        elif status == "done" and md:
            from ..services.file_parser import clip_for_prompt as _clip
            body_md = _clip(md, cap)
            if cap > 0 and chars > cap:
                head += f" (按 Agent 配置截取至 {cap} 字符)"
            sections.append(f"{head}\n\n```\n{body_md}\n```")
        elif status == "parsing":
            sections.append(f"{head}\n\n(文件正在解析中,本轮无法读取内容)")
        elif status == "failed":
            err = f.get("parse_error") or "未知错误"
            sections.append(f"{head}\n\n(文件解析失败: {err})")
        else:
            sections.append(f"{head}\n\n(文件未解析,可向用户说明)")
    body = "\n\n".join(sections)
    return ("\n\n---\n\n# 用户上传的附件(已解析的文本可直接引用;标注为'原始文件直传'的需把 path/url 当作工具参数)\n\n"
            f"{body}\n\n---\n")