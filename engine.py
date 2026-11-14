# -*- coding: utf-8 -*-
"""完全开放式RPG · 游戏主循环
回合流程: 输入 → 快照 → 掷骰 → LLM(JSON+修复) → 确定性合并状态 → 打字机叙事 → 自动存档
本文由 ZCode (GLM-5.3-Flash) 编写。
"""

import copy

import llm
import prompts
import state as st


HELP_ZH = """命令（以 / 开头；其余输入全部作为你的行动交给世界）:
  /help        显示本帮助            /status   查看世界账本（天数/地点/事实/NPC/物品）
  /roll        查看上回合命运骰      /reroll   撤销本回合并换骰重演
  /suggestions 重显上回合的建议       /save     立即存档
  /config      重新配置 API          /quit     存档并退出
提示: 直接输入 1/2/3 可快速采用上回合给出的建议; 想输入纯数字内容时请写成「数字 文字」形式。"""

HELP_EN = """Commands (start with /; everything else is your action, handed to the world):
  /help        show this help           /status   inspect the world ledger (day/place/facts/NPCs/items)
  /roll        show last turn's fate die /reroll  undo this turn and re-roll
  /suggestions re-show last suggestions /save     save now
  /config      reconfigure the API      /quit     save and quit
Tip: type 1/2/3 to quickly adopt last turn's suggestions; to enter plain numbers, write "12 sometext"."""


class Game:
    def __init__(self, save: dict, cfg: dict, ui):
        self.save = save
        self.cfg = cfg
        self.ui = ui
        self.last_suggestions: list[str] = []
        self.last_input = ""
        self.snapshot = None

    # ---------- 主循环 ----------
    def lang(self) -> str:
        # 全局配置语言优先: 大厅切换语言后, 旧存档的后续生成与界面一并跟随
        return self.cfg.get("language") or self.save.get("language") or "zh"

    def run(self):
        lang = self.lang()
        if not self.save["history"]:  # 新档: 播放开场
            self.ui.title("OpenEndRPG —— " + self.save['name'] + " (hero: " + self.save['hero'] + ")"
                          if lang == "en" else
                          "完全开放式RPG ——" f"{self.save['name']}（主角:{self.save['hero']}）")
            self.ui.narrative(prompts.opening_text(lang), typewriter=False)
            self.ui.muted("(Type /help for commands; anything else you type is your action)"
                          if lang == "en" else
                          "（输入 /help 查看命令；其余任何输入都是你的行动）")
        else:
            s = self.save["state"]
            self.ui.info(f"Welcome back, {self.save['hero']}. The story resumes on Day {s['day']} · "
                         f"{prompts.period_label(s['period'], lang)}; carry on."
                         if lang == "en" else
                         f"欢迎回来，{self.save['hero']}。剧情回到第{s['day']}天·{prompts.period_label(s['period'], lang)}，请继续。")
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
                self.ui.error("Turn generation failed; the game returned to the state before the turn. "
                              "Rephrase and retry, or /config to switch models."
                              if self.lang() == "en" else
                              "回合生成失败，已回到回合开始前的状态，请换种说法重试或 /config 更换模型。")

    # ---------- 一个回合 ----------
    def turn(self, player_input: str) -> bool:
        lang = self.lang()
        self.last_input = player_input
        self.snapshot = copy.deepcopy(self.save)  # /reroll 用
        _, dice = prompts.roll_dice(lang)
        self.ui.dice_hidden()
        spin = self.ui.spinner("世界正在推演")
        try:
            system = prompts.system_rules(self.save["hero"], lang)
            user = prompts.build_turn_prompt(self.save, player_input, dice, lang)
            obj = llm.complete_turn_json(self.cfg, system, user)
        except llm.LLMError as e:
            self.ui.error(("Generation failed: " + str(e)) if lang == "en" else f"生成失败：{e}")
            return False
        finally:
            if spin:
                spin.stop()

        old_time, _ = st.advance_time(self.save["state"], obj["time_advance"]["days"],
                                      str(obj["time_advance"].get("period", "")))
        changes = st.apply_delta(self.save, obj["state_updates"])
        # 字画幻灯片: 展示元数据, 只做宽松钳位(画面失败不使回合失败), 不进世界账本
        slides = obj.get("slides")
        slides = [x for x in slides if isinstance(x, dict)][:3] if isinstance(slides, list) else []
        if slides:
            self.save["stage"] = slides
        save_summary = str(obj.get("summary", "")).strip()
        if save_summary:
            self.save["summary"] = save_summary
        st.record_turn(self.save, player_input, dice, obj["narrative"],
                       [str(x) for x in obj.get("suggestions", [])], old_time, slides)
        self.save["provider"] = {"provider": self.cfg.get("provider", ""), "model": self.cfg.get("model", "")}
        st.save_game(self.save)

        self.ui.rule()
        self.ui.narrative(obj["narrative"])
        self.last_suggestions = [str(x) for x in obj.get("suggestions", [])][:4]
        self.ui.suggestions(self.last_suggestions)
        if lang == "en":
            line = (f"(auto-saved · ledger: +{changes['facts+']} facts -{changes['facts-']} facts, "
                    f"{len(changes['npcs'])} NPCs, +{changes['items+']} items"
                    + (f" · moved to {changes['location']}" if changes["location"] else "") + ")")
        else:
            line = (f"（已自动存档 · 账本变化: +{changes['facts+']}事实 -{changes['facts-']}事实 "
                    f"{len(changes['npcs'])}人物 +{changes['items+']}物品"
                    + (f" · 移动至{changes['location']}" if changes["location"] else "") + "）")
        self.ui.muted(line)
        return True

    # ---------- 命令 ----------
    def command(self, line: str) -> bool:
        """返回 True 继续 / False 退出主循环"""
        lang = self.lang()
        en = lang == "en"
        cmd = line.split()[0].lower()
        if cmd in ("/quit", "/exit", "/q"):
            st.save_game(self.save)
            self.ui.info(f'Saved "{self.save["name"]}". Farewell.' if en
                         else f"已存档「{self.save['name']}」。江湖再见。")
            return False
        if cmd == "/help":
            self.ui.info(HELP_EN if en else HELP_ZH)
        elif cmd == "/status":
            self.show_status()
        elif cmd == "/save":
            st.save_game(self.save)
            self.ui.success(f"Saved: {st.save_path(self.save['name'])}" if en
                            else f"已存档：{st.save_path(self.save['name'])}")
        elif cmd == "/roll":
            log = self.save.get("dice_log", [])
            if log:
                last = log[-1]
                self.ui.dice_reveal(prompts.turn_dice_line(
                    last["turn"], last["roll"], last.get("label", ""), lang))
            else:
                self.ui.info("No dice rolled yet." if en else "还没有掷过骰。")
        elif cmd == "/suggestions":
            if self.last_suggestions:
                self.ui.suggestions(self.last_suggestions)
            else:
                self.ui.info("No suggestions yet this turn." if en else "本回合还没有建议。")
        elif cmd == "/reroll":
            self.reroll()
        elif cmd == "/config":
            from rpg import run_wizard
            self.cfg = run_wizard(self.ui)
            self.ui.info(f"Switched to {self.cfg.get('provider')} / {self.cfg.get('model')}" if en
                         else f"已切换到 {self.cfg.get('provider')} / {self.cfg.get('model')}")
        else:
            self.ui.warn(f"Unknown command {cmd}; /help for the list." if en
                         else f"未知命令 {cmd}；/help 查看命令。")
        return True

    def show_status(self):
        s = self.save["state"]
        en = self.lang() == "en"
        self.ui.rule()
        self.ui.info(f'Save "{self.save["name"]}"  hero:{self.save["hero"]}  turn:{self.save["turn"]}'
                     if en else
                     f"存档「{self.save['name']}」 主角:{self.save['hero']} 回合:{self.save['turn']}")
        self.ui.info(f"Time: Day {s['day']} · {prompts.period_label(s['period'], 'en')}    Location: {s['location']}"
                     if en else
                     f"时间: 第{s['day']}天·{s['period']}    地点: {s['location']}")
        self.ui.info("World facts:" if en else "世界事实:")
        for f in s["facts"]:
            self.ui.info(f"  · {f}")
        self.ui.info("Characters:" if en else "人物:")
        for name, n in s.get("npcs", {}).items():
            lm = n.get("last_met") or {}
            if en:
                line = f"  · {name} — {n.get('status','')}"
                line += f" ({n['relation']})" if n.get('relation') else ""
                line += f" [at {n['location']}]" if n.get('location') else ""
                line += (f" (last met Day {lm['day']} · {prompts.period_label(lm.get('period',''), 'en')}"
                         f", met {n.get('met_count', 1)} time(s))" if lm else "")
            else:
                line = f"  · {name} — {n.get('status','')}"
                line += f"（{n['relation']}）" if n.get('relation') else ""
                line += f"［{n['location']}］" if n.get('location') else ""
                line += (f"（上次见面 第{lm['day']}天·{lm.get('period','')}"
                         f"，见过{n.get('met_count', 1)}次）" if lm else "")
            self.ui.info(line)
        self.ui.info(("Items: " + ("; ".join(s["items"]) if s["items"] else "(empty)")) if en
                     else "物品: " + ("、".join(s["items"]) if s["items"] else "（空）"))
        self.ui.muted(("Plot summary: " if en else "剧情摘要: ")
                      + (self.save.get("summary") or ("(none)" if en else "（无）")))

    def reroll(self):
        en = self.lang() == "en"
        if not self.snapshot or not self.last_input:
            self.ui.info("Nothing to re-roll yet this turn." if en else "本回合还没有可重掷的内容。")
            return
        self.ui.info(f'Undoing this turn and re-rolling: "{self.last_input}"' if en
                     else f"撤销本回合，换骰重演：「{self.last_input}」")
        self.save.clear()
        self.save.update(copy.deepcopy(self.snapshot))
        self.turn(self.last_input)
