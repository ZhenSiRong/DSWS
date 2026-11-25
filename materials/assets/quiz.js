/* ============================================================
   quiz.js — 可复用测验组件
   用法：
     <div class="quiz" data-explain="解析文本">
       <p class="q">题干</p>
       <div class="opts">
         <button type="button" data-opt data-correct="false">A</button>
         <button type="button" data-opt data-correct="true">B</button>
       </div>
       <p class="feedback" aria-live="polite"></p>
     </div>
   计分：页面任意位置放 <span data-score>，会显示 答对/已答。
   一次性作答（不可重试），迫使学习者先做记忆提取再获得反馈。
   ============================================================ */
(function () {
  "use strict";

  var answered = 0;
  var correct = 0;

  function renderScore() {
    var el = document.querySelector("[data-score]");
    if (el) {
      el.textContent = answered === 0 ? "尚未作答" : correct + " / " + answered;
    }
  }

  function wire(quiz) {
    var opts = Array.prototype.slice.call(quiz.querySelectorAll("[data-opt]"));
    var fb = quiz.querySelector(".feedback");
    var done = false;

    opts.forEach(function (btn) {
      btn.addEventListener("click", function () {
        if (done) return;
        done = true;
        answered += 1;

        var isCorrect = btn.getAttribute("data-correct") === "true";
        if (isCorrect) correct += 1;

        opts.forEach(function (b) {
          b.disabled = true;
          if (b.getAttribute("data-correct") === "true") b.classList.add("is-correct");
        });
        if (!isCorrect) btn.classList.add("is-wrong");

        if (fb) {
          var explain = quiz.getAttribute("data-explain") || "";
          fb.textContent = (isCorrect ? "✓ 对。" : "✗ 不对，正确项已标绿。") + explain;
          fb.className = "feedback " + (isCorrect ? "ok" : "bad");
        }
        renderScore();
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    Array.prototype.forEach.call(document.querySelectorAll(".quiz"), wire);
    renderScore();
  });
})();
