# -*- coding: utf-8 -*-
"""完全开放式RPG · 本地 Web 服务 (Python 标准库实现, 零新增依赖)
路由: GET / 与 /static/* (前端) · GET /api/state · POST /api/say
回合经全局锁串行化; LLM 调用发生在请求线程内; API key 始终只在本机 config.json。
实施决策见 ../规划.md §0 (同步 POST, WebSocket 推迟到 M3 多人)。
本文由 ZCode (GLM-5.3-Flash) 编写。
"""

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import prompts
from webui import CollectingUI

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


class GameServer:
    """包装单个 Game; 线程锁串行化回合, 独立 GET 不受 LLM 长调用阻塞"""

    def __init__(self, game):
        self.game = game
        self.lock = threading.Lock()

    # ---------- API ----------

    def api_state(self) -> dict:
        save = self.game.save
        s = save["state"]
        last = None
        if save.get("history"):
            t = save["history"][-1]
            label = next((d.get("label") for d in save.get("dice_log", [])
                          if d.get("turn") == t.get("turn")), "")
            last = {"turn": t.get("turn"), "player": t.get("player"),
                    "narrative": t.get("narrative", ""),
                    "suggestions": t.get("suggestions", []),
                    "dice": {"roll": t.get("dice"), "label": label}}
        elif save["turn"] == 0:
            last = {"turn": 0, "player": "", "narrative": prompts.OPENING_TEXT,
                    "suggestions": [], "dice": None}
        return {
            "ok": True,
            "meta": {"name": save["name"], "hero": save["hero"],
                     "day": s["day"], "period": s["period"], "location": s["location"],
                     "turn": save["turn"], "provider": save.get("provider", {})},
            "canvas": {"w": prompts.CANVAS_W, "h": prompts.CANVAS_H, "tones": prompts.TONES},
            "stage": save.get("stage", []),
            "last": last,
            "history_tail": [{"turn": t.get("turn"), "player": t.get("player"),
                              "narrative": t.get("narrative", "")}
                             for t in save.get("history", [])[-8:]],
        }

    def api_say(self, text: str) -> dict:
        text = (text or "").strip()
        if not text:
            return {"ok": False, "kind": "error", "message": "输入为空"}
        ui: CollectingUI = self.game.ui
        with self.lock:
            if text.startswith("/"):
                cmd = text.split()[0].lower()
                if cmd == "/config":
                    return {"ok": True, "kind": "command",
                            "events": [{"k": "warn", "t": "网页模式不支持 /config；请在终端运行 "
                                                            "python3 rpg.py config 后重启服务。"}]}
                if cmd in ("/quit", "/exit", "/q"):
                    return {"ok": True, "kind": "command",
                            "events": [{"k": "info", "t": "网页模式请直接关闭页面；进度每回合已自动存档。"}]}
                ui.events = []
                cont = self.game.command(text)
                events = ui.events
                if not cont:
                    events = events + [{"k": "info", "t": "（本局已结束；服务保持运行，刷新页面可新建。）"}]
                return {"ok": True, "kind": "command", "events": events,
                        "stage": self.game.save.get("stage", [])}
            ui.events = []
            ok = self.game.turn(text)
            events = ui.events
            if not ok:
                err = next((e["t"] for e in reversed(events) if e["k"] == "error"),
                           "回合生成失败，请换种说法重试。")
                return {"ok": False, "kind": "error", "message": err, "events": events}
            result = {
                "ok": True,
                "kind": "turn",
                "narrative": next((e["t"] for e in events if e["k"] == "narrative"), ""),
                "suggestions": next((e.get("items", []) for e in events if e["k"] == "suggestions"), []),
                "dice": next(({"roll": d.get("roll"), "label": d.get("label")}
                              for d in reversed(self.game.save.get("dice_log", []))), None),
                "stage": self.game.save.get("stage", []),
                "events": [e for e in events if e["k"] in ("muted", "info", "warn", "header")],
                "state": self._state_brief(),
            }
            return result

    def _state_brief(self) -> dict:
        save = self.game.save
        s = save["state"]
        return {"day": s["day"], "period": s["period"], "location": s["location"],
                "turn": save["turn"]}


# ---------- HTTP 处理 ----------

class Handler(BaseHTTPRequestHandler):
    server_version = "OpenEndRPG/0.2"

    def log_message(self, fmt, *args):  # 静默访问日志
        pass

    # ----- 工具 -----
    def _send(self, code: int, body: bytes, ctype: str = "application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    # ----- 路由 -----
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        gs: GameServer = self.server.gameserver
        if path in ("/", "/index.html"):
            return self._static("index.html")
        if path.startswith("/static/"):
            return self._static(path[len("/static/"):])
        if path == "/api/state":
            return self._json(gs.api_state())
        self._json({"ok": False, "message": "not found"}, 404)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        gs: GameServer = self.server.gameserver
        if path != "/api/say":
            return self._json({"ok": False, "message": "not found"}, 404)
        try:
            length = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            text = str(data.get("text", ""))
        except (ValueError, json.JSONDecodeError):
            return self._json({"ok": False, "message": "请求体不是合法 JSON"}, 400)
        self._json(gs.api_say(text))

    def _static(self, rel: str):
        full = os.path.abspath(os.path.join(WEB_DIR, os.path.normpath(rel).lstrip("/")))
        if not full.startswith(os.path.abspath(WEB_DIR) + os.sep) or not os.path.isfile(full):
            return self._json({"ok": False, "message": "not found"}, 404)
        ctype = STATIC_TYPES.get(os.path.splitext(full)[1].lower())
        if not ctype:
            return self._json({"ok": False, "message": "unsupported type"}, 404)
        with open(full, "rb") as f:
            self._send(200, f.read(), ctype)


def serve(game, host: str = "127.0.0.1", port: int = 8770) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.gameserver = GameServer(game)
    return httpd
