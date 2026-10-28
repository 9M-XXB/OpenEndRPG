/* 完全开放式RPG · 字画幻灯片引擎 (M2, 见 ../..//规划.md)
   解析 LLM 输出的字符画布 → 布点渲染 → PPT 式切换(淡入/按字平滑滑动/硬切)。
   零图像元素: 本文件不含任何形状库、图标或图片; 所有字与位置 100% 来自运行时 LLM 输出。
   "移动即切换": 前后两张画布中同名汉字位置不同, 切换时按最近距离配对平滑滑动。
   本文由 ZCode (GLM-5.3-Flash) 编写。 */
(function (global) {
  "use strict";

  var FULL = "　"; // 全角空格 = 空白格

  // ---------- 解析与归一化: 画面错误永不使回合失败(钳位/截断/丢弃) ----------
  function normalizeSlides(raw, W, H) {
    if (!Array.isArray(raw)) return [];
    var out = [];
    for (var i = 0; i < raw.length && out.length < 3; i++) {
      var s = raw[i];
      if (!s || typeof s !== "object" || !Array.isArray(s.canvas)) continue;
      var cells = [];
      for (var r = 0; r < H; r++) {
        var rowStr = typeof s.canvas[r] === "string" ? s.canvas[r].split(" ").join(FULL) : "";
        var chars = Array.from(rowStr).slice(0, W);
        while (chars.length < W) chars.push(FULL);
        cells.push(chars);
      }
      out.push({
        caption: typeof s.caption === "string" ? s.caption.slice(0, 12) : "",
        tone: typeof s.tone === "string" ? s.tone : "",
        cells: cells
      });
    }
    return out;
  }

  // ---------- 舞台 ----------
  function createStage(container, opts) {
    var W = opts.W, H = opts.H;
    var TONES = Array.isArray(opts.tones) && opts.tones.length ? opts.tones : ["灰"];
    var onSlide = opts.onSlide || function () {};
    var spans = [];   // 与"当前显示画布的非空白格"一一平行: {ch, col, row, el}
    var slides = [];
    var cur = -1;
    var timer = null;
    var dwell = 5200; // PPT 自动翻页间隔

    container.style.aspectRatio = opts.aspect || (W + " / " + H);
    container.setAttribute("data-tone", "灰");
    container.addEventListener("click", function () { next(); });

    // 尺寸变化(含首帧布局未稳)时重排布点: 布点必须以真实渲染尺寸为准
    function replant() {
      if (!spans.length) return;
      container.classList.add("snap");
      spans.forEach(function (sp) { place(sp, sp.col, sp.row); });
      requestAnimationFrame(function () { container.classList.remove("snap"); });
    }
    if (typeof ResizeObserver !== "undefined") {
      new ResizeObserver(replant).observe(container);
    } else {
      window.addEventListener("resize", replant);
    }

    function cellSize() {
      return { w: container.clientWidth / W, h: container.clientHeight / H };
    }

    // 远近分层: 上 2 行远景小字, 中间中景, 下 2 行近景大字 (布局规则属"框架", 非图像元素)
    function tierSize(row) {
      var t = row < 2 ? 0.7 : (row < 4 ? 0.9 : 1.08);
      return cellSize().w * t * 0.95;
    }

    function place(sp, col, row) {
      var c = cellSize();
      sp.col = col;
      sp.row = row;
      sp.el.style.fontSize = tierSize(row) + "px";
      sp.el.style.transform = "translate(" + (col * c.w + c.w / 2) + "px," +
                              (row * c.h + c.h / 2) + "px) translate(-50%,-50%)";
    }

    function glyphEntries(slide) {
      var out = [];
      for (var r = 0; r < slide.cells.length; r++) {
        for (var c = 0; c < slide.cells[r].length; c++) {
          var ch = slide.cells[r][c];
          if (ch && ch !== FULL) out.push({ ch: ch, col: c, row: r });
        }
      }
      return out;
    }

    // 按字匹配: 同名汉字在前后两张画布间按曼哈顿距离最近贪心配对
    function match(prev, next) {
      var byChar = {};
      prev.forEach(function (p, i) { (byChar[p.ch] = byChar[p.ch] || []).push(i); });
      var pairs = [], usedNext = {};
      Object.keys(byChar).forEach(function (ch) {
        var cand = [];
        byChar[ch].forEach(function (pi) {
          next.forEach(function (n, ni) {
            if (n.ch !== ch || usedNext[ni]) return;
            cand.push({ pi: pi, ni: ni,
                        d: Math.abs(prev[pi].col - n.col) + Math.abs(prev[pi].row - n.row) });
          });
        });
        cand.sort(function (a, b) { return a.d - b.d; });
        var usedPrev = {};
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
      var entries = glyphEntries(slide);
      var pairs = prev ? match(glyphEntries(prev), entries) : [];
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

      // 延续的字平滑滑动 / 新字淡入
      var nextSpans = [];
      entries.forEach(function (en, ni) {
        var old = prev ? keptSpans[prevByNext[ni]] : null;
        if (old) {
          place(old, en.col, en.row);
          nextSpans.push(old);
        } else {
          var elx = document.createElement("span");
          elx.className = "glyph in";
          elx.textContent = en.ch;
          container.appendChild(elx);
          var sp = { ch: en.ch, col: en.col, row: en.row, el: elx };
          place(sp, en.col, en.row);
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
      slides = normalizeSlides(raw, W, H);
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

  var api = { normalizeSlides: normalizeSlides, createStage: createStage };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  global.SlideEngine = api;
})(typeof window !== "undefined" ? window : globalThis);
