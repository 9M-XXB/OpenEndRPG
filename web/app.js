/* 完全开放式RPG · 网页客户端 (M1/M2, 规划.md)
   流程: 启动拉取 /api/state → 输入 POST /api/say → 渲染叙事(打字机)+字画幻灯片(自动翻页)。
   本文由 ZCode (GLM-5.3-Flash) 编写。 */
(function () {
  "use strict";

  var $ = function (sel) { return document.querySelector(sel); };
  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var stage = null;
  var meta = {};

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  // ---------- 渲染 ----------
  function setMeta(patch) {
    Object.assign(meta, patch || {});
    var s = meta.state || {};
    var day = (s.day != null ? s.day : meta.day);
    var period = (s.period != null ? s.period : meta.period);
    var loc = (s.location != null ? s.location : meta.location);
    var turn = (s.turn != null ? s.turn : meta.turn);
    var prov = meta.provider || {};
    $("#meta").textContent =
      "存档「" + (meta.name || "—") + "」 主角:" + (meta.hero || "—") +
      " · 第" + day + "天·" + period + " · " + loc +
      " · 回合" + turn +
      (prov.provider ? " · " + prov.provider + "/" + prov.model : "");
  }

  function renderEvents(events) {
    var box = $("#events");
    box.innerHTML = "";
    (events || []).forEach(function (ev) {
      box.appendChild(el("div", "ev ev-" + ev.k, ev.t));
    });
    return box;
  }

  function setSuggestions(items) {
    var box = $("#suggestions");
    box.innerHTML = "";
    (items || []).forEach(function (s, i) {
      var b = el("button", "chip", (i + 1) + ". " + s);
      b.type = "button";
      b.addEventListener("click", function () { submit(s); });
      box.appendChild(b);
    });
  }

  function typeWriter(node, text) {
    if (reduced || text.length > 1400) { node.textContent = text; return; }
    node.textContent = "";
    var i = 0;
    var step = Math.max(1, Math.round(text.length / 240));
    var t = setInterval(function () {
      i += step;
      node.textContent = text.slice(0, i);
      if (i >= text.length) clearInterval(t);
    }, 16);
  }

  function updateDots(idx, total, caption) {
    var dots = $("#slide-dots");
    dots.innerHTML = "";
    for (var i = 0; i < total; i++) {
      dots.appendChild(el("span", "dot" + (i === idx ? " on" : "")));
    }
    $("#slide-caption").textContent = caption || "";
  }

  function renderTurn(d, opts) {
    opts = opts || {};
    var nar = $("#narrative");
    var txt = (d.narrative || "").replace(/\*\*/g, "");
    if (opts.animate === false || reduced) nar.textContent = txt;
    else typeWriter(nar, txt);
    var box = renderEvents(d.events || []);
    if (d.dice && d.dice.roll) {
      box.prepend(el("div", "ev ev-dice",
        "🎲 命运骰 " + d.dice.roll + "/20 · " + (d.dice.label || "")));
    }
    setSuggestions(d.suggestions || []);
    if (d.stage && d.stage.length) {
      stage.play(d.stage, { all: true });
    }
  }

  function renderHistory(tail) {
    var box = $("#history-list");
    box.innerHTML = "";
    (tail || []).forEach(function (t) {
      var item = el("div", "h-item");
      item.appendChild(el("b", "", "回合 " + t.turn + " · " + (t.player || "（开场）")));
      item.appendChild(el("p", "", (t.narrative || "").replace(/\*\*/g, "")));
      box.appendChild(item);
    });
  }

  // ---------- 交互 ----------
  async function submit(text) {
    if (text == null) text = $("#input").value.trim();
    if (!text) return;
    $("#input").value = "";
    $("#busy").hidden = false;
    $("#input").disabled = true;
    try {
      var r = await fetch("/api/say", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text })
      });
      var d = await r.json();
      if (d.kind === "turn") {
        renderTurn(d);
        if (d.state) setMeta({ state: d.state });
      } else if (d.kind === "command") {
        renderEvents(d.events || []);
        if (d.stage && d.stage.length) stage.play(d.stage, { all: true });
      } else {
        var box = renderEvents([]);
        box.appendChild(el("div", "ev ev-error", d.message || "请求失败"));
      }
    } catch (e) {
      var box2 = renderEvents([]);
      box2.appendChild(el("div", "ev ev-error", "网络错误: " + e.message));
    } finally {
      $("#busy").hidden = true;
      $("#input").disabled = false;
      $("#input").focus();
    }
  }

  // ---------- 启动 ----------
  async function boot() {
    var state = await (await fetch("/api/state")).json();
    var cfg = state.canvas || { w: 12, h: 6, tones: ["灰"] };
    stage = SlideEngine.createStage($("#stage"), {
      W: cfg.w, H: cfg.h, tones: cfg.tones,
      onSlide: updateDots
    });
    setMeta(state.meta || {});
    renderHistory(state.history_tail);
    if (state.last) {
      renderTurn(Object.assign({}, state.last, { events: [] }), { animate: false });
    }
    stage.play(state.stage || [], { instant: true });

    $("#input-form").addEventListener("submit", function (ev) {
      ev.preventDefault();
      submit();
    });
    $("#btn-ledger").addEventListener("click", function () { submit("/status"); });
    $("#btn-history").addEventListener("click", function () {
      var p = $("#history");
      p.hidden = !p.hidden;
    });
    $("#history").querySelector(".close").addEventListener("click", function () {
      $("#history").hidden = true;
    });
  }

  boot().catch(function (e) {
    document.body.appendChild(el("div", "ev ev-error", "启动失败: " + e.message));
  });
})();
