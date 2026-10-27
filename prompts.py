# -*- coding: utf-8 -*-
"""完全开放式RPG · 提示词与规则文案
依据: 调研笔记.md — song-2024(叙事归LLM/状态归函数), zhou-2023(两级记忆), wang-2023(自动课程式的建议铺垫)。
画面幻灯片: 规划.md — PPT式字画, 画布规格与组字法在【画面幻灯片】节教给运行时 LLM; 前端零图像元素。
本文由 ZCode (GLM-5.3-Flash) 编写。
"""

import json
import random

GAME_TITLE = "完全开放式RPG · 终端原型"

PERIODS = ["清晨", "上午", "下午", "傍晚", "夜晚"]

# ---------- 字画画布常量 (前端经 /api/state 读取同一来源, 勿在别处硬编码) ----------

CANVAS_W = 12
CANVAS_H = 6
TONES = ["暗", "明", "暖", "冷", "灰"]

FULL = "　"  # 全角空格 = 空白格


def pad_row(s: str) -> str:
    """画布行归一: 半角空格视为空白, 不足 W 补全角空格, 超出截断"""
    s = str(s).replace(" ", FULL)
    return s[:CANVAS_W] + FULL * max(0, CANVAS_W - len(s))


def canvas(*rows: str) -> list[str]:
    """按 W×H 规格生成画布行(不足补空行)"""
    rows = list(rows) + [""] * (CANVAS_H - len(rows))
    return [pad_row(r) for r in rows[:CANVAS_H]]


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


# ---------- 字画: 开场幻灯片(属"游戏本体提供的开头", README §2 种子范畴) ----------

OPENING_SLIDE = {
    "caption": "溪谷村·夜",
    "tone": "暗",
    "canvas": canvas(
        "",
        "　山　　　山　　山",
        "　　灯　　　　灯",
        "　　　一一一一",
        "　　　｜　　｜",
        "　我",
    ),
}

# 教学示例(注入 SYSTEM_RULES, 行宽由 canvas() 保证精确)
EXAMPLE_SLIDE = {
    "caption": "离村北行",
    "tone": "暗",
    "canvas": canvas(
        "",
        "　　　山　　山　　山",
        "",
        "　　　　　　一一一",
        "　　　　　　丨　丨",
        "　我",
    ),
}

_EXAMPLE_JSON = "\n".join("  " + ln for ln in
                          json.dumps(EXAMPLE_SLIDE, ensure_ascii=False, indent=1).splitlines())

# ---------- 画面幻灯片教学节: 教会运行时 LLM 生成画面 ----------

_SLIDES_RULES = """【画面幻灯片(与剧情同时输出, 你兼任画面导演)】
narrative 用文字叙述, slides 数组(0~3张)把其中最具画面性的瞬间定格成"字画": 每张画面是一个字符画布。文字与画面不得矛盾; 纯对话/心理活动的回合可为 0 张。

每张 slide 的格式:
{"caption": "画面小标题(10字内)", "tone": "暗|明|暖|冷|灰 之一", "canvas": ["第1行", "第2行", ... 共 {H} 行]}

画布规格(必须严格遵守):
1. canvas 共 {H} 行, 每行恰好 {W} 个字符; 每个字符(汉字/标点/「丨」「一」「┌」等)占一个格子, 空白格用全角空格「　」, 不要用半角空格。
2. 行不足 {W} 字用「　」补齐; 除 canvas 字符串外不要输出任何注释、行号或说明。

组字法(画面如何组成):
- 物即其字: 用表示该物的汉字直接排布成形。山的轮廓沿线放「山」; 房屋用「一」作梁、「丨」作柱; 箱子用「┌ ─ ┐ │ └ ┘」拼出箱体、箱心放「宝」「箱」二字; 雨用多行稀疏的「雨」或「丶」; 道路用一列「丨」向远方收窄。
- 远近分层: 画布上方 1~2 行是远景(字小而稀疏), 中间是中景, 下方 1~2 行是近景(字大而集中); 留白也是画面, 不要填满画布。
- 焦点唯一: 每张画面只呈现一个视觉焦点——本回合最关键的人/物/变化。

人物与连续性:
- 主角固定用「我」一个字, 整个画布至多一个「我」; NPC 用其名字的第一个字。
- 方位: 上北下南左西右东。上一张画面见【当前画面】; 若 narrative 中主角移动(走/跑/退/飞等), 新画布中「我」必须相对旧位置移动 1~2 格, 严禁瞬移; 已离场的人物不再出现。
- 前后两张画面中同名汉字的位置差会被平滑播出——"移动"就体现在这里。

示例({W}×{H}, 「我」在左, 右前方是用字拼成的一扇门):
{EXAMPLE}"""

_SLIDES_RULES = (_SLIDES_RULES
                 .replace("{W}", str(CANVAS_W))
                 .replace("{H}", str(CANVAS_H))
                 .replace("{EXAMPLE}", _EXAMPLE_JSON))

SYSTEM_RULES = """你是文字冒险游戏的"游戏主持人"(GM)与世界的唯一运转者。玩家扮演{hero}。

【世界观】玩家正处于一个经典奇幻大陆的开端: 遥远的黑曜王座上有大魔王, 人间各国勉强维持着脆弱的和平。除此之外, 世界没有任何预设内容——城市、人物、组织、任务, 全部由你根据玩家的行动即时创造, 并保持前后一致。

【本回合铁律】
1. 你生成的剧情只覆盖"自上一幕结束起、一天以内"发生的事, 不许跳到更远的未来——除非玩家在本回合输入中明确要求跳过时间(如"三天后"), 此时才允许 time_advance.days>1。
2. 剧情必须与世界账本、剧情摘要、最近剧情完全连续: 已死角色不能复活(除非有合理剧情), 已定事实不得无端推翻。
3. 你必须遵循本回合"命运骰"的倾向安排走向(见用户消息末尾), 但骰只定"调性", 不替你写字。
4. 对玩家输入的所有合理行动都要给出后果; 后果要有因果与逻辑, 重要转折要有铺垫。
5. 不要替玩家决定其未声明的主观意图(想什么/感受什么), 只描述世界与他人对其行动的反应。
6. summary 必须在上一段摘要基础上增量更新(150字内), 保留关键因果链、人物关系变化、未决伏笔。

【NPC 常驻与重逢】
1. NPC 一旦登场便常驻于世界账本, 不随回合结束而消失或被遗忘——玩家随时可能再次遇到他们。
2. 你不在场的时间, NPC 仍过自己的生活: 与某 NPC 重逢时, 参考其【上次见面】距今的天数与既有 notes/status, 先交代他这段时间的近况(去了哪/遭遇了什么/心态变化), 再续写当下互动; 严禁当作初次见面重新介绍。
3. 玩家提起或寻找旧识时: 账本记有其 location 则据实安排(或让寻人本身成为剧情), 并以其现状回应; 已死亡/永久离去的 NPC 不得无故复活或回归(除非有合理剧情)。
4. 关系有积累: 见过多次的 NPC, 其与主角的语气与距离感应随见面次数与 notes 演变(熟人/恩人/冤家各有其感)。
5. 每次重逢与其近况变化都必须写入 npc_upserts(status/note), 让账本记住这次见面。

【输出格式】只输出一个合法 JSON 对象(不要 markdown 代码块、不要多余文字), 字段如下:
{
  "narrative": "本回合剧情, 2-5个自然段, 中文, 生动但不冗长",
  "slides": [按【画面幻灯片】节约定输出, 可为空数组],
  "time_advance": {"days": 0, "period": "上午"},
  "state_updates": {
    "facts_add": ["新确立的世界事实, 每条一句"],
    "facts_remove": ["要移除的旧事实(须与账本原文一致或为其片段)"],
    "npc_upserts": [{"name": "NPC名", "status": "现状一句话", "relation": "与主角的关系", "location": "所在地", "note": "本回合与主角相关变化"}],
    "items_add": ["主角新获得的物品"],
    "location": "本回合结束时主角所在地点"
  },
  "summary": "更新后的剧情滚动摘要",
  "suggestions": ["下一步建议1", "建议2", "建议3"]
}
字段约束: time_advance.period 只能取 清晨/上午/下午/傍晚/夜晚 之一; days>=0, 未跨天为 0; npc_upserts 中同名 NPC 只出现一次, 首次登场的 NPC 四个字段都要给; suggestions 给 2-4 条, 是"铺垫下一步"的行动建议(以玩家口吻的动宾短语); 没有变化的字段给空数组; slides 见下节, 画面失败宁缺毋滥。

""" + _SLIDES_RULES

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
                 "notes": ["将祖传短剑交付主角"], "last_met": {"day": 1, "period": "夜晚"}, "met_count": 1},
        "母亲": {"status": "在灶间落泪, 担心主角安危", "relation": "至亲", "location": "溪谷村·家中",
                 "notes": [], "last_met": {"day": 1, "period": "夜晚"}, "met_count": 1},
        "老猎户": {"status": "愿意传授野外本领", "relation": "同村长辈, 未深交", "location": "溪谷村",
                  "notes": [], "last_met": {"day": 1, "period": "夜晚"}, "met_count": 1},
    },
    "items": ["祖传短剑", "半收拾好的行囊"],
    "summary": "大魔王苏醒, 溪谷村决定让主角北上报信。村长交付刻有神秘符文的祖传短剑; 主角出发前夜: 行囊收拾一半, 母亲不舍, 老猎户愿传授野外本领。",
}

REPAIR_PROMPT = """你上一次的输出不是合法 JSON 或字段不符合要求。错误信息:
{error}

请重新输出: 只输出一个修复后的合法 JSON 对象, 严格遵守此前约定的字段与取值范围, 不要任何解释或代码块标记。"""


def _elapsed_text(state, last_met) -> str:
    """上次见面距今的紧凑描述 (NPC 常驻重逢, 规划.md §7)"""
    if not isinstance(last_met, dict) or "day" not in last_met:
        return ""
    try:
        gap = int(state.get("day", 1)) - int(last_met.get("day", 1))
    except (TypeError, ValueError):
        return ""
    gap_text = "今天" if gap <= 0 else f"距今{gap}天"
    return f"上次见面:第{last_met.get('day','?')}天·{last_met.get('period','')},{gap_text}"


def world_digest(state) -> str:
    """世界账本摘要 (F6): 超长时裁剪, 保证上下文预算。
    NPC 常驻: 详细列出最近 12 名(含上次见面/见面次数/近况), 其余旧识保留记名名录防遗忘。"""
    facts = state.get("facts", [])
    if len(facts) > 24:
        facts = facts[-24:]
    npc_items = list(state.get("npcs", {}).items())
    npc_lines = []
    for name, n in npc_items[-12:]:
        notes = "; ".join(n.get("notes", [])[-3:]) if n.get("notes") else ""
        met = n.get("met_count")
        npc_lines.append(
            f"- {name}：{n.get('status','')}"
            + (f"（与主角:{n['relation']}）" if n.get("relation") else "")
            + (f"［在{n['location']}］" if n.get("location") else "")
            + (f"（{_elapsed_text(state, n.get('last_met'))}, 见过{met}次）" if met else "")
            + (f" 近况:{notes}" if notes else "")
        )
    elders = [name for name, _ in npc_items[:-12]]
    items = state.get("items", [])[-15:]
    return (
        f"第{state.get('day',1)}天·{state.get('period','清晨')}，主角位于：{state.get('location','未知')}\n"
        f"世界事实（账本）：\n" + "\n".join(f"- {f}" for f in facts) + "\n"
        + ("人物：\n" + "\n".join(npc_lines) + "\n" if npc_lines else "")
        + ("其余旧识（记名, 亦可重逢）：" + "、".join(elders) + "\n" if elders else "")
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


def current_slide_text(save) -> str:
    """上一张字画的紧凑文本 (注入 prompt, 供位置连续性)"""
    stage = save.get("stage") or []
    if not stage or not isinstance(stage[-1], dict):
        return ""
    s = stage[-1]
    rows = [str(r) for r in s.get("canvas", []) if isinstance(r, str)]
    if not rows:
        return ""
    cap = str(s.get("caption") or "").strip()
    return (cap + "\n" if cap else "") + "\n".join(rows)


def build_turn_prompt(save, player_input: str, dice: dict) -> str:
    """组装每回合用户消息: 账本 + 摘要 + 近3回合 + 当前画面 + 输入 + 骰"""
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
    ]
    slide = current_slide_text(save)
    if slide:
        parts += ["【当前画面（上一张字画; 新画面中的「我」必须与其位置连续, 按行动移动1~2格, 严禁瞬移）】",
                  slide, ""]
    parts += [
        f"【玩家行动】{player_input}",
        "",
        f"【命运骰】点数 {dice['roll']}/20，倾向「{dice['label']}」：{dice['hint']}。请在走向上体现此倾向，但不要在文中提及骰子。",
        "",
        "现在请只输出约定的 JSON。",
    ]
    return "\n".join(parts)
