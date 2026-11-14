# -*- coding: utf-8 -*-
"""完全开放式RPG · 提示词与规则文案
依据: 调研笔记.md — song-2024(叙事归LLM/状态归函数), zhou-2023(两级记忆), wang-2023(自动课程式的建议铺垫)。
画面幻灯片: 规划.md 第五轮 — 统一 glyphs 契约(坐标/字号档/旋转, 中英双语); 组字法与字母构形法
在【画面幻灯片】节教给运行时 LLM, 前端零图像元素; 手写示例七例为规律来源、非模板(作者 2026-11-13)。
本文由 ZCode (GLM-5.3-Flash) 编写。
"""

import copy
import json
import random

GAME_TITLE = "完全开放式RPG · 终端原型"

PERIODS = ["清晨", "上午", "下午", "傍晚", "夜晚"]
LANGUAGES = ("zh", "en")

PERIOD_EN = {"清晨": "dawn", "上午": "morning", "下午": "afternoon",
             "傍晚": "evening", "夜晚": "night"}


def period_label(period: str, language: str = "zh") -> str:
    """时段展示标签(状态内部仍存中文枚举, 仅展示层换算)"""
    return PERIOD_EN.get(period, period) if language == "en" else period


# ---------- 旧字画画布常量 (v0.2 网格; 仅用于旧存档换算, 新产出一律走 glyphs) ----------

CANVAS_W = 12
CANVAS_H = 6

FULL = "　"  # 全角空格 = 空白格


def pad_row(s: str) -> str:
    """画布行归一: 半角空格视为空白, 不足 W 补全角空格, 超出截断"""
    s = str(s).replace(" ", FULL)
    return s[:CANVAS_W] + FULL * max(0, CANVAS_W - len(s))


def canvas(*rows: str) -> list[str]:
    """按 W×H 规格生成画布行(不足补空行)"""
    rows = list(rows) + [""] * (CANVAS_H - len(rows))
    return [pad_row(r) for r in rows[:CANVAS_H]]


# ---------- glyphs 契约 v2 常量 (规划.md 第五轮; 前端经 /api/state 的 stage_spec 读取同一来源) ----------

STAGE_COORDS = 100   # x/y 百分比坐标; 渲染框保持 12:7
S_MIN, S_MAX = 1, 9  # 字号档: 1~2 远景小字, 3 常规, 5~6 主角/近物, 8~9 巨型主干
R_MAX = 90           # 旋转角 |r| 上限(度; 正=顺时针)
GLYPHS_MAX = 24      # 每张字画最多字数
SLIDES_MAX = 3       # 每回合最多张数
TONES = ["暗", "明", "暖", "冷", "灰"]


def _num(v, default: float) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def glyphs(*specs) -> list[dict]:
    """按 glyphs 契约生成字形列表; 每个 spec = (ch, x, y[, s[, r]]), 缺省 s=3 r=0"""
    out = []
    for spec in specs:
        out.append({"ch": spec[0], "x": spec[1], "y": spec[2],
                    "s": spec[3] if len(spec) > 3 else 3,
                    "r": spec[4] if len(spec) > 4 else 0})
    return out[:GLYPHS_MAX]


def canvas_to_glyphs(rows) -> list[dict]:
    """旧 canvas 网格 → glyphs (与前端渲染端同款换算; 旧存档兼容用)"""
    out = []
    for r, row in enumerate(rows or []):
        for c, ch in enumerate(str(row)):
            if ch and ch != FULL:
                out.append({"ch": ch,
                            "x": round((c + 0.5) * STAGE_COORDS / CANVAS_W, 1),
                            "y": round((r + 0.5) * STAGE_COORDS / CANVAS_H, 1),
                            "s": 2 if r < 2 else 3,  # 旧行分层 → 字号档
                            "r": 0})
    return out[:GLYPHS_MAX]


def slide(caption: str, tone: str, glyph_list: list[dict]) -> dict:
    return {"caption": caption, "tone": tone, "glyphs": glyph_list[:GLYPHS_MAX]}


# ---------- 命运骰: d20 + 事件倾向表 (F5 随机性; 双语) ----------

DICE_TABLE = [
    (1, 4, "意外挫折", "an unexpected setback",
     "本回合安排一个出乎意料的挫折或阻力(可克服, 但要有真实代价)",
     "Arrange an unexpected setback or obstacle this turn (surmountable, but with a real cost)"),
    (5, 9, "平淡进展", "steady progress",
     "本回合按情理平稳推进, 穿插一个小的生活化细节",
     "Let events move along sensibly this turn, woven with a small everyday detail"),
    (10, 14, "小机遇", "a small opening",
     "本回合出现一个对玩家有利的小机遇或有用信息",
     "A small opportunity or a useful piece of information appears this turn"),
    (15, 19, "重要转机", "a major turn",
     "本回合发生一个显著改变局势的重要转机",
     "Something significant changes the situation this turn"),
    (20, 20, "命运大事件", "a twist of fate",
     "本回合发生一件震动局面的大事件(新势力/重大揭示/意外相遇)",
     "A major event shakes the situation this turn (new faction / major revelation / unexpected encounter)"),
]


def roll_dice(language: str = "zh") -> tuple[int, dict]:
    """掷 d20, 返回 (点数, 倾向 dict{roll,label,hint}; 标签按语言)"""
    n = random.randint(1, 20)
    zh = language != "en"
    for lo, hi, zl, el, zh_hint, en_hint in DICE_TABLE:
        if lo <= n <= hi:
            return n, {"roll": n, "label": zl if zh else el,
                       "hint": zh_hint if zh else en_hint}
    return n, {"roll": n, "label": "?" if zh else "?", "hint": ""}


def dice_line(d: dict, language: str = "zh") -> str:
    if language == "en":
        return f"Fate die {d['roll']:2d} · {d['label']}"
    return f"命运骰 {d['roll']:2d} · {d['label']}"


def turn_dice_line(turn, roll, label, language: str = "zh") -> str:
    if language == "en":
        return f"Turn {turn}: roll {roll}/20 · {label}"
    return f"回合 {turn}：点数 {roll}/20 · {label}"


# ---------- 字画: 开场幻灯片(属"游戏本体提供的开头", README §2 种子范畴) ----------

# 剑的字母构形(作者 2026-11-13 给定): s 旋转作剑柄, w 作护手, ord 沿对角线作剑身,
# d 必为小写——其升部上端模拟剑尖
SWORD_GLYPHS = glyphs(
    ("s", 14, 82, 5, -40),   # 剑柄(左下)
    ("w", 31, 66, 7, 50),    # 护手(垂直于剑身的横向字)
    ("o", 47, 52, 5, -40),   # 剑身
    ("r", 61, 38, 4, -40),   # 剑身(渐小=纵深)
    ("d", 76, 22, 6, 50),    # 剑尖: 小写 d 的升部指向右上方
)

OPENING_SLIDE_ZH = slide("溪谷村·夜", "暗", canvas_to_glyphs(canvas(
    "",
    "　山　　　山　　山",
    "　　灯　　　　灯",
    "　　　一一一一",
    "　　　｜　　｜",
    "　我",
)))

OPENING_SLIDE_EN = slide("The Ancestral Sword", "暗", copy.deepcopy(SWORD_GLYPHS))

# 教学示例
EXAMPLE_SLIDE_ZH = slide("离村北行", "暗", glyphs(
    ("山", 15, 26, 2), ("山", 45, 20, 3), ("山", 76, 30, 2),
    ("一", 34, 56, 4), ("一", 46, 56, 4), ("一", 58, 56, 4),
    ("丨", 34, 72, 4), ("丨", 58, 72, 4),
    ("我", 12, 88, 6),
))

EXAMPLE_SLIDE_EN = slide("an old sword", "暗", copy.deepcopy(SWORD_GLYPHS))


def _example_json(s: dict) -> str:
    return "\n".join("  " + ln for ln in
                     json.dumps(s, ensure_ascii=False, indent=1).splitlines())


# ---------- 画面幻灯片教学节: 教会运行时 LLM 生成画面 (双语, 按语言二选一注入) ----------

_SLIDES_RULES_ZH = """【画面幻灯片(与剧情同时输出, 你兼任画面导演)】
narrative 用文字叙述, slides 数组(0~3张)把其中最具画面性的瞬间定格成"字画"。文字与画面不得矛盾; 纯对话/心理活动的回合可为 0 张。

每张 slide 的格式:
{"caption": "画面小标题(10字内)", "tone": "暗|明|暖|冷|灰 之一", "glyphs": [{"ch": "山", "x": 45, "y": 20, "s": 3, "r": 0}, ...]}

glyphs 规格(必须严格遵守):
1. glyphs 是字的列表, 最多 {GM} 个; ch 是单个汉字/标点/「丨」「一」「┌」等; 缺省字段按 s=3, r=0 处理。
2. x/y 是 0~100 的舞台百分比坐标(x 右 y 下), 即字的中心位置; 舞台留白也是画面, 不要填满。
3. s 是字号档 1~9: 1~2 远景小字, 3 常规, 5~6 主角/近物, 8~9 巨型主干; r 是旋转角 -90~90 度(正=顺时针)。

组字法(画面如何组成):
- 物即其字: 用表示该物的汉字直接排布成形。山的轮廓沿线放「山」; 房屋用「一」作梁、「丨」作柱; 箱子用「┌ ─ ┐ │ └ ┘」围出箱体、箱心放「宝」「箱」二字; 雨用散布的「雨」「丶」; 道路用一列「丨」沿对角线渐小伸向远方。
- 字号即远近: 远景小号(1~2)稀疏, 近景/焦点大号(5~7); 巨型字号(8~9)只给画面中最大的那个形体。
- 旋转表达方向与透视: 斜坡、道路、队伍沿对角线旋转排布, 越远越小。
- 焦点唯一: 每张画面只呈现一个视觉焦点——本回合最关键的人/物/变化。

人物与连续性:
- 主角固定用「我」一个字(建议 s=5~6), 整个画布至多一个「我」; NPC 用其名字的第一个字。
- 方位: 上北下南左西右东。上一张画面见【当前画面】; 若 narrative 中主角移动(走/跑/退/飞等), 新画布中「我」的坐标必须相对旧位置移动 1~15 个舞台单位, 严禁瞬移; 已离场的人物不再出现。
- 前后两张画面中同名汉字的位移会被平滑播出——"移动"就体现在这里。

这些手法是词汇, 不是模板——按本回合的实际场景取用与变通, 不要逐词硬套。

示例(「我」在左, 右前方是用字拼成的一扇门):
{EXAMPLE}"""

_SLIDES_RULES_EN = """【PICTURE SLIDES (glyph art — you are also the art director)】
narrative tells the story in words; the slides array (0~3 items) freezes its most visual moments as glyph art. Words and pictures must not contradict; a pure dialogue/reflection turn may have 0 slides.

Format of each slide:
{"caption": "short title (within 24 characters)", "tone": "暗|明|暖|冷|灰 (one of these five Chinese enum values)", "glyphs": [{"ch": "T", "x": 50, "y": 50, "s": 3, "r": 0}, ...]}

Strict format rules:
1. glyphs is a list of at most {GM} glyphs; ch is a single letter/digit/punctuation mark — CASE MATTERS; missing fields default to s=3, r=0.
2. x/y are stage percentage coordinates 0~100 (x rightward, y downward) marking the glyph's CENTER; whitespace is part of the picture — never fill the stage.
3. s is the size tier 1~9: 1~2 tiny & distant, 3 normal, 5~6 the hero / near objects, 8~9 one giant structural letter; r is rotation in degrees, -90~90 (positive = clockwise).

Letter pictography (how a word becomes a picture):
- One KEY letter, hugely enlarged, forms the structure: in "table" a giant T is the tabletop and its leg; in "bOx" the huge O is the box body with small b/x flanking it; in "chair" an extra-tall h is the backrest.
- Rotation expresses form and depth: letters placed along a diagonal, shrinking toward the far end, read as perspective — a road receding, a marching column. A wide w rotated perpendicular to a blade reads as a cross-guard.
- Stacking spells a creature: "wOman" stacked top-to-bottom reads as a figure (w hair, O head, m body, A N legs).
- Scattered small glyphs read as drifting atmosphere: snow is a big O with s/n/w/e scattered around it.
- Build artifacts from their own letters. An old sword: s rotated (~-40) at the lower left is the HILT; w (rotated ~+50, perpendicular to the blade) is the GUARD; o r d ascend along the same diagonal as the BLADE, slightly shrinking with distance; the final d MUST be lowercase and rotated (~+50) so its ascender sticks out beyond as the TIP — uppercase D has no ascender, never use it.
- One focal point per slide. Hero marker: a single "I" (capital i), at most one per slide, s=5~6; NPCs use the first letter of their name.
- Continuity: north is up, west is left. The previous slide is given as 【当前画面】; if the hero moves in the narrative, "I" must shift by 1~15 stage units — never teleport. Glyph displacement is animated smoothly between slides.

These patterns are a vocabulary, not templates — combine and adapt them to what actually happens in this turn; never force a word into a picture when the scene does not call for it.

Example (an old sword):
{EXAMPLE}"""


def _slides_rules(language: str) -> str:
    example = _example_json(EXAMPLE_SLIDE_EN if language == "en" else EXAMPLE_SLIDE_ZH)
    tpl = _SLIDES_RULES_EN if language == "en" else _SLIDES_RULES_ZH
    return tpl.replace("{GM}", str(GLYPHS_MAX)).replace("{EXAMPLE}", example)


_BASE_RULES = """你是文字冒险游戏的"游戏主持人"(GM)与世界的唯一运转者。玩家扮演{hero}。

【世界观】玩家正处于一个经典奇幻大陆的开端: 遥远的黑曜王座上有大魔王, 人间各国勉强维持着脆弱的和平。除此之外, 世界没有任何预设内容——城市、人物、组织、任务, 全部由你根据玩家的行动即时创造, 并保持前后一致。

【本回合铁律】
1. 你生成的剧情只覆盖"自上一幕结束起、一天以内"发生的事, 不许跳到更远的未来——除非玩家在本回合输入中明确要求跳过时间(如"三天后"), 此时才允许 time_advance.days>1。
2. 剧情必须与世界账本、剧情摘要、最近剧情完全连续: 已死角色不能复活(除非有合理剧情), 已定事实不得无端推翻。
3. 你必须遵循本回合"命运骰"的倾向安排走向(见用户消息末尾), 但骰只定"调性", 不替你写字。
4. 对玩家输入的所有合理行动都要给出后果; 后果要有因果与逻辑, 重要转折要有铺垫。
5. 不要替玩家决定其未声明的主观意图(想什么/感受什么), 只描述世界与他人对其行动的反应。
6. summary 必须在上一段摘要基础上增量更新{SUMMARY_LIMIT}, 保留关键因果链、人物关系变化、未决伏笔。

【NPC 常驻与重逢】
1. NPC 一旦登场便常驻于世界账本, 不随回合结束而消失或被遗忘——玩家随时可能再次遇到他们。
2. 你不在场的时间, NPC 仍过自己的生活: 与某 NPC 重逢时, 参考其【上次见面】距今的天数与既有 notes/status, 先交代他这段时间的近况(去了哪/遭遇了什么/心态变化), 再续写当下互动; 严禁当作初次见面重新介绍。
3. 玩家提起或寻找旧识时: 账本记有其 location 则据实安排(或让寻人本身成为剧情), 并以其现状回应; 已死亡/永久离去的 NPC 不得无故复活或回归(除非有合理剧情)。
4. 关系有积累: 见过多次的 NPC, 其与主角的语气与距离感应随见面次数与 notes 演变(熟人/恩人/冤家各有其感)。
5. 每次重逢与其近况变化都必须写入 npc_upserts(status/note), 让账本记住这次见面。

【输出格式】只输出一个合法 JSON 对象(不要 markdown 代码块、不要多余文字), 字段如下:
{
  "narrative": "{NARRATIVE_DESC}",
  "slides": [按画面教学节约定输出, 可为空数组],
  "time_advance": {"days": 0, "period": "上午"},
  "state_updates": {
    "facts_add": ["新确立的世界事实, 每条一句"],
    "facts_remove": ["要移除的旧事实(须与账本原文一致或为其片段)"],
    "npc_upserts": [{"name": "NPC名", "status": "现状一句话", "relation": "与主角的关系", "location": "所在地", "note": "本回合与主角相关变化"}],
    "items_add": ["主角新获得的物品"],
    "location": "本回合结束时主角所在地点"
  },
  "summary": "{SUMMARY_DESC}",
  "suggestions": ["{SUGG_EXAMPLE}", "...", "..."]
}
字段约束: time_advance.period 只能取 清晨/上午/下午/傍晚/夜晚 之一{PERIOD_NOTE}; days>=0, 未跨天为 0; npc_upserts 中同名 NPC 只出现一次, 首次登场的 NPC 四个字段都要给; suggestions 给 2-4 条({SUGG_DESC}); 没有变化的字段给空数组; slides 见下节, 画面失败宁缺毋滥。

"""


def system_rules(hero: str, language: str = "zh") -> str:
    """按游戏语言组装系统提示词 (规则骨架中文, 叙事/画面教学按语言)"""
    if language == "en":
        narrative_desc = "this turn's story, 2-5 paragraphs, in vivid natural English, not overly long"
        summary_desc = "the updated rolling plot summary (in English, incremental)"
        summary_limit = " (under 120 words)"
        sugg_desc = "short next-step suggestions phrased in the player's voice, in English"
        sugg_example = "ask the elder about the rune"
        period_note = " (keep these exact Chinese enum values even though the story is in English)"
        slides_section = _slides_rules("en")
    else:
        narrative_desc = "本回合剧情, 2-5个自然段, 中文, 生动但不冗长"
        summary_desc = "更新后的剧情滚动摘要"
        summary_limit = "(150字内)"
        sugg_desc = "以玩家口吻的动宾短语"
        sugg_example = "下一步建议1"
        period_note = ""
        slides_section = _slides_rules("zh")
    return (_BASE_RULES
            .replace("{hero}", hero)
            .replace("{NARRATIVE_DESC}", narrative_desc)
            .replace("{SUMMARY_DESC}", summary_desc)
            .replace("{SUMMARY_LIMIT}", summary_limit)
            .replace("{SUGG_DESC}", sugg_desc)
            .replace("{SUGG_EXAMPLE}", sugg_example)
            .replace("{PERIOD_NOTE}", period_note)
            + slides_section)


OPENING_TEXT_ZH = """**序章 · 启程**

溪谷村坐落在王国东南的群山褶皱里, 已经七十年没听说过战事。七十年前的旧闻重新在灶台与井台间流传——黑曜王座上的大魔王苏醒了。北方商队带来烧成焦炭的界碑, 山那边逃来的难民说, 夜里的地平线会发出暗红色的光。

村长把一柄祖传的短剑放在你手里。剑身朴素, 剑格上刻着一个你叫不出名字的符文。"长老们商量过了, "老人声音发哑, "村里凑不出一支像样的队伍, 但总得有人去把消息带到王都, 或者……做点什么。"

今夜是出发前的最后一晚。行囊已收拾了一半, 母亲在灶间落泪, 门口的老猎户据说愿意教你几手野外保命的本事。天亮之后, 道路向北方延伸, 那里有魔王, 也有你从未见过的整个世界。

（你可以做任何事: 和任何人交谈、出发、练剑、睡觉、打听消息……直接输入即可。）"""

OPENING_TEXT_EN = """**Prologue · The Departure**

Brookvale Village lies folded into the southeastern hills of the kingdom, and for seventy years it has heard nothing of war. Now the old news runs again from hearth to well — the Demon King on the Obsidian Throne has awakened. Caravans from the north bring boundary stones scorched to charcoal, and refugees from beyond the mountains say the night horizon glows a dull red.

The village elder places an ancestral short sword in your hands. The blade is plain, with a rune on the guard that no one can name. "The elders have talked it over," the old man says, his voice hoarse. "The village cannot field a proper company — but someone must carry the news to the royal capital, or... do something."

Tonight is your last night before departure. Your pack is half-ready; your mother weeps by the stove; the old hunter at the gate, they say, is willing to teach you a few tricks of staying alive out there. At dawn the road runs north — toward the Demon King, and toward the whole world you have never seen.

(You may do anything: talk to anyone, set out, practice with the sword, sleep, ask around... just type it.)"""


def opening_text(language: str = "zh") -> str:
    return OPENING_TEXT_EN if language == "en" else OPENING_TEXT_ZH


OPENING_STATE_ZH = {
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

OPENING_STATE_EN = {
    "day": 1,
    "period": "夜晚",
    "location": "Brookvale Village · home",
    "facts": [
        "The Demon King has awakened on the Obsidian Throne; monsters and refugees press the northern border",
        "Brookvale Village is the hero's hometown in the southeastern hills, warless for seventy years",
        "The village elder handed the hero an ancestral short sword with an unidentifiable rune on its guard",
        "The hero plans to go north: carry the news to the royal capital first, then deal with the Demon King",
        "The old hunter is willing to teach the hero wilderness skills",
    ],
    "npcs": {
        "Elder": {"status": "aged and worried, urges the hero to carry the news north",
                  "relation": "village elder, trusts the hero", "location": "Brookvale Village",
                  "notes": ["entrusted the ancestral short sword to the hero"],
                  "last_met": {"day": 1, "period": "夜晚"}, "met_count": 1},
        "Mother": {"status": "weeping by the stove, fears for the hero's safety",
                   "relation": "close family", "location": "Brookvale Village · home",
                   "notes": [], "last_met": {"day": 1, "period": "夜晚"}, "met_count": 1},
        "Old Hunter": {"status": "willing to teach wilderness skills",
                       "relation": "village elder, not yet close", "location": "Brookvale Village",
                       "notes": [], "last_met": {"day": 1, "period": "夜晚"}, "met_count": 1},
    },
    "items": ["Ancestral short sword", "Half-packed travel bag"],
    "summary": "The Demon King has awakened; Brookvale Village decides to send the hero north with the news. The elder entrusts an ancestral short sword with a mysterious rune; on the eve of departure the pack is half-ready, the mother grieves, and the old hunter offers to teach wilderness skills.",
}


def opening_state(language: str = "zh") -> dict:
    src = OPENING_STATE_EN if language == "en" else OPENING_STATE_ZH
    return copy.deepcopy(src)


def opening_slide(language: str = "zh") -> dict:
    return copy.deepcopy(OPENING_SLIDE_EN if language == "en" else OPENING_SLIDE_ZH)


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
    """上一张字画的紧凑文本 (注入 prompt, 供位置连续性; glyphs 与旧 canvas 兼容)"""
    stage = save.get("stage") or []
    if not stage or not isinstance(stage[-1], dict):
        return ""
    s = stage[-1]
    cap = str(s.get("caption") or "").strip()
    gl = s.get("glyphs")
    if isinstance(gl, list) and gl:
        items = []
        for g in gl[:GLYPHS_MAX]:
            if not isinstance(g, dict):
                continue
            ch = str(g.get("ch", ""))[:1]
            if not ch:
                continue
            items.append(f"{ch}({round(_num(g.get('x'), 50))},{round(_num(g.get('y'), 50))},"
                         f"{round(_num(g.get('s'), 3))},{round(_num(g.get('r'), 0))})")
        body = " ".join(items)
    else:
        rows = [str(r) for r in s.get("canvas", []) if isinstance(r, str)]
        body = "\n".join(rows) if rows else ""
    if not body:
        return ""
    return (cap + "\n" if cap else "") + body


def build_turn_prompt(save, player_input: str, dice: dict, language: str = "zh") -> str:
    """组装每回合用户消息: 账本 + 摘要 + 近3回合 + 当前画面 + 输入 + 骰"""
    en = language == "en"
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
    slide_text = current_slide_text(save)
    if slide_text:
        note = ('The previous slide is given below; the new slide\'s "I" must stay position-continuous '
                'with it, moving 1~15 stage units per action, never teleporting'
                if en else
                '上一张字画如下; 新画面中的「我」必须与其位置连续, 按行动移动1~15个舞台单位, 严禁瞬移')
        parts += ["【当前画面（" + note + "）】", slide_text, ""]
    dice_line_text = (f"【FATE DIE】Roll {dice['roll']}/20, tendency \"{dice['label']}\": {dice['hint']}. "
                      "Shape the turn's direction accordingly, but never mention the die in the text."
                      if en else
                      f"【命运骰】点数 {dice['roll']}/20，倾向「{dice['label']}」：{dice['hint']}。请在走向上体现此倾向，但不要在文中提及骰子。")
    parts += [
        f"【玩家行动】{player_input}",
        "",
        dice_line_text,
        "",
        "Now output only the agreed JSON." if en else "现在请只输出约定的 JSON。",
    ]
    return "\n".join(parts)
