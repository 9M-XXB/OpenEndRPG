# -*- coding: utf-8 -*-
"""完全开放式RPG · 提示词与规则文案
依据: 调研笔记.md — song-2024(叙事归LLM/状态归函数), zhou-2023(两级记忆), wang-2023(自动课程式的建议铺垫)。
本文由 ZCode (GLM-5.3-Flash) 编写。
"""

import random

GAME_TITLE = "完全开放式RPG · 终端原型"

PERIODS = ["清晨", "上午", "下午", "傍晚", "夜晚"]

# 命运骰: d20 + 事件倾向表 (F5 随机性)
DICE_TABLE = [
    (1, 4, "意外挫折", "本回合安排一个出乎意料的挫折或阻力(可克服, 但要有真实代价)"),
    (5, 9, "平淡进展", "本回合按情理平稳推进, 穿插一个小的生活化细节"),
    (10, 14, "小机遇", "本回合出现一个对玩家有利的小机遇或有用信息"),
    (15, 19, "重要转机", "本回合发生一个显著改变局势的重要转机"),
    (20, 20, "命运大事件", "本回合发生一件震动局面的大事件(新势力/重大揭示/意外相遇)"),
]


def roll_dice() -> tuple[int, dict]:
    """掷 d20, 返回 (点数, 倾向dict{label, hint, min, max})"""
    n = random.randint(1, 20)
    for lo, hi, label, hint in DICE_TABLE:
        if lo <= n <= hi:
            return n, {"roll": n, "label": label, "hint": hint}
    return n, {"roll": n, "label": "?", "hint": ""}


def dice_line(d: dict) -> str:
    return f"命运骰 {d['roll']:2d} · {d['label']}"


SYSTEM_RULES = """你是文字冒险游戏的"游戏主持人"(GM)与世界的唯一运转者。玩家扮演{hero}。

【世界观】玩家正处于一个经典奇幻大陆的开端: 遥远的黑曜王座上有大魔王, 人间各国勉强维持着脆弱的和平。除此之外, 世界没有任何预设内容——城市、人物、组织、任务, 全部由你根据玩家的行动即时创造, 并保持前后一致。

【本回合铁律】
1. 你生成的剧情只覆盖"自上一幕结束起、一天以内"发生的事, 不许跳到更远的未来——除非玩家在本回合输入中明确要求跳过时间(如"三天后"), 此时才允许 time_advance.days>1。
2. 剧情必须与世界账本、剧情摘要、最近剧情完全连续: 已死角色不能复活(除非有合理剧情), 已定事实不得无端推翻。
3. 你必须遵循本回合"命运骰"的倾向安排走向(见用户消息末尾), 但骰只定"调性", 不替你写字。
4. 对玩家输入的所有合理行动都要给出后果; 后果要有因果与逻辑, 重要转折要有铺垫。
5. 不要替玩家决定其未声明的主观意图(想什么/感受什么), 只描述世界与他人对其行动的反应。
6. summary 必须在上一段摘要基础上增量更新(150字内), 保留关键因果链、人物关系变化、未决伏笔。

【输出格式】只输出一个合法 JSON 对象(不要 markdown 代码块、不要多余文字), 字段如下:
{{
  "narrative": "本回合剧情, 2-5个自然段, 中文, 生动但不冗长",
  "time_advance": {{"days": 0, "period": "上午"}},
  "state_updates": {{
    "facts_add": ["新确立的世界事实, 每条一句"],
    "facts_remove": ["要移除的旧事实(须与账本原文一致或为其片段)"],
    "npc_upserts": [{{"name": "NPC名", "status": "现状一句话", "relation": "与主角的关系", "location": "所在地", "note": "本回合与主角相关变化"}}],
    "items_add": ["主角新获得的物品"],
    "location": "本回合结束时主角所在地点"
  }},
  "summary": "更新后的剧情滚动摘要",
  "suggestions": ["下一步建议1", "建议2", "建议3"]
}}
字段约束: time_advance.period 只能取 清晨/上午/下午/傍晚/夜晚 之一; days>=0, 未跨天为 0; npc_upserts 中同名 NPC 只出现一次, 首次登场的 NPC 四个字段都要给; suggestions 给 2-4 条, 是"铺垫下一步"的行动建议(以玩家口吻的动宾短语); 没有变化的书段给空数组。"""

OPENING_TEXT = """**序章 · 启程**

溪谷村坐落在王国东南的群山褶皱里, 已经七十年没听说过战事。七十年前的旧闻重新在灶台与井台间流传——黑曜王座上的大魔王苏醒了。北方商队带来烧成焦炭的界碑, 山那边逃来的难民说, 夜里的地平线会发出暗红色的光。

村长把一柄祖传的短剑放在你手里。剑身朴素, 剑格上刻着一个你叫不出名字的符文。"长老们商量过了, "老人声音发哑, "村里凑不出一支像样的队伍, 但总得有人去把消息带到王都, 或者……做点什么。"

今夜是出发前的最后一晚。行囊已收拾了一半, 母亲在灶间落泪, 门口的老猎户据说愿意教你几手野外保命的本事。天亮之后, 道路向北方延伸, 那里有魔王, 也有你从未见过的整个世界。

（你可以做任何事: 和任何人交谈、出发、练剑、睡觉、打听消息……直接输入即可。）"""

OPENING_STATE = {
    "day": 1,
    "period": "夜晚",
    "location": "溪谷村·家中",
    "facts": [
        "大魔王在黑曜王座苏醒, 北方边境已现魔兽与难民",
        "溪谷村是主角的家乡, 位于王国东南山区, 七十年无战事",
        "村长将祖传短剑交给主角, 剑格上有无人识得的符文",
        "主角计划北上: 先把消息带往王都, 再图魔王",
        "老猎户愿意教主角野外本领",
    ],
    "npcs": {
        "村长": {"status": "年迈忧心, 主张主角北上报信", "relation": "长辈, 信任主角", "location": "溪谷村",
                 "notes": ["将祖传短剑交付主角"]},
        "母亲": {"status": "在灶间落泪, 担心主角安危", "relation": "至亲", "location": "溪谷村·家中",
                 "notes": []},
        "老猎户": {"status": "愿意传授野外本领", "relation": "同村长辈, 未深交", "location": "溪谷村",
                  "notes": []},
    },
    "items": ["祖传短剑", "半收拾好的行囊"],
    "summary": "大魔王苏醒, 溪谷村决定让主角北上报信。村长交付刻有神秘符文的祖传短剑; 主角出发前夜: 行囊收拾一半, 母亲不舍, 老猎户愿传授野外本领。",
}

REPAIR_PROMPT = """你上一次的输出不是合法 JSON 或字段不符合要求。错误信息:
{error}

请重新输出: 只输出一个修复后的合法 JSON 对象, 严格遵守此前约定的字段与取值范围, 不要任何解释或代码块标记。"""


def world_digest(state) -> str:
    """世界账本摘要 (F6): 超长时裁剪, 保证上下文预算"""
    facts = state.get("facts", [])
    if len(facts) > 24:
        facts = facts[-24:]
    npc_lines = []
    for name, n in list(state.get("npcs", {}).items())[-12:]:
        notes = "; ".join(n.get("notes", [])[-2:]) if n.get("notes") else ""
        npc_lines.append(
            f"- {name}：{n.get('status','')}"
            + (f"（与主角:{n['relation']}）" if n.get("relation") else "")
            + (f"［在{n['location']}］" if n.get("location") else "")
            + (f" 近况:{notes}" if notes else "")
        )
    items = state.get("items", [])[-15:]
    return (
        f"第{state.get('day',1)}天·{state.get('period','清晨')}，主角位于：{state.get('location','未知')}\n"
        f"世界事实（账本）：\n" + "\n".join(f"- {f}" for f in facts) + "\n"
        + ("人物：\n" + "\n".join(npc_lines) + "\n" if npc_lines else "")
        + ("主角物品：" + "、".join(items) if items else "")
    )


def recent_turns_text(history, k=3, per_cap=1100) -> str:
    """最近 k 回合原文 (超长裁剪最旧)"""
    turns = history[-k:]
    blocks = []
    for t in turns:
        p = (t.get("player") or "")[:300]
        n = (t.get("narrative") or "")
        if len(n) > per_cap:
            n = n[: per_cap // 2] + "\n……（中略）……\n" + n[-per_cap // 2:]
        blocks.append(f"【玩家】{p}\n【剧情】{n}")
    return "\n———\n".join(blocks)


def build_turn_prompt(save, player_input: str, dice: dict) -> str:
    """组装每回合用户消息: 账本 + 摘要 + 近3回合 + 输入 + 骰"""
    parts = [
        "【世界账本（当前事实, 必须保持连续）】",
        world_digest(save["state"]),
        "",
        "【剧情滚动摘要（此前全部剧情的浓缩）】",
        save.get("summary") or "（开局）",
        "",
        "【最近剧情（最多近3回合原文）】",
        recent_turns_text(save.get("history", [])) or "（本回合是第一回合）",
        "",
        f"【玩家行动】{player_input}",
        "",
        f"【命运骰】点数 {dice['roll']}/20，倾向「{dice['label']}」：{dice['hint']}。请在走向上体现此倾向，但不要在文中提及骰子。",
        "",
        "现在请只输出约定的 JSON。",
    ]
    return "\n".join(parts)
