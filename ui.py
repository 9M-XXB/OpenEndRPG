# -*- coding: utf-8 -*-
"""完全开放式RPG · 终端渲染 (rich / plain 双模式)
本文由 ZCode (GLM-5.3-Flash) 编写。
"""

import sys
import time


class UI:
    """rich 模式默认; --plain 时降级为纯 print"""

    def __init__(self, plain: bool = False):
        self.plain = plain
        if not plain:
            try:
                from rich.console import Console
                self.console = Console(highlight=False, markup=False)
            except ImportError:  # rich 未安装也能玩
                self.plain = True

    # --- 基础输出 ---
    def _print(self, text: str = ""):
        if self.plain:
            print(text)
        else:
            self.console.print(text)

    def info(self, text: str):
        self._print(text)

    def muted(self, text: str):
        self._print(f"\033[2m{text}\033[0m" if self.plain else f"[dim]{text}[/dim]")

    def warn(self, text: str):
        self._print(f"\033[33m{text}\033[0m" if self.plain else f"[yellow]{text}[/yellow]")

    def error(self, text: str):
        self._print(f"\033[31m{text}\033[0m" if self.plain else f"[bold red]{text}[/bold red]")

    def success(self, text: str):
        self._print(f"\033[32m{text}\033[0m" if self.plain else f"[bold green]{text}[/bold green]")

    def accent(self, text: str):
        self._print(f"\033[36m{text}\033[0m" if self.plain else f"[bold cyan]{text}[/bold cyan]")

    # --- 游戏画面 ---
    def title(self, text: str):
        if self.plain:
            print("=" * 56 + "\n" + text + "\n" + "=" * 56)
        else:
            from rich.panel import Panel
            self.console.print(Panel(text, style="cyan", expand=False))

    def rule(self):
        if self.plain:
            print("-" * 56)
        else:
            self.console.rule(style="dim")

    def turn_header(self, day: int, period: str, location: str, turn: int):
        line = f"第{day}天 · {period} · {location}    （回合 {turn}）"
        if self.plain:
            print("\n" + "-" * 56 + "\n" + line + "\n" + "-" * 56)
        else:
            from rich.panel import Panel
            self.console.print(Panel(line, expand=False, border_style="dim"))

    def narrative(self, text: str, typewriter: bool = True):
        """剧情正文; 本地打字机效果 (叙事在 JSON 内, 不做网络流式)"""
        if self.plain:
            print(text)
            return
        if not typewriter:
            self.console.print(text)
            return
        delay = min(0.012, 4.0 / max(len(text), 1))
        # 逐字符打印: rich 已关 markup, 直接向其输出流写字符
        console_file = self.console.file
        try:
            for ch in text:
                console_file.write(ch)
                console_file.flush()
                if ch not in "\n " and delay > 0:
                    time.sleep(delay)
            console_file.write("\n")
            console_file.flush()
        except UnicodeEncodeError:
            self.console.print(text)

    def suggestions(self, items: list[str]):
        if not items:
            return
        self.muted("—— 下一步建议（可输入序号直取，也可自由输入任何行动）——")
        for i, s in enumerate(items, 1):
            self._print(f"  {i}. {s}")

    def dice_hidden(self):
        self.muted("🎲 命运骰已掷下……")

    def dice_reveal(self, line: str):
        self.accent("🎲 " + line)

    def prompt(self, text: str = " you > ") -> str:
        try:
            return input(text if self.plain else "\033[36m你 ›\033[0m ")
        except (EOFError, KeyboardInterrupt):
            print()
            return "/quit"

    def spinner(self, text: str):
        """rich 状态动画; plain 模式打印一行提示"""
        if self.plain:
            print(text + "……")
            return None
        return self.console.status(text + "……", spinner="dots")

    def wait_key(self, text: str = "（回车继续）"):
        try:
            input(text)
        except (EOFError, KeyboardInterrupt):
            print()
