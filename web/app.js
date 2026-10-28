/* 完全开放式RPG · 网页客户端 (大厅 + 游戏, ../规划.md §8/§10)
   启动 → /api/state: in_game=false 进大厅(新建/选择/删除/配置API/退出);
   选择存档后 POST /api/enter 切换到游戏视图。
   本文由 ZCode (GLM-5.3-Flash) 编写。 */
(function () {
  "use strict";

  var $ = function (sel) { return document.querySelector(sel); };
  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var stage = null;
  var meta = {};
  var providers = [];
  var gameBound = false;

  // 故事分页状态
  var pages = [];
  var pageIdx = 0;
  var typing = null;
  var PAGE_MAX = 620;

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  async function post(url, body) {
    var r = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {})
    });
    return r.json();
  }

  // ================= 大厅 =================

  function lobbyMsg(text, isError) {
    var box = $("#lobby-msg");
    box.innerHTML = "";
    box.appendChild(el("div", "ev" + (isError ? " ev-error" : ""), text));
  }

  function currentProvider() {
    var id = $("#cfg-provider").value;
    for (var i = 0; i < providers.length; i++) {
      if (providers[i].id === id) return providers[i];
    }
    return null;
  }

  function onProviderChange() {
    var p = currentProvider();
    if (!p) return;
    $("#cfg-base").placeholder = p.base_url ? "留空用预设：" + p.base_url : "必填：以 /v1 结尾";
    $("#cfg-model").placeholder = p.default_model ? "留空用预设：" + p.default_model : "必填：模型名";
    $("#cfg-key").placeholder = p.need_key ? "API key（密码式, 只存本机）" : "本地模型可留空";
  }

  function renderSaveList(saves) {
    var box = $("#save-list");
    box.innerHTML = "";
    if (!(saves || []).length) {
      box.appendChild(el("div", "ev", "（还没有存档——先在上面新建一个）"));
      return;
    }
    saves.forEach(function (s) {
      var row = el("div", "save-row");
      row.appendChild(el("span", "save-name grow",
        s.name + "（第" + s.day + "天 · " + s.turn + "回合 · " + s.updated_at + "）"));
      var enter = el("button", "mini", "进入");
      enter.type = "button";
      enter.addEventListener("click", function () { enterSave(s.name); });
      var del = el("button", "mini danger", "删除");
      del.type = "button";
      del.addEventListener("click", async function () {
        if (!window.confirm("确认删除「" + s.name + "」？不可恢复。")) return;
        var r = await post("/api/saves/delete", { name: s.name });
        if (!r.ok) lobbyMsg(r.message || "删除失败", true);
        loadLobby();
      });
      row.appendChild(enter);
      row.appendChild(del);
      box.appendChild(row);
    });
  }

  async function loadLobby() {
    var cfg = await (await fetch("/api/config")).json();
    providers = cfg.providers || [];
    var sel = $("#cfg-provider");
    sel.innerHTML = "";
    providers.forEach(function (p) { sel.appendChild(new Option(p.name, p.id)); });
    sel.value = cfg.config.provider || "mock";
    onProviderChange();
    $("#cfg-base").value = cfg.config.base_url || "";
    $("#cfg-key").value = "";
    $("#cfg-key").placeholder = cfg.config.api_key_set
      ? "已保存（留空则沿用已存 key）" : $("#cfg-key").placeholder;
    $("#cfg-line").textContent = cfg.config.configured
      ? "当前：" + cfg.config.provider + " / " + cfg.config.model : "未配置";
    var saves = await (await fetch("/api/saves")).json();
    renderSaveList(saves.saves);
  }

  function draftFromForm() {
    return { provider: $("#cfg-provider").value,
             base_url: $("#cfg-base").value.trim(),
             api_key: $("#cfg-key").value,
             model: $("#cfg-model").value.trim() };
  }

  function cfgMsg(text, isError) {
    var box = $("#cfg-msg");
    box.innerHTML = "";
    box.appendChild(el("div", "ev" + (isError ? " ev-error" : ""), text));
  }

  async function pullModels() {
    cfgMsg("正在拉取模型列表……");
    var r = await post("/api/models", draftFromForm());
    if (!r.ok) { cfgMsg("拉取失败：" + r.message, true); return; }
    var sel = $("#cfg-models");
    sel.innerHTML = "";
    (r.models || []).forEach(function (m) { sel.appendChild(new Option(m, m)); });
    if ((r.models || []).length) {
      sel.hidden = false;
      sel.onchange = function () { $("#cfg-model").value = sel.value; };
      cfgMsg("拉取到 " + r.models.length + " 个模型，下拉选择或直接手填。");
    } else {
      sel.hidden = true;
      cfgMsg("服务商未返回模型列表，请手填模型名。");
    }
  }

  async function testConfig() {
    cfgMsg("测试对话中……");
    var r = await post("/api/config/test", draftFromForm());
    if (r.ok) cfgMsg("连接成功，模型回复：" + r.reply);
    else cfgMsg("测试失败：" + r.message, true);
  }

  async function saveConfig() {
    var r = await post("/api/config", draftFromForm());
    if (r.ok) {
      $("#cfg-line").textContent = "当前：" + r.config.provider + " / " + r.config.model;
      $("#cfg-key").value = "";
      $("#cfg-key").placeholder = "已保存（留空则沿用已存 key）";
      cfgMsg("已保存到本机 config.json。");
    } else {
      cfgMsg(r.message || "保存失败", true);
    }
  }

  async function enterSave(name) {
    lobbyMsg("正在进入「" + name + "」……");
    var r = await post("/api/enter", { name: name });
    if (!r.ok) { lobbyMsg(r.message || "进入失败", true); return; }
    var state = await (await fetch("/api/state")).json();
    enterGame(state);
  }

  async function exitServer() {
    if (!window.confirm("确认退出？将保存当前对局并关闭服务。")) return;
    lobbyMsg("正在退出……");
    await post("/api/shutdown", {});
    document.querySelector("main").innerHTML = "";
    var bye = el("div", "lobby-card");
    bye.appendChild(el("b", "", "服务已退出，已自动存档。可关闭此页面。"));
    document.querySelector("main").appendChild(bye);
  }

  // ================= 游戏 =================

  // 元信息
  function setMeta(patch) {
    Object.assign(meta, patch || {});
    var s = meta.state || meta;
    var prov = meta.provider || {};
    $("#meta").textContent =
      "存档「" + (meta.name || "—") + "」 主角:" + (meta.hero || "—") +
      " · 第" + s.day + "天·" + s.period + " · " + s.location +
      " · 回合" + s.turn +
      (prov.provider ? " · " + prov.provider + "/" + prov.model : "");
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
    if (!(tail || []).length) {
      box.appendChild(el("div", "ev", "（还没有剧情——打完第一回合就会出现在这里）"));
    }
  }

  function refreshMeta() {
    fetch("/api/state").then(function (r) { return r.json(); }).then(function (s) {
      if (s.in_game === false) return;
      setMeta(s.meta || {});
      renderHistory(s.history_tail);
    }).catch(function () {});
  }

  function fillPanel(listSel, events, emptyHint) {
    var box = $(listSel);
    box.innerHTML = "";
    (events || []).forEach(function (ev) {
      box.appendChild(el("div", "ev ev-" + ev.k, ev.t));
    });
    if (!(events || []).length && emptyHint) box.appendChild(el("div", "ev", emptyHint));
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

  // 剧情翻页
  function paginate(text) {
    var paras = text.split("\n");
    var out = [], cur = "";
    paras.forEach(function (p) {
      if (p.length > PAGE_MAX) {
        if (cur) { out.push(cur); cur = ""; }
        for (var i = 0; i < p.length; i += PAGE_MAX) out.push(p.slice(i, i + PAGE_MAX));
        return;
      }
      if (cur && (cur + "\n" + p).length > PAGE_MAX) { out.push(cur); cur = p; }
      else cur = cur ? cur + "\n" + p : p;
    });
    if (cur || !out.length) out.push(cur || "");
    return out;
  }

  function stopTyping(finish) {
    if (typing) {
      clearInterval(typing);
      typing = null;
      if (finish && pages[0] != null) {
        var node = $("#story-track").children[0];
        if (node) node.textContent = pages[0];
      }
    }
  }

  function updatePager() {
    var dots = $("#pg-dots");
    dots.innerHTML = "";
    pages.forEach(function (_, i) {
      dots.appendChild(el("span", "pgdot" + (i === pageIdx ? " on" : "")));
    });
    $("#pg-label").textContent = pages.length > 1 ? (pageIdx + 1) + " / " + pages.length : "";
    $("#story-track").style.transform = "translateX(-" + pageIdx * 100 + "%)";
    $("#pg-prev").disabled = pageIdx === 0;
    $("#pg-next").disabled = pageIdx >= pages.length - 1;
  }

  function buildPages(texts, animateFirst) {
    stopTyping(false);
    pages = texts;
    pageIdx = 0;
    var track = $("#story-track");
    track.innerHTML = "";
    texts.forEach(function (t) {
      var d = el("div", "story-page");
      d.textContent = t;
      track.appendChild(d);
    });
    updatePager();
    if (animateFirst && texts.length === 1 && !reduced) typePage0(texts[0]);
  }

  function typePage0(text) {
    var node = $("#story-track").children[0];
    if (!node) return;
    node.textContent = "";
    var pos = 0;
    var step = Math.max(1, Math.round(text.length / 240));
    stopTyping(false);
    typing = setInterval(function () {
      pos += step;
      node.textContent = text.slice(0, pos);
      if (pos >= text.length) stopTyping(false);
    }, 16);
  }

  function gotoPage(i) {
    if (i < 0 || i >= pages.length || i === pageIdx) return;
    stopTyping(true);
    pageIdx = i;
    updatePager();
  }

  // 字画描述: 标题·色调·时间地点·页码
  function updateSlide(idx, total, caption, tone) {
    var dots = $("#slide-dots");
    dots.innerHTML = "";
    for (var i = 0; i < total; i++) {
      dots.appendChild(el("span", "dot" + (i === idx ? " on" : "")));
    }
    if (idx < 0) {
      $("#slide-caption").textContent = "（暂无画面——剧情继续中）";
      return;
    }
    var s = meta.state || meta;
    var parts = [];
    if (caption) parts.push(caption);
    if (tone) parts.push(tone + "色调");
    if (s.day != null) parts.push("第" + s.day + "天·" + s.period + " · " + s.location);
    if (total > 1) parts.push((idx + 1) + "/" + total);
    $("#slide-caption").textContent = parts.join(" · ");
  }

  function renderTurn(d, opts) {
    opts = opts || {};
    var txt = (d.narrative || "").replace(/\*\*/g, "");
    buildPages(paginate(txt), opts.animate !== false);
    var box = renderEvents(d.events || []);
    if (d.dice && d.dice.roll) {
      box.prepend(el("div", "ev ev-dice",
        "🎲 命运骰 " + d.dice.roll + "/20 · " + (d.dice.label || "")));
    }
    setSuggestions(d.suggestions || []);
    if (d.stage && d.stage.length) stage.play(d.stage, { all: true });
  }

  async function submit(text, sink) {
    if (text == null) text = $("#input").value.trim();
    if (!text) return;
    $("#input").value = "";
    $("#busy").hidden = false;
    $("#input").disabled = true;
    try {
      var d = await post("/api/say", { text: text });
      if (d.kind === "turn") {
        renderTurn(d);
        if (d.state) setMeta({ state: d.state });
        refreshMeta();
      } else if (d.kind === "command") {
        if (sink) {
          fillPanel(sink + "-list", d.events || []);
          $(sink).hidden = false;
        } else {
          renderEvents(d.events || []);
        }
        refreshMeta();
      } else {
        renderEvents([]).appendChild(el("div", "ev ev-error", d.message || "请求失败"));
      }
    } catch (e) {
      renderEvents([]).appendChild(el("div", "ev ev-error", "网络错误: " + e.message));
    } finally {
      $("#busy").hidden = true;
      $("#input").disabled = false;
      $("#input").focus();
    }
  }

  function enterGame(state) {
    document.body.classList.remove("lobby");
    $("#meta").textContent = "";
    if (!gameBound) {
      gameBound = true;
      var cfg = state.canvas || { w: 12, h: 6, tones: ["灰"] };
      stage = SlideEngine.createStage($("#stage"), {
        W: cfg.w, H: cfg.h, tones: cfg.tones,
        aspect: cfg.w + " / " + Math.round(cfg.h * 1.2),
        onSlide: updateSlide
      });
      $("#input-form").addEventListener("submit", function (ev) {
        ev.preventDefault();
        submit();
      });
      $("#btn-ledger").addEventListener("click", function () { submit("/status", "#ledger"); });
      $("#btn-history").addEventListener("click", function () {
        $("#history").hidden = !$("#history").hidden;
      });
      Array.prototype.forEach.call(document.querySelectorAll(".panel .close"), function (btn) {
        btn.addEventListener("click", function () { btn.closest(".panel").hidden = true; });
      });
      $("#pg-prev").addEventListener("click", function () { gotoPage(pageIdx - 1); });
      $("#pg-next").addEventListener("click", function () { gotoPage(pageIdx + 1); });
      var sx = null;
      var vp = $("#story-viewport");
      vp.addEventListener("touchstart", function (e) { sx = e.touches[0].clientX; }, { passive: true });
      vp.addEventListener("touchend", function (e) {
        if (sx == null) return;
        var dx = e.changedTouches[0].clientX - sx;
        if (Math.abs(dx) > 40) gotoPage(pageIdx + (dx < 0 ? 1 : -1));
        sx = null;
      });
    }
    setMeta(state.meta || {});
    renderHistory(state.history_tail);
    if (state.last) {
      renderTurn(Object.assign({}, state.last, { events: [] }), { animate: false });
    }
    stage.play(state.stage || [], { instant: true });
  }

  // ================= 启动 =================

  async function boot() {
    // 大厅绑定
    $("#btn-config").addEventListener("click", function () {
      $("#config-panel").hidden = false;
      cfgMsg("");
    });
    $("#config-panel").querySelector(".close").addEventListener("click", function () {
      $("#config-panel").hidden = true;
    });
    $("#cfg-provider").addEventListener("change", onProviderChange);
    $("#btn-models").addEventListener("click", pullModels);
    $("#btn-test").addEventListener("click", testConfig);
    $("#btn-save-cfg").addEventListener("click", saveConfig);
    $("#new-form").addEventListener("submit", async function (ev) {
      ev.preventDefault();
      var name = $("#new-name").value.trim();
      if (!name) { lobbyMsg("请先填写存档名", true); return; }
      var r = await post("/api/saves", { name: name, hero: $("#new-hero").value });
      if (!r.ok) { lobbyMsg(r.message || "创建失败", true); return; }
      $("#new-name").value = "";
      $("#new-hero").value = "";
      enterSave(name);
    });
    $("#btn-exit").addEventListener("click", exitServer);

    var state = await (await fetch("/api/state")).json();
    if (state.in_game === false) {
      await loadLobby();
    } else {
      enterGame(state);
    }
  }

  boot().catch(function (e) {
    document.body.appendChild(el("div", "ev ev-error", "启动失败: " + e.message));
  });
})();
