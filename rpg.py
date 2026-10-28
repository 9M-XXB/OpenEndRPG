#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""完全开放式RPG（原型 v0.2）
用法:
  python3 rpg.py               # 网页模式（默认）: 起本地服务, 浏览器打开即玩（含字画幻灯片）
  python3 rpg.py --new 存档名   # 网页模式, 直接新建开局
  python3 rpg.py --save 存档名  # 网页模式, 直接继续存档
  python3 rpg.py config        # 重新配置 API（key 密码式输入, 不回显）
  python3 rpg.py --terminal    # 终端模式: 主菜单 + 命令行对话
  python3 rpg.py --terminal --plain   # 终端纯文本渲染（不用 rich）
本项目由 ZCode (GLM-5.3-Flash) 编写; 设计依据见 ../调研笔记.md 与 ../规划.md。
"""

import argparse
import getpass
import json
import os
import sys

import httpx

import engine
import llm
import state as st
from ui import UI

CODE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(CODE_DIR, "config.json")
GAME_TITLE = "完全开放式RPG · 终端原型 v0.1"


# ---------- 配置读写 ----------

def load_config() -> dict | None:
    if not os.path.exists(CONFIG_PATH):
        return None
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    if not cfg.get("provider") or not cfg.get("protocol"):
        return None
    cfg.setdefault("temperature", 0.9)
    return cfg


def save_config(cfg: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)


# ---------- 配置向导 (F1) ----------

def _ask(ui: UI, label: str, default: str = "", secret: bool = False) -> str:
    tail = f"（回车 = {default}）" if default else ("（可留空）" if not secret else "（输入不回显, 密码式）")
    ui.info(f"{label}{tail}")
    try:
        if secret:
            val = getpass.getpass("  > ").strip()  # 不回显, 防偷窥/防入终端历史
        else:
            val = input("  > ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    return val or default


def _pick(ui: UI, options: list[str], title: str) -> int:
    ui.info(title)
    for i, o in enumerate(options, 1):
        ui.info(f"  {i:2d}. {o}")
    while True:
        try:
            raw = input("  序号 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw) - 1
        ui.warn("请输入列表中的序号")


def run_wizard(ui: UI) -> dict:
    ui.title("API 配置向导")
    ui.muted("本游戏兼容任何 OpenAI 格式的接口（含 Ollama/LM Studio 本地模型）；key 只保存在本机 config.json。")

    idx = _pick(ui, [p["name"] for p in llm.PROVIDERS], "选择服务商：")
    preset = llm.PROVIDERS[idx]

    cfg = {"provider": preset["id"], "protocol": preset["protocol"],
           "temperature": 0.9, "api_key": "", "base_url": preset["base_url"], "model": preset["model"]}

    if preset["id"] == "mock":
        save_config(cfg)
        ui.success("已选择 Mock 离线测试模式（无需 API，剧情为脚本演示）。")
        return cfg

    if preset["id"] == "custom" or not preset["base_url"]:
        cfg["base_url"] = _ask(ui, "base_url（以 /v1 结尾的 OpenAI 兼容地址）").rstrip("/")
        if not cfg["base_url"]:
            ui.error("base_url 不能为空")
            return run_wizard(ui)
    elif preset["id"] in ("ollama", "lmstudio"):
        cfg["base_url"] = _ask(ui, "base_url", preset["base_url"]).rstrip("/")

    if preset["key"]:
        cfg["api_key"] = _ask(ui, "API key", secret=True)

    # 模型: 优先在线拉取列表
    models = []
    if cfg["base_url"]:
        try:
            with ui.console.status("正在拉取模型列表……") if not ui.plain else _null_ctx():
                models = llm.list_models(cfg)
        except (llm.LLMError, httpx.HTTPError):
            models = []
    if models:
        shown = models[:30]
        ui.info(f"拉取到 {len(models)} 个模型" + ("（仅显示前 30）" if len(models) > 30 else "") + "：")
        for i, m in enumerate(shown, 1):
            ui.info(f"  {i:2d}. {m}")
        ui.info("  直接回车则手输模型名")
        raw = input("  序号或模型名 > ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(shown):
            cfg["model"] = shown[int(raw) - 1]
        elif raw:
            cfg["model"] = raw
    if not cfg["model"]:
        cfg["model"] = _ask(ui, "模型名")
        if not cfg["model"]:
            ui.error("模型名不能为空")
            return run_wizard(ui)

    # 测试对话
    while True:
        ui.muted(f"测试对话中……（{cfg['provider']} / {cfg['model']}）")
        try:
            out = llm.test_chat(cfg)
            ui.success(f"连接成功！模型回复: {out}")
            break
        except (llm.LLMError, httpx.HTTPError) as e:
            ui.error(f"测试失败: {e}")
            if _pick(ui, ["重试测试", "重选服务商", "手改模型名", "仍然保存退出"], "怎么办？") == 0:
                continue
            break
    save_config(cfg)
    ui.success(f"配置已保存到 {CONFIG_PATH}")
    return cfg


class _null_ctx:
    def __enter__(self): return self
    def __exit__(self, *a): return False


# ---------- 菜单 (F2) ----------

def main_menu(ui: UI, cfg: dict):
    while True:
        ui.title(GAME_TITLE)
        saves = st.list_saves()
        ui.info(f"配置: {cfg.get('provider')}/{cfg.get('model')}    存档目录: {st.saves_dir()}")
        ui.info("")
        ui.info("  1. 新建存档（打魔王的故事，从这里开始）")
        ui.info("  2. 继续存档")
        ui.info("  3. 删除存档")
        ui.info("  4. 重新配置 API")
        ui.info("  5. 退出")
        try:
            choice = input("选择 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if choice == "1":
            name = _ask(ui, "存档名")
            if not name:
                continue
            hero = _ask(ui, "主角名", default="勇者")
            try:
                save = st.new_save(name, hero)
                st.save_game(save)
            except st.SaveError as e:
                ui.error(str(e))
                continue
            engine.Game(save, cfg, ui).run()

        elif choice == "2":
            if not saves:
                ui.warn("还没有存档，先新建一个。")
                continue
            idx = _pick(ui, [f"{s['name']}（第{s['day']}天 · {s['turn']}回合 · {s['updated_at']}）" for s in saves],
                        "选择存档：")
            try:
                save = st.load_save(saves[idx]["name"])
            except st.SaveError as e:
                ui.error(str(e))
                continue
            engine.Game(save, cfg, ui).run()

        elif choice == "3":
            if not saves:
                ui.warn("没有可删除的存档。")
                continue
            idx = _pick(ui, [s["name"] for s in saves], "删除哪个存档？")
            name = saves[idx]["name"]
            if input(f"  确认删除「{name}」？(y/N) > ").strip().lower() == "y":
                st.delete_save(name)
                ui.success("已删除。")

        elif choice == "4":
            cfg = run_wizard(ui)

        elif choice in ("5", "q", "Q", "exit", "quit"):
            return


# ---------- 网页模式 (默认模式; M1 基座, 规划.md) ----------

def _pick_port(host: str, preferred: int) -> int:
    """首选端口被占用时自动改用系统分配的空闲端口; preferred=0 表示总是随机"""
    import socket
    if preferred != 0:
        s = socket.socket()
        try:
            s.bind((host or "127.0.0.1", preferred))
            s.close()
            return preferred
        except OSError:
            s.close()
    s = socket.socket()
    s.bind((host or "127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def run_server(args, ui: UI, cfg: dict):
    import server as webserver
    from webui import CollectingUI

    game = None
    if args.new:
        save = st.new_save(args.new, args.hero)
        st.save_game(save)
        game = engine.Game(save, cfg, CollectingUI())
    elif args.save:
        try:
            save = st.load_save(args.save)
        except st.SaveError as e:
            ui.error(str(e))
            sys.exit(1)
        game = engine.Game(save, cfg, CollectingUI())

    port = _pick_port(args.host, args.port)
    if port != args.port:
        ui.info(f"端口 {args.port} 被占用，已自动改用空闲端口 {port}。")
    try:
        httpd = webserver.serve(cfg, game=game, host=args.host, port=port)
    except OSError as e:
        ui.error(f"服务启动失败（{e}）")
        sys.exit(1)
    shown_host = "127.0.0.1" if args.host in ("0.0.0.0", "") else args.host
    ui.success(f"网页模式已启动：http://{shown_host}:{port}   （Ctrl+C 退出并自动存档）")
    if game is None:
        ui.info("启动到大厅页：在浏览器中新建存档、选择存档、配置 API 或退出。")
    if args.host == "0.0.0.0":
        ui.muted("已监听全部网卡，同一局域网的设备可用本机 IP 访问。")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    game = getattr(httpd.gameserver, "game", None)
    if game is not None:
        st.save_game(game.save)
    ui.info("服务已关闭。")


# ---------- 入口 ----------

def main():
    ap = argparse.ArgumentParser(description=GAME_TITLE)
    ap.add_argument("cmd", nargs="?", choices=["config"], help="config = 重新配置 API")
    ap.add_argument("--terminal", action="store_true",
                    help="终端对话模式（不加分隔即为网页模式）")
    ap.add_argument("--server", action="store_true", help=argparse.SUPPRESS)  # 兼容旧用法: 网页模式本已是默认
    ap.add_argument("--host", default="127.0.0.1", help="网页模式监听地址 (局域网联机用 0.0.0.0)")
    ap.add_argument("--port", type=int, default=8770,
                    help="网页模式首选端口; 被占用时自动改用空闲端口, 0 = 总是随机")
    ap.add_argument("--save", metavar="存档名", help="直接继续指定存档")
    ap.add_argument("--new", metavar="存档名", help="直接新建指定存档")
    ap.add_argument("--hero", metavar="主角名", default="勇者")
    ap.add_argument("--plain", action="store_true", help="（仅终端模式）纯文本渲染")
    args = ap.parse_args()

    ui = UI(plain=args.plain)
    cfg = load_config()

    if args.terminal:  # 终端模式: 菜单/命令行对话
        if args.cmd == "config" or cfg is None:
            cfg = run_wizard(ui)
            if args.cmd == "config" and not args.save and not args.new:
                return
        if args.new:
            save = st.new_save(args.new, args.hero)
            st.save_game(save)
            engine.Game(save, cfg, ui).run()
            return
        if args.save:
            try:
                save = st.load_save(args.save)
            except st.SaveError as e:
                ui.error(str(e))
                sys.exit(1)
            engine.Game(save, cfg, ui).run()
            return
        main_menu(ui, cfg)
        return

    # 默认: 网页模式
    if args.cmd == "config" or cfg is None:
        run_wizard(ui)
        if args.cmd == "config":
            return
        cfg = load_config()
    run_server(args, ui, cfg)


if __name__ == "__main__":
    main()
