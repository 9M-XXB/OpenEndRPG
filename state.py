# -*- coding: utf-8 -*-
"""完全开放式RPG · 存档与世界状态账本
"叙事归LLM、状态归函数": 所有状态变更由本模块的确定性代码合并 (song-2024 范式)。
本文由 ZCode (GLM-5.3-Flash) 编写。
"""

import copy
import json
import os
import time
from datetime import datetime

from prompts import PERIODS

SAVE_VERSION = 1


class SaveError(Exception):
    pass


def new_save(name: str, hero: str) -> dict:
    from prompts import OPENING_STATE, OPENING_SLIDE
    now = datetime.now().isoformat(timespec="seconds")
    return {
        "version": SAVE_VERSION,
        "name": name,
        "hero": hero or "勇者",
        "created_at": now,
        "updated_at": now,
        "turn": 0,
        "state": copy.deepcopy(OPENING_STATE),
        "summary": OPENING_STATE["summary"],
        "history": [],
        "dice_log": [],
        "stage": [copy.deepcopy(OPENING_SLIDE)],
        "provider": {},
    }


def saves_dir() -> str:
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saves")
    os.makedirs(d, exist_ok=True)
    return d


def save_path(name: str) -> str:
    safe = "".join(c for c in name if c not in '\\/:*?"<>|').strip()
    if not safe:
        raise SaveError("存档名不能为空")
    return os.path.join(saves_dir(), safe + ".json")


def save_game(save: dict) -> str:
    save["updated_at"] = datetime.now().isoformat(timespec="seconds")
    p = save_path(save["name"])
    with open(p, "w", encoding="utf-8") as f:
        json.dump(save, f, ensure_ascii=False, indent=1)
    return p


def load_save(name: str) -> dict:
    p = save_path(name)
    if not os.path.exists(p):
        raise SaveError(f"存档不存在: {name}")
    with open(p, encoding="utf-8") as f:
        save = json.load(f)
    if not isinstance(save.get("state"), dict):
        raise SaveError(f"存档损坏: {name}")
    return save


def list_saves() -> list[dict]:
    out = []
    d = saves_dir()
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(d, fn), encoding="utf-8") as f:
                s = json.load(f)
            out.append({
                "name": s.get("name", fn[:-5]),
                "day": s.get("state", {}).get("day", "?"),
                "turn": s.get("turn", 0),
                "updated_at": s.get("updated_at", "?"),
            })
        except (json.JSONDecodeError, OSError):
            out.append({"name": fn[:-5], "day": "?", "turn": "?", "updated_at": "损坏"})
    return sorted(out, key=lambda x: str(x["updated_at"]), reverse=True)


def delete_save(name: str) -> bool:
    p = save_path(name)
    if os.path.exists(p):
        os.remove(p)
        return True
    return False


# ---------- 时间推进 ----------

def advance_time(state: dict, days: int, period: str) -> tuple[int, str]:
    """按 LLM 给出的增量推进时间; 返回 (旧标签, 新标签)。非法值按同日推进处理。"""
    old = f"第{state['day']}天·{state['period']}"
    period = period if period in PERIODS else state["period"]
    try:
        days = max(0, int(days))
    except (TypeError, ValueError):
        days = 0
    if days == 0:
        if PERIODS.index(period) > PERIODS.index(state["period"]):
            state["period"] = period
        else:  # 回到更早时段 => 视为次日
            state["day"] += 1
            state["period"] = period
    else:
        state["day"] += days
        state["period"] = period
    return old, f"第{state['day']}天·{state['period']}"


# ---------- 状态增量合并 (确定性代码, 不经 LLM) ----------

def _as_str_list(v) -> list[str]:
    if not isinstance(v, list):
        return []
    return [str(x).strip() for x in v if str(x).strip()]


def apply_delta(save: dict, delta: dict) -> dict:
    """把 LLM 的 state_updates 合并进世界账本; 返回人类可读的变更清单。"""
    state = save["state"]
    changes = {"facts+": 0, "facts-": 0, "npcs": [], "items+": 0, "location": None}
    if not isinstance(delta, dict):
        return changes

    facts_add = _as_str_list(delta.get("facts_add"))
    for f in facts_add:
        if f not in state["facts"]:
            state["facts"].append(f)
            changes["facts+"] += 1

    for target in _as_str_list(delta.get("facts_remove")):
        before = len(state["facts"])
        state["facts"] = [f for f in state["facts"] if target not in f and f not in target]
        changes["facts-"] += before - len(state["facts"])

    upserts = delta.get("npc_upserts")
    if isinstance(upserts, list):
        for u in upserts:
            if not isinstance(u, dict):
                continue
            name = str(u.get("name", "")).strip()
            if not name:
                continue
            npc = state["npcs"].setdefault(
                name, {"status": "", "relation": "", "location": "", "notes": []}
            )
            for k in ("status", "relation", "location"):
                v = str(u.get(k) or "").strip()
                if v:
                    npc[k] = v
            note = str(u.get("note") or "").strip()
            if note:
                npc.setdefault("notes", []).append(note)
                del npc["notes"][:-8]  # 每个 NPC 只留最近8条(重逢记忆)
            # NPC 常驻: 记录本次见面时间与累计次数 (规划.md §7)
            npc["last_met"] = {"day": state["day"], "period": state["period"]}
            npc["met_count"] = int(npc.get("met_count", 0)) + 1
            changes["npcs"].append(name)

    for it in _as_str_list(delta.get("items_add")):
        if it not in state["items"]:
            state["items"].append(it)
            changes["items+"] += 1

    loc = str(delta.get("location") or "").strip()
    if loc:
        state["location"] = loc
        changes["location"] = loc
    return changes


def record_turn(save: dict, player: str, dice: dict, narrative: str,
                suggestions: list[str], old_time: str, slides: list | None = None) -> None:
    save["turn"] = save.get("turn", 0) + 1
    save["history"].append({
        "turn": save["turn"],
        "day": save["state"]["day"],
        "period": save["state"]["period"],
        "player": player,
        "dice": dice.get("roll"),
        "narrative": narrative,
        "slides": slides or [],
        "suggestions": suggestions,
    })
    save.setdefault("dice_log", []).append(
        {"turn": save["turn"], "roll": dice.get("roll"), "label": dice.get("label")}
    )
    del save["dice_log"][:-50]
    save.setdefault("meta_times", []).append(old_time)
    del save["meta_times"][:-20]
