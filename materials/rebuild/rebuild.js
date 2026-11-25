/* rebuild.js — 重构版组件的交互行为（让 8 块真正可用，Q8 判据2）。
 * ③ 代码块「复制」按钮：写入剪贴板并回显「已复制」。
 * ② 阅读进度条：随页面滚动填充。
 * 纯前端、无依赖；重构版自正典，独立成页也能用。
 */
(function () {
  "use strict";

  // ③ 复制按钮
  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest(".rb-copy");
    if (!btn) return;
    var code = btn.parentElement.querySelector("code");
    if (!code) return;
    var text = code.textContent;
    var done = function () {
      var old = btn.textContent;
      btn.textContent = "已复制";
      setTimeout(function () { btn.textContent = old; }, 1200);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, function () { fallback(text); done(); });
    } else { fallback(text); done(); }
  });

  function fallback(text) {
    var ta = document.createElement("textarea");
    ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); } catch (e) {}
    ta.remove();
  }

  // ② 阅读进度条：滚动填充
  var bar = document.querySelector(".rb-progress > span");
  if (bar) {
    var fill = function () {
      var h = document.documentElement;
      var max = h.scrollHeight - h.clientHeight;
      var pct = max > 0 ? (h.scrollTop || window.scrollY) / max * 100 : 0;
      bar.style.width = Math.max(0, Math.min(100, pct)) + "%";
    };
    window.addEventListener("scroll", fill, { passive: true });
    window.addEventListener("resize", fill);
    fill();
  }
})();