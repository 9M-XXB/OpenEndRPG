/* 完全开放式RPG · 字画幻灯片引擎 v2 (规划.md 第五轮: 双语统一 glyphs 契约)
   契约: slide = {caption, tone, glyphs:[{ch,x,y,s,r}]} — x/y 0~100 舞台百分比, s 字号档 1~9,
   r 旋转 -90~90 度。旧 v0.2 canvas 网格在归一化时换算为 glyphs(格位→坐标, 行分层→字号档)。
   解析 → 布点渲染 → PPT 式切换(淡入/实例匹配平滑滑动/硬切)。
   零图像元素: 本文件不含任何形状库、图标或图片; 所有字与位置 100% 来自运行时 LLM 输出。
   "移动即切换": 前后两张字画中同名且距离≤30 舞台单位的字按实例配对, 切换时平滑滑动/缩放/旋转。
   本文由 ZCode (GLM-5.3-Flash) 编写。 */
(function (global) {
  "use strict";

  var FULL = "　";        // 旧画布空白格
  var STAGE = 100;        // 舞台百分比坐标上限
  var S_MIN = 1, S_MAX = 9, R_MAX = 90, GLYPHS_MAX = 24, SLIDES_MAX = 3;
  var BASE_COL = 12;      // 字号基准: s=3 时字宽 ≈ 舞台宽/12 (与 v0.2 网格一致)
  var MATCH_DIST = 30;    // 实例配对的舞台距离阈值(同一字形 + 距离内才视为"同一个字在移动")

  function clamp(v, lo, hi, dflt) {
    v = typeof v === "number" && isFinite(v) ? v : dflt;
    return Math.max(lo, Math.min(hi, v));
  }

  // ---------- 解析与归一化: 画面错误永不使回合失败(钳位/截断/丢弃) ----------
  function normalizeGlyphs(raw) {
    var out = [];
    if (!Array.isArray(raw)) return out;
    for (var i = 0; i < raw.length && out.length < GLYPHS_MAX; i++) {
      var g = raw[i];
      if (!g || typeof g !== "object") continue;
      var ch = typeof g.ch === "string" ? Array.from(g.ch.trim())[0] : undefined;
      if (!ch || ch === FULL || ch === " ") continue;
      out.push({
        ch: ch,
        x: clamp(g.x, 0, STAGE, STAGE / 2),
        y: clamp(g.y, 0, STAGE, STAGE / 2),
        s: Math.round(clamp(g.s, S_MIN, S_MAX, 3)),
        r: clamp(g.r, -R_MAX, R_MAX, 0)
      });
    }
    return out;
  }

  // 旧 v0.2 canvas 网格 → glyphs (格位→坐标, 行分层→字号档, r=0)
  function canvasToGlyphs(cells, W, H) {
    var out = [];
    for (var r = 0; r < cells.length && out.length < GLYPHS_MAX; r++) {
      for (var c = 0; c < cells[r].length && out.length < GLYPHS_MAX; c++) {
        var ch = cells[r][c];
        if (ch && ch !== FULL && ch !== " ") {
          out.push({
            ch: ch,
            x: (c + 0.5) * STAGE / W,
            y: (r + 0.5) * STAGE / H,
            s: r < 2 ? 2 : 3,
            r: 0
          });
        }
      }
    }
    return out;
  }

  function normalizeSlides(raw, W, H) {
    // W/H 兼容旧签名; 新契约不需要
    W = W || 12; H = H || 6;
    if (!Array.isArray(raw)) return [];
    var out = [];
    for (var i = 0; i < raw.length && out.length < SLIDES_MAX; i++) {
      var s = raw[i];
      if (!s || typeof s !== "object") continue;
      var glyphs;
      if (Array.isArray(s.glyphs)) {
        glyphs = normalizeGlyphs(s.glyphs);
      } else if (Array.isArray(s.canvas)) {
        var rows = [];
        for (var r = 0; r < H; r++) {
          var rowStr = typeof s.canvas[r] === "string" ? s.canvas[r].split(" ").join(FULL) : "";
          var chars = Array.from(rowStr).slice(0, W);
          while (chars.length < W) chars.push(FULL);
          rows.push(chars);
        }
        glyphs = canvasToGlyphs(rows, W, H);
      } else {
        continue;
      }
      if (!glyphs.length) continue;
      out.push({
        caption: typeof s.caption === "string" ? s.caption.slice(0, 24) : "",
        tone: typeof s.tone === "string" ? s.tone : "",
        glyphs: glyphs
      });
    }
    return out;
  }

  // ---------- 舞台 ----------
  function createStage(container, opts) {
    var TONES = Array.isArray(opts.tones) && opts.tones.length ? opts.tones : ["灰"];
    var onSlide = opts.onSlide || function () {};
    var spans = [];   // 与"当前显示的字形"一一平行: {ch,x,y,s,r,el}
    var slides = [];
    var cur = -1;
    var timer = null;
    var dwell = 5200; // PPT 自动翻页间隔

    container.style.aspectRatio = opts.aspect || "12 / 7";
    container.setAttribute("data-tone", "灰");
    container.addEventListener("click", function () { next(); });

    function metrics() {
      var w = container.clientWidth, h = container.clientHeight;
      return { w: w, h: h, font: w / BASE_COL };
    }

    // 尺寸变化(含首帧布局未稳)时重排布点: 布点必须以真实渲染尺寸为准
    function replant() {
      if (!spans.length) return;
      container.classList.add("snap");
      spans.forEach(function (sp) { place(sp); });
      requestAnimationFrame(function () { container.classList.remove("snap"); });
    }
    if (typeof ResizeObserver !== "undefined") {
      new ResizeObserver(replant).observe(container);
    } else {
      window.addEventListener("resize", replant);
    }

    function place(sp) {
      var m = metrics();
      sp.el.style.fontSize = Math.max(8, m.font * (sp.s / 3)) + "px";
      sp.el.style.transform = "translate(" + (sp.x / STAGE * m.w) + "px," + (sp.y / STAGE * m.h) + "px)" +
                              " translate(-50%,-50%)" +
                              (sp.r ? " rotate(" + sp.r + "deg)" : "");
    }

    // 实例匹配: 同名字形在前后两张字画间按距离最近贪心配对(≤MATCH_DIST 才算"同一个字在移动")
    function match(prev, next) {
      var byChar = {};
      prev.forEach(function (p, i) { (byChar[p.ch] = byChar[p.ch] || []).push(i); });
      var pairs = [], usedNext = {}, usedPrev = {};
      Object.keys(byChar).forEach(function (ch) {
        var cand = [];
        byChar[ch].forEach(function (pi) {
          next.forEach(function (n, ni) {
            if (n.ch !== ch || usedNext[ni]) return;
            var d = Math.abs(prev[pi].x - n.x) + Math.abs(prev[pi].y - n.y);
            if (d <= MATCH_DIST) cand.push({ pi: pi, ni: ni, d: d });
          });
        });
        cand.sort(function (a, b) { return a.d - b.d; });
        cand.forEach(function (c) {
          if (!usedPrev[c.pi] && !usedNext[c.ni]) {
            usedPrev[c.pi] = usedNext[c.ni] = true;
            pairs.push(c);
          }
        });
      });
      return pairs;
    }

    function show(slide, prev, instant) {
      var entries = slide.glyphs;
      var pairs = prev ? match(prev.glyphs, entries) : [];
      var prevByNext = {};
      pairs.forEach(function (p) { prevByNext[p.ni] = p.pi; });

      if (instant) container.classList.add("snap");

      // 未被延续的字: 淡出移除
      var keptSpans = {};
      if (prev) pairs.forEach(function (p) { keptSpans[p.pi] = spans[p.pi]; });
      spans.forEach(function (sp, i) {
        if (prev && keptSpans[i]) return;
        var elx = sp.el;
        if (instant) { elx.remove(); }
        else {
          elx.classList.add("out");
          setTimeout(function () { elx.remove(); }, 500);
        }
      });

      // 延续的字平滑滑动/缩放/旋转, 新字淡入
      var nextSpans = [];
      entries.forEach(function (en, ni) {
        var old = prev ? keptSpans[prevByNext[ni]] : null;
        if (old) {
          old.ch = en.ch; old.x = en.x; old.y = en.y; old.s = en.s; old.r = en.r;
          old.el.textContent = en.ch;
          place(old);
          nextSpans.push(old);
        } else {
          var elx = document.createElement("span");
          elx.className = "glyph in";
          elx.textContent = en.ch;
          container.appendChild(elx);
          var sp = { ch: en.ch, x: en.x, y: en.y, s: en.s, r: en.r, el: elx };
          place(sp);
          if (instant) {
            elx.classList.remove("in");
          } else {
            requestAnimationFrame(function () {
              requestAnimationFrame(function () { elx.classList.remove("in"); });
            });
          }
          nextSpans.push(sp);
        }
      });
      spans = nextSpans;

      container.setAttribute("data-tone", TONES.indexOf(slide.tone) >= 0 ? slide.tone : TONES[0]);
      if (instant) {
        requestAnimationFrame(function () { container.classList.remove("snap"); });
        // 首帧布局未稳时的兜底重排(布局定型后再布点一次)
        requestAnimationFrame(function () {
          requestAnimationFrame(replant);
        });
      }
    }

    function fire() {
      var s = slides[cur];
      onSlide(cur, slides.length, s ? s.caption : "", s ? s.tone : "");
    }

    function step() {
      cur++;
      show(slides[cur], cur > 0 ? slides[cur - 1] : null, false);
      fire();
      if (cur < slides.length - 1) timer = setTimeout(step, dwell);
    }

    function stopTimer() { if (timer) { clearTimeout(timer); timer = null; } }

    function play(raw, opts2) {
      opts2 = opts2 || {};
      stopTimer();
      slides = normalizeSlides(raw);
      if (!slides.length) {
        spans.forEach(function (sp) { sp.el.remove(); });
        spans = [];
        cur = -1;
        fire();
        return;
      }
      if (opts2.instant) { // 启动/刷新: 直接落在最后一张
        cur = slides.length - 1;
        show(slides[cur], null, true);
        fire();
        return;
      }
      cur = -1;
      step();
    }

    function next() { // 手动翻页(点击画面), 同 PPT
      if (cur < 0 || cur >= slides.length - 1) return;
      stopTimer();
      step();
    }

    return { play: play, next: next };
  }

  var api = { normalizeSlides: normalizeSlides, createStage: createStage,
              canvasToGlyphs: canvasToGlyphs, normalizeGlyphs: normalizeGlyphs };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  global.SlideEngine = api;
})(typeof window !== "undefined" ? window : globalThis);
