# -*- coding: utf-8 -*-
"""完全开放式RPG · Web 事件适配器
与 ui.UI 同方法面: 把 engine 的渲染调用收集为事件列表, 由 server 转成 JSON。
engine/llm/state 无需感知 Web 的存在 (规划.md §3)。
本文由 ZCode (GLM-5.3-Flash) 编写。
"""


class CollectingUI:
    """收集版渲染器: server 每次请求前清空 events, 回合/命令结束后整包返回"""

    def __init__(self):
        self.events: list[dict] = []

    def _add(self, kind: str, text: str = ""):
        self.events.append({"k": kind, "t": text})

    # --- 基础输出 ---
    def info(self, text: str):
        self._add("info", text)

    def muted(self, text: str):
        self._add("muted", text)

    def warn(self, text: str):
        self._add("warn", text)

    def error(self, text: str):
        self._add("error", text)

    def success(self, text: str):
        self._add("success", text)

    def accent(self, text: str):
        self._add("accent", text)

    # --- 游戏画面 ---
    def title(self, text: str):
        self._add("title", text)

    def rule(self):
        pass  # 纯排版分隔, Web 端不需要

    def turn_header(self, day: int, period: str, location: str, turn: int):
        self._add("header", f"第{day}天 · {period} · {location} · 回合{turn}")

    def narrative(self, text: str, typewriter: bool = True):
        self._add("narrative", text)

    def suggestions(self, items: list[str]):
        items = [str(x) for x in items if str(x).strip()]
        if items:
            self.events.append({"k": "suggestions", "items": items})

    def dice_hidden(self):
        self._add("muted", "🎲 命运骰已掷下……")

    def dice_reveal(self, line: str):
        self._add("dice", line)

    # --- Web 模式不使用 ---
    def prompt(self, text: str = "") -> str:
        return ""  # 输入由 HTTP 请求驱动, 不会走到这里

    def spinner(self, text: str):
        return None  # 等待态由前端显示

    def wait_key(self, text: str = ""):
        pass
