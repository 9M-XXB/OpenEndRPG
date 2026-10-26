# -*- coding: utf-8 -*-
"""完全开放式RPG · 游戏主循环
回合流程: 输入 → 快照 → 掷骰 → LLM(JSON+修复) → 确定性合并状态 → 打字机叙事 → 自动存档
本文由 ZCode (GLM-5.3-Flash) 编写。
"""

import copy

import llm
import prompts
import state as st


HELP = """命令（以 / 开头；其余输入全部作为你的行动交给世界）:
  /help        显示本帮助            /status   查看世界账本（天数/地点/事实/NPC/物品）
  /roll        查看上回合命运骰      /reroll   撤销本回合并换骰重演
  /suggestions 重显上回合的建议       /save     立即存档
  /config      重新配置 API          /quit     存档并退出
提示: 直接输入 1/2/3 可快速采用上回合给出的建议; 想输入纯数字内容时请写成「数字 文字」形式。"""


class Game:
    def __init__(self, save: dict, cfg: dict, ui):
        self.save = save
        self.cfg = cfg
        self.ui = ui
        self.last_suggestions: list[str] = []
        self.last_input = ""
        self.snapshot = None

    # ---------- 主循环 ----------
    def run(self):
        if not self.save["history"]:  # 新档: 播放开场
            self.ui.title("完全开放式RPG ——" f"{self.save['name']}（主角:{self.save['hero']}）")
            self.ui.narrative(prompts.OPENING_TEXT, typewriter=False)
            self.ui.muted("（输入 /help 查看命令；其余任何输入都是你的行动）")
        else:
            s = self.save["state"]
            self.ui.info(f"欢迎回来，{self.save['hero']}。剧情回到第{s['day']}天·{s['period']}，请继续。")
        while True:
            s = self.save["state"]  # 每轮现取: /reroll 会整体替换 state 对象
            self.ui.turn_header(s["day"], s["period"], s["location"], self.save["turn"])
            line = self.ui.prompt()
            if line is None:
                return
            line = line.strip()
            if not line:
                continue
            if line.startswith("/"):
                if not self.command(line):
                    return
                continue
            if line.isdigit() and self.last_suggestions:
                idx = int(line)
                if 1 <= idx <= len(self.last_suggestions):
                    line = self.last_suggestions[idx - 1]
                    self.ui.muted(f"（采纳建议 {idx}：{line}）")
            if not self.turn(line):
                self.ui.error("回合生成失败，已回到回合开始前的状态，请换种说法重试或 /config 更换模型。")

    # ---------- 一个回合 ----------
    def turn(self, player_input: str) -> bool:
        self.last_input = player_input
        self.snapshot = copy.deepcopy(self.save)  # /reroll 用
        _, dice = prompts.roll_dice()
        self.ui.dice_hidden()
        spin = self.ui.spinner("世界正在推演")
        try:
            system = prompts.SYSTEM_RULES.replace("{hero}", self.save["hero"])
            user = prompts.build_turn_prompt(self.save, player_input, dice)
            obj = llm.complete_turn_json(self.cfg, system, user)
        except llm.LLMError as e:
            self.ui.error(f"生成失败：{e}")
            return False
        finally:
            if spin:
                spin.stop()

        old_time, _ = st.advance_time(self.save["state"], obj["time_advance"]["days"],
                                      str(obj["time_advance"].get("period", "")))
        changes = st.apply_delta(self.save, obj["state_updates"])
        save_summary = str(obj.get("summary", "")).strip()
        if save_summary:
            self.save["summary"] = save_summary
        st.record_turn(self.save, player_input, dice, obj["narrative"],
                       [str(x) for x in obj.get("suggestions", [])], old_time)
        self.save["provider"] = {"provider": self.cfg.get("provider", ""), "model": self.cfg.get("model", "")}
        st.save_game(self.save)

        self.ui.rule()
        self.ui.narrative(obj["narrative"])
        self.last_suggestions = [str(x) for x in obj.get("suggestions", [])][:4]
        self.ui.suggestions(self.last_suggestions)
        self.ui.muted(f"（已自动存档 · 账本变化: +{changes['facts+']}事实 -{changes['facts-']}事实 "
                      f"{len(changes['npcs'])}人物 +{changes['items+']}物品"
                      + (f" · 移动至{changes['location']}" if changes["location"] else "") + "）")
        return True

    # ---------- 命令 ----------
    def command(self, line: str) -> bool:
        """返回 True 继续 / False 退出主循环"""
        cmd = line.split()[0].lower()
        if cmd in ("/quit", "/exit", "/q"):
            st.save_game(self.save)
            self.ui.info(f"已存档「{self.save['name']}」。江湖再见。")
            return False
        if cmd == "/help":
            self.ui.info(HELP)
        elif cmd == "/status":
            self.show_status()
        elif cmd == "/save":
            st.save_game(self.save)
            self.ui.success(f"已存档：{st.save_path(self.save['name'])}")
        elif cmd == "/roll":
            log = self.save.get("dice_log", [])
            if log:
                last = log[-1]
                self.ui.dice_reveal(f"回合 {last['turn']}：点数 {last['roll']}/20 · {last['label']}")
            else:
                self.ui.info("还没有掷过骰。")
        elif cmd == "/suggestions":
            if self.last_suggestions:
                self.ui.suggestions(self.last_suggestions)
            else:
                self.ui.info("本回合还没有建议。")
        elif cmd == "/reroll":
            self.reroll()
        elif cmd == "/config":
            from rpg import run_wizard
            self.cfg = run_wizard(self.ui)
            self.ui.info(f"已切换到 {self.cfg.get('provider')} / {self.cfg.get('model')}")
        else:
            self.ui.warn(f"未知命令 {cmd}；/help 查看命令。")
        return True

    def show_status(self):
        s = self.save["state"]
        self.ui.rule()
        self.ui.info(f"存档「{self.save['name']}」 主角:{self.save['hero']} 回合:{self.save['turn']}")
        self.ui.info(f"时间: 第{s['day']}天·{s['period']}    地点: {s['location']}")
        self.ui.info("世界事实:")
        for f in s["facts"]:
            self.ui.info(f"  · {f}")
        self.ui.info("人物:")
        for name, n in s.get("npcs", {}).items():
            self.ui.info(f"  · {name} — {n.get('status','')}"
                         + (f"（{n['relation']}）" if n.get("relation") else "")
                         + (f"［{n['location']}］" if n.get("location") else ""))
        self.ui.info("物品: " + ("、".join(s["items"]) if s["items"] else "（空）"))
        self.ui.muted("剧情摘要: " + (self.save.get("summary") or "（无）"))

    def reroll(self):
        if not self.snapshot or not self.last_input:
            self.ui.info("本回合还没有可重掷的内容。")
            return
        self.ui.info(f"撤销本回合，换骰重演：「{self.last_input}」")
        self.save.clear()
        self.save.update(copy.deepcopy(self.snapshot))
        self.turn(self.last_input)
