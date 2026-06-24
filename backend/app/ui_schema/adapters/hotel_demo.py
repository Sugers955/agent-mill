"""Demo Skill: a fake hotel search that emits a UI Schema.

Register it as an atomic.callable Skill in the admin panel:
  source_json: {"callable": "app.ui_schema.adapters.hotel_demo:search_hotels"}

The call returns a dict with `__ui__` payload that the runtime extracts and
emits as a `ui` SSE event for the frontend ComponentRegistry to render.
"""
from __future__ import annotations
from typing import Any
from ..types import make_surface_id


_FIXTURES = [
    {"id": "h001", "name": "北京君悦酒店", "price": 1288, "rating": 4.8,
     "tags": ["含早", "可免费取消", "近地铁"],
     "address": "北京市朝阳区建国门外大街 1 号",
     "image": "https://images.unsplash.com/photo-1455587734955-081b22074882?w=400"},
    {"id": "h002", "name": "上海外滩华尔道夫酒店", "price": 2188, "rating": 4.9,
     "tags": ["江景房", "含早", "豪华套房"],
     "address": "上海市黄浦区中山东一路 2 号",
     "image": "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?w=400"},
    {"id": "h003", "name": "杭州西湖国宾馆", "price": 1888, "rating": 4.7,
     "tags": ["园林", "湖景", "VIP 接待"],
     "address": "杭州市西湖区杨公堤 18 号",
     "image": "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=400"},
    {"id": "h004", "name": "成都瑞吉酒店", "price": 1488, "rating": 4.6,
     "tags": ["含早", "近春熙路", "免费 wifi"],
     "address": "成都市锦江区下东大街 88 号",
     "image": "https://images.unsplash.com/photo-1551882547-ff40c63fe5fa?w=400"},
]


def search_hotels(**kwargs) -> dict[str, Any]:
    """Look up hotels and return a CardList UI Schema."""
    city = (kwargs.get("city") or "").strip()
    items = [h for h in _FIXTURES if not city or city in h["name"] or city in h["address"]] or _FIXTURES
    schema = {
        "message_type": "ui",
        "surface_id": make_surface_id("hotel_search"),
        "component_type": "CardList",
        "title": f"为您找到 {len(items)} 家酒店" + (f" · {city}" if city else ""),
        "data_model": {"items": items, "total": len(items)},
        "filters": [
            {"field": "price", "label": "价格升序", "type": "sort", "agent_call": False},
            {"field": "rating", "label": "评分降序", "type": "sort", "agent_call": False},
        ],
        "actions": [
            {
                "name": "view_detail",
                "label": "查看详情",
                "trigger": "card_click",
                "agent_call": True,
                "tool": "get_hotel_detail",
                "params_from": "/items/{index}",
                "style": "default",
            },
            {
                "name": "book_now",
                "label": "立即预订",
                "trigger": "button_click",
                "agent_call": True,
                "tool": "init_booking",
                "params_from": "/items/{index}",
                "confirm": "确认预订该酒店?",
                "style": "primary",
            },
        ],
    }
    return {
        "city": city, "count": len(items),
        # The runtime extracts this and emits as a `ui` SSE event.
        # The model gets a small summary back, not the whole schema.
        "__ui__": schema,
    }


def get_hotel_detail(**kwargs) -> dict[str, Any]:
    """Show a confirm-style detail view for a single hotel."""
    item = kwargs.get("input") or kwargs
    name = item.get("name") or "酒店"
    price = item.get("price")
    rating = item.get("rating")
    tags = item.get("tags") or []
    schema = {
        "message_type": "ui",
        "surface_id": make_surface_id("hotel_detail"),
        "component_type": "ConfirmDialog",
        "title": f"{name} · 详情",
        "data_model": {
            "fields": [
                {"label": "酒店", "value": name},
                {"label": "价格", "value": f"¥ {price} / 晚" if price else "—"},
                {"label": "评分", "value": rating or "—"},
                {"label": "地址", "value": item.get("address") or "—"},
                {"label": "标签", "value": "、".join(tags) or "—"},
            ],
        },
        "actions": [
            {"name": "go_book", "label": "去预订", "trigger": "button_click",
             "agent_call": True, "tool": "init_booking",
             "params_from": "/_self", "style": "primary"},
        ],
    }
    return {"id": item.get("id"), "__ui__": schema}


def init_booking(**kwargs) -> dict[str, Any]:
    """Show a DynamicForm to collect booking info."""
    item = kwargs.get("input") or kwargs
    schema = {
        "message_type": "ui",
        "surface_id": make_surface_id("booking_form"),
        "component_type": "DynamicForm",
        "title": f"预订 · {item.get('name', '酒店')}",
        "data_model": {"hotel_id": item.get("id"), "hotel_name": item.get("name")},
        "components": [
            {"id": "guest_name", "type": "Input", "binds": "/guest_name",
             "props": {"label": "入住人", "placeholder": "中文姓名", "required": True}},
            {"id": "phone", "type": "Input", "binds": "/phone",
             "props": {"label": "联系电话", "placeholder": "11 位手机号", "required": True}},
            {"id": "checkin", "type": "DatePicker", "binds": "/checkin",
             "props": {"label": "入住日期", "required": True}},
            {"id": "nights", "type": "InputNumber", "binds": "/nights",
             "props": {"label": "入住天数", "min": 1, "max": 30, "default": 1}},
            {"id": "room_type", "type": "Select", "binds": "/room_type",
             "props": {"label": "房型",
                        "options": [{"label": "大床房", "value": "king"},
                                    {"label": "双床房", "value": "twin"},
                                    {"label": "套房", "value": "suite"}]}},
            {"id": "remark", "type": "Textarea", "binds": "/remark",
             "props": {"label": "备注", "rows": 3}},
        ],
        "actions": [
            {"name": "submit_booking", "label": "提交预订",
             "trigger": "form_submit", "agent_call": True,
             "tool": "confirm_booking", "params_from": "/", "style": "primary"},
        ],
    }
    return {"hotel_id": item.get("id"), "__ui__": schema}


def confirm_booking(**kwargs) -> dict[str, Any]:
    """Final step: show a status timeline."""
    info = kwargs.get("input") or kwargs
    schema = {
        "message_type": "ui",
        "surface_id": make_surface_id("booking_status"),
        "component_type": "StatusTimeline",
        "title": "预订进度",
        "data_model": {
            "steps": [
                {"title": "提交订单", "description": "已收到您的预订请求", "status": "done", "time": "刚刚"},
                {"title": "酒店确认", "description": "正在通知酒店确认房态", "status": "current", "time": "进行中"},
                {"title": "支付", "description": "等待酒店确认后通知支付", "status": "pending"},
                {"title": "出票", "description": "完成预订", "status": "pending"},
            ],
        },
    }
    return {"booking_id": "B" + str(abs(hash(str(info))) % 100000),
            "guest": info.get("guest_name"),
            "__ui__": schema}
