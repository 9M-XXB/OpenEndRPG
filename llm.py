# -*- coding: utf-8 -*-
"""完全开放式RPG · LLM 接入层
三类协议 × 12 预设, 统一 chat()/list_models() 接口; httpx 直连, 零 SDK 依赖。
本文由 ZCode (GLM-5.3-Flash) 编写。
"""

import json
import os

import httpx

TIMEOUT = httpx.Timeout(20.0, read=300.0)
UA = {"User-Agent": "open-rpg-terminal/0.1"}


class LLMError(Exception):
    pass


def _hint(status: int) -> str:
    if status in (401, 403):
        return "（API key 无效或无权限，可用 `python3 rpg.py config` 重新配置）"
    if status == 429:
        return "（触发限流/欠费，稍后再试或更换服务商）"
    if status == 404:
        return "（接口或模型名不存在，检查 base_url 与模型名）"
    return ""


# ---------- 服务商预设 ----------
# protocol: openai | anthropic | google | mock

PROVIDERS = [
    {"id": "openai",      "name": "OpenAI",              "protocol": "openai",    "base_url": "https://api.openai.com/v1",                    "model": "gpt-4o-mini",           "key": True},
    {"id": "deepseek",    "name": "DeepSeek 深度求索",    "protocol": "openai",    "base_url": "https://api.deepseek.com/v1",                  "model": "deepseek-chat",         "key": True},
    {"id": "kimi",        "name": "Kimi / Moonshot",     "protocol": "openai",    "base_url": "https://api.moonshot.cn/v1",                   "model": "moonshot-v1-8k",        "key": True},
    {"id": "zhipu",       "name": "智谱 GLM",            "protocol": "openai",    "base_url": "https://open.bigmodel.cn/api/paas/v4",         "model": "glm-4-flash",           "key": True},
    {"id": "qwen",        "name": "通义千问 Qwen（兼容模式）", "protocol": "openai", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus",        "key": True},
    {"id": "openrouter",  "name": "OpenRouter（聚合）",   "protocol": "openai",    "base_url": "https://openrouter.ai/api/v1",                 "model": "openai/gpt-4o-mini",    "key": True},
    {"id": "groq",        "name": "Groq",                "protocol": "openai",    "base_url": "https://api.groq.com/openai/v1",               "model": "llama-3.3-70b-versatile", "key": True},
    {"id": "siliconflow", "name": "SiliconFlow 硅基流动", "protocol": "openai",    "base_url": "https://api.siliconflow.cn/v1",                "model": "Qwen/Qwen2.5-7B-Instruct", "key": True},
    {"id": "ollama",      "name": "Ollama（本地, 免key）", "protocol": "openai",   "base_url": "http://127.0.0.1:11434/v1",                    "model": "qwen2.5:7b",            "key": False},
    {"id": "lmstudio",    "name": "LM Studio（本地, 免key）", "protocol": "openai", "base_url": "http://127.0.0.1:1234/v1",                    "model": "",                      "key": False},
    {"id": "anthropic",   "name": "Claude (Anthropic)",  "protocol": "anthropic", "base_url": "https://api.anthropic.com",                    "model": "claude-sonnet-4-5",     "key": True},
    {"id": "gemini",      "name": "Gemini (Google)",     "protocol": "google",    "base_url": "https://generativelanguage.googleapis.com",    "model": "gemini-2.0-flash",      "key": True},
    {"id": "custom",      "name": "自定义 OpenAI 兼容端点", "protocol": "openai",   "base_url": "",                                            "model": "",                      "key": True},
    {"id": "mock",        "name": "Mock（离线测试, 免key）", "protocol": "mock",    "base_url": "mock://local",                                "model": "mock-mini",             "key": False},
]


def provider_by_id(pid: str) -> dict | None:
    return next((p for p in PROVIDERS if p["id"] == pid), None)


# ---------- mock 离线 provider ----------

class _Mock:
    calls = 0
    PERIOD_FLOW = ["上午", "下午", "傍晚", "夜晚", "清晨"]

    def _template(self, user: str, corrupt: bool) -> str:
        self.calls += 1
        if corrupt:
            return "抱歉，我无法以 JSON 以外的格式思考……{这不是合法JSON"
        # 只取【玩家行动】一行, 避免历史上下文/脚手架影响模板判定
        action = user
        if "【玩家行动】" in user:
            action = user.split("【玩家行动】", 1)[1].split("\n", 1)[0]
        p = self.PERIOD_FLOW[(self.calls - 1) % 5]
        days = 3 if "三天后" in action else 0
        import json as _j
        return _j.dumps({
            "narrative": f"【Mock 测试剧情 #{self.calls}】世界回应了你的行动：「{action[:60]}」。"
                         f"远处的山道上扬起尘土，一名信使快马而过，留下一句没头没尾的话：北边的界碑又烧了。"
                         + (f"你日夜兼程三天，" if days else "时间流逝，") + f"转眼到了{p}。",
            "time_advance": {"days": days, "period": p},
            "state_updates": {
                "facts_add": [f"测试事实#{self.calls}：信使再传北境警讯"],
                "facts_remove": [],
                "npc_upserts": [{"name": "神秘信使", "status": "快马北去", "relation": "陌生",
                                 "location": "北方官道", "note": f"第{self.calls}次出现"}],
                "items_add": [f"信使掉落的铜哨#{self.calls}"],
                "location": "官道旁的茶棚",
            },
            "summary": f"（摘要更新到第{self.calls}回合）主角一路北上，途中屡遇北境警讯，神秘信使反复出现。",
            "suggestions": ["追问茶棚老板信使的来历", "检查铜哨上的刻痕", "继续向北赶路"],
        }, ensure_ascii=False)

    def chat(self, cfg, system, user, on_delta=None) -> str:
        action = user.split("【玩家行动】", 1)[1] if "【玩家行动】" in user else user
        corrupt = "[ corrupt ]" in action and "修复请求" not in user
        text = self._template(user, corrupt)
        if on_delta:
            for ch in text:
                on_delta(ch)
        return text

    def list_models(self, cfg):
        return ["mock-mini", "mock-large"]


_mock = _Mock()


# ---------- OpenAI 兼容协议 ----------

def _openai_chat(cfg, system, user, on_delta=None) -> str:
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {cfg.get('api_key','')}", **UA}
    body = {"model": cfg["model"], "temperature": cfg.get("temperature", 0.9),
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if on_delta is not None:
        body["stream"] = True
        buf = []
        with httpx.stream("POST", url, headers=headers, json=body, timeout=TIMEOUT) as r:
            if r.status_code != 200:
                raise LLMError(f"HTTP {r.status_code}: {r.read().decode('utf-8', 'replace')[:300]} {_hint(r.status_code)}")
            for line in r.iter_lines():
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    delta = json.loads(payload)["choices"][0]["delta"].get("content")
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
                if delta:
                    buf.append(delta)
                    on_delta(delta)
        return "".join(buf)
    r = httpx.post(url, headers=headers, json=body, timeout=TIMEOUT)
    if r.status_code != 200:
        raise LLMError(f"HTTP {r.status_code}: {r.text[:300]} {_hint(r.status_code)}")
    try:
        return r.json()["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        raise LLMError(f"响应格式异常: {e}")


def _openai_models(cfg) -> list[str]:
    url = cfg["base_url"].rstrip("/") + "/models"
    r = httpx.get(url, headers={"Authorization": f"Bearer {cfg.get('api_key','')}", **UA}, timeout=30)
    if r.status_code != 200:
        raise LLMError(f"HTTP {r.status_code}: {r.text[:200]} {_hint(r.status_code)}")
    return sorted(m.get("id", "") for m in r.json().get("data", []) if m.get("id"))


# ---------- Anthropic 协议 ----------

def _anthropic_chat(cfg, system, user, on_delta=None) -> str:
    url = cfg["base_url"].rstrip("/") + "/v1/messages"
    headers = {"x-api-key": cfg.get("api_key", ""), "anthropic-version": "2023-06-01", **UA}
    body = {"model": cfg["model"], "max_tokens": 4096, "temperature": cfg.get("temperature", 0.9),
            "system": system, "messages": [{"role": "user", "content": user}]}
    if on_delta is not None:
        body["stream"] = True
        buf = []
        with httpx.stream("POST", url, headers=headers, json=body, timeout=TIMEOUT) as r:
            if r.status_code != 200:
                raise LLMError(f"HTTP {r.status_code}: {r.read().decode('utf-8', 'replace')[:300]} {_hint(r.status_code)}")
            for line in r.iter_lines():
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                try:
                    evt = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                if evt.get("type") == "content_block_delta" and evt.get("delta", {}).get("type") == "text_delta":
                    t = evt["delta"].get("text", "")
                    buf.append(t)
                    on_delta(t)
                elif evt.get("type") == "message_stop":
                    break
        return "".join(buf)
    r = httpx.post(url, headers=headers, json=body, timeout=TIMEOUT)
    if r.status_code != 200:
        raise LLMError(f"HTTP {r.status_code}: {r.text[:300]} {_hint(r.status_code)}")
    return "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")


def _anthropic_models(cfg) -> list[str]:
    r = httpx.get(cfg["base_url"].rstrip("/") + "/v1/models",
                  headers={"x-api-key": cfg.get("api_key", ""), "anthropic-version": "2023-06-01", **UA}, timeout=30)
    if r.status_code != 200:
        raise LLMError(f"HTTP {r.status_code}: {r.text[:200]} {_hint(r.status_code)}")
    return sorted(m.get("id", "") for m in r.json().get("data", []) if m.get("id"))


# ---------- Google Gemini 协议 ----------

def _google_url(cfg, method: str) -> str:
    return (f"{cfg['base_url'].rstrip('/')}/v1beta/models/{cfg['model']}:{method}"
            f"?key={cfg.get('api_key','')}")


def _google_body(system, user, temperature):
    return {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": 8192},
    }


def _google_chat(cfg, system, user, on_delta=None) -> str:
    headers = {**UA}
    if on_delta is not None:
        buf = []
        with httpx.stream("POST", _google_url(cfg, "streamGenerateContent") + "&alt=sse",
                          headers=headers, json=_google_body(system, user, cfg.get("temperature", 0.9)),
                          timeout=TIMEOUT) as r:
            if r.status_code != 200:
                raise LLMError(f"HTTP {r.status_code}: {r.read().decode('utf-8', 'replace')[:300]} {_hint(r.status_code)}")
            for line in r.iter_lines():
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                try:
                    evt = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                for part in evt.get("candidates", [{}])[0].get("content", {}).get("parts", []):
                    t = part.get("text", "")
                    if t:
                        buf.append(t)
                        on_delta(t)
        return "".join(buf)
    r = httpx.post(_google_url(cfg, "generateContent"), headers=headers,
                   json=_google_body(system, user, cfg.get("temperature", 0.9)), timeout=TIMEOUT)
    if r.status_code != 200:
        raise LLMError(f"HTTP {r.status_code}: {r.text[:300]} {_hint(r.status_code)}")
    parts = r.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts)


def _google_models(cfg) -> list[str]:
    r = httpx.get(f"{cfg['base_url'].rstrip('/')}/v1beta/models?key={cfg.get('api_key','')}",
                  headers=UA, timeout=30)
    if r.status_code != 200:
        raise LLMError(f"HTTP {r.status_code}: {r.text[:200]} {_hint(r.status_code)}")
    return sorted(m["name"].split("/")[-1] for m in r.json().get("models", []) if m.get("name"))


# ---------- 统一接口 ----------

def chat(cfg: dict, system: str, user: str, on_delta=None) -> str:
    proto = cfg.get("protocol", "openai")
    try:
        if proto == "mock":
            return _mock.chat(cfg, system, user, on_delta)
        if proto == "openai":
            return _openai_chat(cfg, system, user, on_delta)
        if proto == "anthropic":
            return _anthropic_chat(cfg, system, user, on_delta)
        if proto == "google":
            return _google_chat(cfg, system, user, on_delta)
    except httpx.ConnectError as e:
        raise LLMError(f"无法连接 {cfg.get('base_url')}：{e.__class__.__name__}（本地服务请确认已启动）") from e
    except httpx.TimeoutException as e:
        raise LLMError("请求超时（网络或服务无响应）") from e
    raise LLMError(f"未知协议: {proto}")


def list_models(cfg: dict) -> list[str]:
    proto = cfg.get("protocol", "openai")
    if proto == "mock":
        return _mock.list_models(cfg)
    if proto == "openai":
        return _openai_models(cfg)
    if proto == "anthropic":
        return _anthropic_models(cfg)
    if proto == "google":
        return _google_models(cfg)
    raise LLMError(f"未知协议: {proto}")


def test_chat(cfg: dict) -> str:
    out = chat(cfg, "你是连通性测试器。无论对方说什么，只回复四个字：连接成功", "ping")
    return (out or "").strip()[:50]


# ---------- 结构化回合输出 + JSON 自修复 ----------

def extract_json(text: str):
    """从输出中提取 JSON 对象: 剥代码栅栏、截取首个 { 到末个 }"""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1] if t.count("```") >= 2 else t.lstrip("`")
        if t.startswith("json"):
            t = t[4:]
    start, end = t.find("{"), t.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("输出中找不到 JSON 对象")
    return json.loads(t[start:end + 1])


def validate_turn(obj: dict) -> str | None:
    """校验回合 JSON; 返回错误描述或 None"""
    if not isinstance(obj, dict):
        return "顶层不是 JSON 对象"
    if not isinstance(obj.get("narrative"), str) or not obj["narrative"].strip():
        return "缺少 narrative 字符串"
    ta = obj.get("time_advance")
    if not isinstance(ta, dict) or not isinstance(ta.get("days"), int):
        return "time_advance.days 缺失或不是整数"
    su = obj.get("state_updates")
    if not isinstance(su, dict):
        return "缺少 state_updates 对象"
    if not isinstance(obj.get("summary"), str) or not obj["summary"].strip():
        return "缺少 summary 字符串"
    sug = obj.get("suggestions")
    if not isinstance(sug, list) or not all(isinstance(s, str) for s in sug):
        return "suggestions 必须是字符串数组"
    return None


def complete_turn_json(cfg: dict, system: str, user: str, max_repairs: int = 2) -> dict:
    """调用 LLM 生成回合 JSON; 解析/校验失败带着错误重试修复"""
    last_err = ""
    for attempt in range(1 + max_repairs):
        if attempt == 0:
            prompt = user
        else:
            prompt = user + "\n\n———\n【修复请求】你上一次的输出无法解析（错误: " + last_err + \
                     "）。请重新只输出一个合法 JSON 对象，严格遵守字段约定，不要任何解释。"
        raw = chat(cfg, system, prompt)
        try:
            obj = extract_json(raw)
        except (ValueError, json.JSONDecodeError) as e:
            last_err = f"JSON 解析失败: {e}"
            continue
        err = validate_turn(obj)
        if err is None:
            obj.setdefault("_raw", raw)
            return obj
        last_err = err
    raise LLMError(f"模型输出始终不是合法的回合 JSON（{last_err}）。可输入任意内容重试，或 /config 换模型。")
