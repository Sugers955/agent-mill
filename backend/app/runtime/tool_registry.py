"""Tool definition builders for OpenAI function-calling.

Extracted from agent_runner.py — pure data assembly with no I/O.
"""
from __future__ import annotations
from typing import Any

from .widget_guidelines import WIDGET_TOOL_DEFINITION


def build_openai_tools(
    skills: list,
    packs: list | None = None,
) -> list[dict[str, Any]]:
    """构建 OpenAI function-calling 工具列表。"""
    tools: list[dict[str, Any]] = []
    for s in skills:
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
    if any(s.type == "atomic" and (s.source_json or {}).get("path") for s in skills):
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
    # Universal output-file save tool
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
    if any(s.type == "atomic" and (s.source_json or {}).get("path") for s in skills):
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
    # Solution Packs
    for p in (packs or []):
        spec = p.spec_json or {}
        in_props = {}
        required = []
        for k, cfg in (spec.get("inputs") or {}).items():
            typ = (cfg or {}).get("type") or "string"
            json_type = {
                "string": "string", "number": "number", "boolean": "boolean",
                "list": "array", "object": "object", "daterange": "string",
            }.get(typ, "string")
            desc = (cfg or {}).get("description") or k
            in_props[k] = {"type": json_type, "description": desc}
            if (cfg or {}).get("required"):
                required.append(k)
        tools.append({
            "type": "function",
            "function": {
                "name": f"run_pack__{p.code}",
                "description": (
                    f"执行方案包『{p.name}』。{p.description or ''} "
                    "适用于需要完整业务流程编排的场景,比单个 Skill 更适合。"
                ).strip(),
                "parameters": {
                    "type": "object",
                    "properties": in_props,
                    "required": required,
                },
            },
        })
    # Generative-UI widget guidelines loader
    tools.append(WIDGET_TOOL_DEFINITION)

    # Built-in user-interaction tools
    tools.append({
        "type": "function",
        "function": {
            "name": "ask_user_pick",
            "description": (
                "向用户弹一个可点选的选项卡片列表，让用户从若干候选里挑一个（或多个）。"
                "用户点击后，前端会把用户的选择以普通用户消息的形式提交给你（消息已模板化），"
                "你在下一轮看到结果后再决定如何继续。"
                "适用于『你找到了多个候选，需要用户挑一个再继续推理』的场景。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "卡片列表的标题，例如 '请选择城市'"},
                    "question": {"type": "string", "description": "可选，给用户的提示文案"},
                    "options": {
                        "type": "array",
                        "description": "候选项数组",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string", "description": "显示在卡片上的主标题"},
                                "value": {"description": "选项的内部值（任意类型，原样回传给你）"},
                                "description": {"type": "string", "description": "卡片副标题/简短说明"},
                            },
                            "required": ["label"],
                        },
                    },
                    "multi_select": {
                        "type": "boolean",
                        "description": "是否允许多选；默认 false",
                    },
                    "follow_up_template": {
                        "type": "string",
                        "description": (
                            "用户点击后回传给你的消息模板，支持 {{label}} {{value}} 占位符。"
                            "缺省为 '我选「{{label}}」'。"
                        ),
                    },
                },
                "required": ["title", "options"],
            },
        },
    })
    tools.append({
        "type": "function",
        "function": {
            "name": "ask_user_form",
            "description": (
                "向用户弹出一个表单，让用户填若干字段后提交。"
                "用户提交后，前端会把表单内容以普通用户消息的形式提交给你（消息已模板化），"
                "你在下一轮看到结果后再决定如何继续。"
                "适用于『需要用户先补充几条结构化信息才能继续』的场景。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "表单标题"},
                    "fields": {
                        "type": "array",
                        "description": "字段定义",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string", "description": "字段名（提交时用作 key）"},
                                "label": {"type": "string", "description": "字段显示名"},
                                "type": {
                                    "type": "string",
                                    "description": "Input / Textarea / InputNumber / Select / DatePicker / Radio / Checkbox",
                                },
                                "required": {"type": "boolean"},
                                "placeholder": {"type": "string"},
                                "default": {"description": "缺省值"},
                                "options": {
                                    "type": "array",
                                    "description": "Select / Radio / Checkbox 的选项 [{label,value}]",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "label": {"type": "string"},
                                            "value": {},
                                        },
                                    },
                                },
                            },
                            "required": ["id", "label", "type"],
                        },
                    },
                    "submit_label": {"type": "string", "description": "提交按钮文案，默认 '提交'"},
                    "follow_up_template": {
                        "type": "string",
                        "description": (
                            "表单提交后回传给你的消息模板。支持 {{字段名}} 占位符；"
                            "若不提供，前端会把整个表单 JSON 序列化后回传。"
                        ),
                    },
                },
                "required": ["title", "fields"],
            },
        },
    })
    return tools


def build_ask_user_pick(args: dict[str, Any]) -> dict[str, Any]:
    """构建 CardList UI Schema。"""
    title = str(args.get("title") or "请选择")
    question = args.get("question")
    options = args.get("options") or []
    if not isinstance(options, list) or not options:
        return {"error": "ask_user_pick: options 不能为空"}
    multi = bool(args.get("multi_select"))
    if multi:
        return build_ask_user_form({
            "title": title,
            "fields": [{
                "id": "selected",
                "label": question or title,
                "type": "Checkbox",
                "required": True,
                "options": [{"label": str(o.get("label", "")), "value": o.get("value", o.get("label"))}
                            for o in options if isinstance(o, dict)],
            }],
            "follow_up_template": str(args.get("follow_up_template") or "我选了：{{selected}}"),
            "submit_label": "提交",
        })

    items = []
    for i, o in enumerate(options):
        if not isinstance(o, dict):
            continue
        items.append({
            "id": str(o.get("value", i)),
            "title": str(o.get("label", "")),
            "subtitle": str(o.get("description") or ""),
            "_label": str(o.get("label", "")),
            "_value": o.get("value", o.get("label", "")),
        })

    tpl = str(args.get("follow_up_template") or "用户通过 ask_user_pick 选择了「{{label}}」（value={{value}}），请基于此继续。")
    ui = {
        "message_type": "ui",
        "component_type": "CardList",
        "title": title,
        "data_model": {"items": items, "total": len(items)},
        "actions": [{
            "name": "pick",
            "label": "选择",
            "trigger": "card_click",
            "agent_call": True,
            "submit_as": "message",
            "params_from": "/items/{index}",
            "params_map": {"label": "/_label", "value": "/_value"},
            "message_template": tpl,
        }],
    }
    return {"__ui__": ui, "__halt__": True, "ok": True,
            "note": "已展示选项卡片，等待用户选择后再继续；本轮到此为止。"}


def build_ask_user_form(args: dict[str, Any]) -> dict[str, Any]:
    """构建 DynamicForm UI Schema。"""
    title = str(args.get("title") or "请填写")
    fields = args.get("fields") or []
    if not isinstance(fields, list) or not fields:
        return {"error": "ask_user_form: fields 不能为空"}
    components = []
    defaults: dict[str, Any] = {}
    for f in fields:
        if not isinstance(f, dict) or not f.get("id"):
            continue
        fid = str(f["id"])
        ftype = str(f.get("type") or "Input")
        props: dict[str, Any] = {
            "label": f.get("label") or fid,
            "required": bool(f.get("required")),
        }
        if f.get("placeholder"):
            props["placeholder"] = f.get("placeholder")
        if f.get("options"):
            props["options"] = f.get("options")
        components.append({"id": fid, "type": ftype, "props": props})
        if "default" in f:
            defaults[fid] = f["default"]

    tpl = args.get("follow_up_template")
    if not tpl:
        placeholders = "\n".join(f"- {c['id']}={{{{{c['id']}}}}}" for c in components)
        tpl = (
            "用户已通过 ask_user_form 表单提交了以下内容，请基于这些字段继续完成上一步说要做的任务（不要再次让用户填表单）：\n"
            + placeholders
        )
    submit_label = str(args.get("submit_label") or "提交")

    ui = {
        "message_type": "ui",
        "component_type": "DynamicForm",
        "title": title,
        "data_model": defaults,
        "components": components,
        "actions": [{
            "name": "submit",
            "label": submit_label,
            "trigger": "form_submit",
            "agent_call": True,
            "submit_as": "message",
            "params_from": "/",
            "message_template": tpl,
            "style": "primary",
        }],
    }
    return {"__ui__": ui, "__halt__": True, "ok": True,
            "note": "已展示表单，等待用户提交后再继续；本轮到此为止。"}
