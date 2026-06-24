"""Tiny cron (5-field) + once schedule resolver.

We avoid pulling in croniter/apscheduler to keep the dep tree light. The
cron support handles:
  - exact numbers:        e.g. "0"
  - lists:                e.g. "1,15,30"
  - ranges:               e.g. "9-17"
  - step values:          e.g. "*/5"
  - wildcards:            "*"

Fields, in order: minute(0-59) hour(0-23) day-of-month(1-31) month(1-12) day-of-week(0-6, 0=Sun)

`once` schedule uses ISO datetime in the given timezone. Returns None if the
moment has already passed (one-shot won't refire).
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone as _tz
from zoneinfo import ZoneInfo


def _parse_field(expr: str, lo: int, hi: int) -> set[int]:
    out: set[int] = set()
    for part in expr.split(","):
        part = part.strip()
        if not part:
            continue
        step = 1
        if "/" in part:
            base, step_s = part.split("/", 1)
            step = max(1, int(step_s))
        else:
            base = part
        if base == "*" or base == "":
            r_lo, r_hi = lo, hi
        elif "-" in base:
            a, b = base.split("-", 1)
            r_lo, r_hi = int(a), int(b)
        else:
            v = int(base)
            r_lo = r_hi = v
        for v in range(r_lo, r_hi + 1, step):
            if lo <= v <= hi:
                out.add(v)
    return out


def _parse_cron(expr: str) -> tuple[set[int], set[int], set[int], set[int], set[int]]:
    fields = expr.strip().split()
    if len(fields) != 5:
        raise ValueError(f"cron 表达式必须是 5 段（分 时 日 月 周）：{expr!r}")
    return (
        _parse_field(fields[0], 0, 59),
        _parse_field(fields[1], 0, 23),
        _parse_field(fields[2], 1, 31),
        _parse_field(fields[3], 1, 12),
        _parse_field(fields[4], 0, 6),
    )


def _next_cron_fire(expr: str, tz_name: str, *, after: datetime | None = None) -> datetime:
    minutes, hours, doms, months, dows = _parse_cron(expr)
    try:
        tz = ZoneInfo(tz_name) if tz_name else ZoneInfo("Asia/Shanghai")
    except Exception:
        tz = ZoneInfo("Asia/Shanghai")
    now = (after or datetime.now(_tz.utc)).astimezone(tz)
    # Start from the next minute (avoid racing the same minute we were scheduled in)
    cand = (now.replace(second=0, microsecond=0) + timedelta(minutes=1))
    # Hard cap search at ~4 years for sanity
    end = cand + timedelta(days=4 * 366)
    while cand < end:
        if (cand.minute in minutes
                and cand.hour in hours
                and cand.month in months
                and cand.day in doms
                and (cand.weekday() + 1) % 7 in dows):  # weekday: Mon=0, our DOW: Sun=0
            return cand
        cand += timedelta(minutes=1)
    raise ValueError("找不到下一个匹配时间")


def next_fire_time(schedule_type: str, schedule_value: str, tz_name: str) -> float | None:
    """Return seconds-from-now until the next fire. None if one-shot already passed."""
    if schedule_type == "cron":
        nxt = _next_cron_fire(schedule_value, tz_name)
        return max(0.0, (nxt - datetime.now(nxt.tzinfo)).total_seconds())
    if schedule_type == "once":
        # parse ISO datetime in local tz if no offset present
        try:
            dt = datetime.fromisoformat(schedule_value)
        except ValueError:
            raise ValueError(f"once 时间格式应为 ISO，例如 2026-05-12T09:30:00：{schedule_value!r}")
        try:
            tz = ZoneInfo(tz_name) if tz_name else ZoneInfo("Asia/Shanghai")
        except Exception:
            tz = ZoneInfo("Asia/Shanghai")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        delta = (dt - datetime.now(dt.tzinfo)).total_seconds()
        return None if delta <= 0 else delta
    raise ValueError(f"unsupported schedule_type: {schedule_type}")
