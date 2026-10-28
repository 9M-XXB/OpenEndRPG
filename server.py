# -*- coding: utf-8 -*-
"""完全开放式RPG · 本地 Web 服务 (Python 标准库实现, 零新增依赖)
启动后先进入"大厅": 新建存档 / 存档选择 / 删除存档 / 配置 API / 退出;
选择存档后才创建对局 (Game)。
路由:
  GET  / , /static/*      页面与静态文件
  GET  /api/state         当前对局状态 (in_game=false 表示在大厅)
  GET  /api/saves         存档列表
  POST /api/saves         新建存档 {name, hero}
  POST /api/saves/delete  删除存档 {name}
  POST /api/enter         进入存档 {name}
  POST /api/say           回合/命令 {text} (需已进入存档)
  GET  /api/config        当前 API 配置(不含 key) + 服务商预设
  POST /api/models        按草稿配置拉取模型列表 (不落盘)
  POST /api/config/test   按草稿配置测试对话 (不落盘)
  POST /api/config        保存 API 配置到本机 config.json
  POST /api/shutdown      保存当前对局并退出服务
回合经全局锁串行化; key 只存本机 config.json。
本文由 ZCode (GLM-5.3-Flash) 编写; 实施决策见 ../规划.md。
"""

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import engine
import llm
import prompts
import state as st
from webui import CollectingUI

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


def _public_config(cfg: dict) -> dict:
    return {"configured": bool(cfg and cfg.get("provider")),
            "provider": (cfg or {}).get("provider", ""),
            "model": (cfg or {}).get("model", ""),
            "base_url": (cfg or {}).get("base_url", ""),
            "api_key_set": bool((cfg or {}).get("api_key"))}


def _providers_public() -> list[dict]:
    return [{"id": p["id"], "name": p["name"], "protocol": p["protocol"],
             "base_url": p.get("base_url", ""), "need_key": p.get("key", False),
             "default_model": p.get("model", "")} for p in llm.PROVIDERS]


def _draft_cfg(partial: dict) -> dict:
    """按前端提交的草稿组装可调用配置 (只用于拉模型/测试, 不落盘)"""
    pid = str(partial.get("provider", "")).strip()
    preset = llm.provider_by_id(pid) or {}
    cfg = {"provider": pid or "mock",
           "protocol": preset.get("protocol", "openai"),
           "temperature": 0.9,
           "api_key": str(partial.get("api_key", "")).strip(),
           "base_url": str(partial.get("base_url", "")).strip(),
           "model": str(partial.get("model", "")).strip()}
    if cfg["provider"] == "mock":
        cfg.update(base_url="mock://local", model="mock-mini", api_key="")
        return cfg
    if not cfg["base_url"]:
        cfg["base_url"] = preset.get("base_url", "")
    if not cfg["model"]:
        cfg["model"] = preset.get("model", "")
    return cfg


class GameServer:
    """cfg = 全局 API 配置; game=None 表示处于大厅(尚未进入任何存档)"""

    def __init__(self, cfg: dict, game=None, on_shutdown=None):
        self.cfg = cfg
        self.game = game
        self.lock = threading.Lock()
        self.on_shutdown = on_shutdown

    # ---------- 大厅: 存档与配置 ----------

    def api_saves(self) -> dict:
        return {"ok": True, "saves": st.list_saves(),
                "config": _public_config(self.cfg)}

    def api_create(self, name: str, hero: str) -> dict:
        name = (name or "").strip()
        hero = (hero or "").strip() or "勇者"
        if not name:
            return {"ok": False, "message": "存档名不能为空"}
        with self.lock:
            try:
                save = st.new_save(name, hero)
                st.save_game(save)
            except st.SaveError as e:
                return {"ok": False, "message": str(e)}
        return {"ok": True}

    def api_delete(self, name: str) -> dict:
        with self.lock:
            if self.game is not None and self.game.save.get("name") == (name or "").strip():
                return {"ok": False, "message": "该存档正在游戏中, 请先退出服务或另选存档"}
            ok = st.delete_save((name or "").strip())
        return {"ok": ok, "message": "" if ok else "存档不存在"}

    def api_enter(self, name: str) -> dict:
        with self.lock:
            try:
                save = st.load_save((name or "").strip())
            except st.SaveError as e:
                return {"ok": False, "message": str(e)}
            self.game = engine.Game(save, self.cfg, CollectingUI())
        return {"ok": True}

    def api_config_get(self) -> dict:
        return {"ok": True, "config": _public_config(self.cfg),
                "providers": _providers_public()}

    def api_models(self, partial: dict) -> dict:
        draft = _draft_cfg(partial)
        try:
            models = llm.list_models(draft)
        except Exception as e:  # 拉取失败不致命, 返回原因
            return {"ok": False, "message": str(e)[:300]}
        return {"ok": True, "models": models[:50]}

    def api_config_test(self, partial: dict) -> dict:
        draft = _draft_cfg(partial)
        if draft["provider"] == "mock":
            return {"ok": True, "reply": "（Mock 模式无需测试, 直接可用）"}
        try:
            reply = llm.test_chat(draft)
        except Exception as e:
            return {"ok": False, "message": str(e)[:300]}
        return {"ok": True, "reply": (reply or "")[:80]}

    def api_config_save(self, body: dict) -> dict:
        cfg = _draft_cfg(body)
        if not cfg["provider"]:
            return {"ok": False, "message": "provider 不能为空"}
        if not cfg["model"]:
            return {"ok": False, "message": "模型名不能为空 (可先点「拉取模型列表」)"}
        try:
            temperature = float(body.get("temperature", self.cfg.get("temperature", 0.9)))
        except (TypeError, ValueError):
            temperature = 0.9
        cfg["temperature"] = temperature
        from rpg import save_config  # 惰性导入, 避免循环依赖
        save_config(cfg)
        self.cfg = cfg
        return {"ok": True, "config": _public_config(cfg)}

    def api_shutdown(self) -> dict:
        with self.lock:
            if self.game is not None:
                st.save_game(self.game.save)
        if self.on_shutdown:
            threading.Thread(target=self.on_shutdown, daemon=True).start()
        return {"ok": True, "message": "已存档, 服务退出。"}

    # ---------- 对局 ----------

    def api_state(self) -> dict:
        if self.game is None:
            return {"ok": True, "in_game": False}
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
            "in_game": True,
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
        if self.game is None:
            return {"ok": False, "kind": "error", "message": "尚未进入存档"}
        text = (text or "").strip()
        if not text:
            return {"ok": False, "kind": "error", "message": "输入为空"}
        ui: CollectingUI = self.game.ui
        with self.lock:
            if text.startswith("/"):
                cmd = text.split()[0].lower()
                if cmd == "/config":
                    return {"ok": True, "kind": "command",
                            "events": [{"k": "warn", "t": "网页模式请回到大厅页使用「配置 API」"
                                                       "（刷新页面即可返回大厅）。"}]}
                if cmd in ("/quit", "/exit", "/q"):
                    return {"ok": True, "kind": "command",
                            "events": [{"k": "info", "t": "网页模式请直接关闭页面；"
                                                         "进度每回合已自动存档。"}]}
                ui.events = []
                cont = self.game.command(text)
                events = ui.events
                if not cont:
                    events = events + [{"k": "info", "t": "（本局已结束；服务保持运行，"
                                                         "刷新页面可回到大厅新建。）"}]
                return {"ok": True, "kind": "command", "events": events,
                        "stage": self.game.save.get("stage", [])}
            ui.events = []
            ok = self.game.turn(text)
            events = ui.events
            if not ok:
                err = next((e["t"] for e in reversed(events) if e["k"] == "error"),
                           "回合生成失败，请换种说法重试。")
                return {"ok": False, "kind": "error", "message": err, "events": events}
            return {
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

    def _state_brief(self) -> dict:
        save = self.game.save
        s = save["state"]
        return {"day": s["day"], "period": s["period"], "location": s["location"],
                "turn": save["turn"]}


# ---------- HTTP 处理 ----------

class Handler(BaseHTTPRequestHandler):
    server_version = "OpenEndRPG/0.3"

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

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            return data if isinstance(data, dict) else {}
        except (ValueError, json.JSONDecodeError):
            return None

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
        if path == "/api/saves":
            return self._json(gs.api_saves())
        if path == "/api/config":
            return self._json(gs.api_config_get())
        self._json({"ok": False, "message": "not found"}, 404)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        gs: GameServer = self.server.gameserver
        data = self._body()
        if data is None:
            return self._json({"ok": False, "message": "请求体不是合法 JSON"}, 400)
        if path == "/api/say":
            return self._json(gs.api_say(str(data.get("text", ""))))
        if path == "/api/saves":
            return self._json(gs.api_create(str(data.get("name", "")), str(data.get("hero", ""))))
        if path == "/api/saves/delete":
            return self._json(gs.api_delete(str(data.get("name", ""))))
        if path == "/api/enter":
            return self._json(gs.api_enter(str(data.get("name", ""))))
        if path == "/api/models":
            return self._json(gs.api_models(data))
        if path == "/api/config/test":
            return self._json(gs.api_config_test(data))
        if path == "/api/config":
            return self._json(gs.api_config_save(data))
        if path == "/api/shutdown":
            return self._json(gs.api_shutdown())
        self._json({"ok": False, "message": "not found"}, 404)

    def _static(self, rel: str):
        full = os.path.abspath(os.path.join(WEB_DIR, os.path.normpath(rel).lstrip("/")))
        if not full.startswith(os.path.abspath(WEB_DIR) + os.sep) or not os.path.isfile(full):
            return self._json({"ok": False, "message": "not found"}, 404)
        ctype = STATIC_TYPES.get(os.path.splitext(full)[1].lower())
        if not ctype:
            return self._json({"ok": False, "message": "unsupported type"}, 404)
        with open(full, "rb") as f:
            self._send(200, f.read(), ctype)


def serve(cfg: dict, game=None, host: str = "127.0.0.1", port: int = 8770) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.gameserver = GameServer(cfg, game=game, on_shutdown=httpd.shutdown)
    return httpd
