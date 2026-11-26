/* 编辑器的「另存为 / 覆盖保存」按钮（注入 editor.html；挂到顶栏 .hf-bar） */
(function () {
  'use strict';
  const page = (location.pathname.match(/page-(\d{2})/) || [])[1];
  if (!page) return;

  function toast(msg) {
    if (window.__layerEditor && typeof window.__layerEditor.toast === 'function') {
      window.__layerEditor.toast(msg);
    } else {
      console.log('[save-ui]', msg);
    }
  }
  function getHTML() {
    return (window.__layerEditor && typeof window.__layerEditor.fullHTML === 'function')
      ? window.__layerEditor.fullHTML() : null;
  }
  function makeBtn(text, primary) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'hf-btn' + (primary ? ' primary' : '');
    b.textContent = text;
    return b;
  }
  function mount() {
    if (!window.__layerEditor || !document.querySelector('.hf-bar')) return false;
    if (document.getElementById('ds-save-as')) return true;
    const bar = document.querySelector('.hf-bar');
    const zoom = bar.querySelector('.hf-zoom');
    const asBtn = makeBtn('另存为 HTML', false); asBtn.id = 'ds-save-as';
    const saveBtn = makeBtn('覆盖保存', true); saveBtn.id = 'ds-save-overwrite';

    asBtn.addEventListener('click', function () {
      const html = getHTML();
      if (!html) { toast('编辑器还没就绪'); return; }
      const name = prompt('另存文件名（浏览器下载目录）', 'page-' + page + '-edited.html');
      if (!name) return;
      const url = URL.createObjectURL(new Blob([html], { type: 'text/html;charset=utf-8' }));
      const a = Object.assign(document.createElement('a'), { href: url, download: name });
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
      toast('已另存：' + name);
    });

    saveBtn.addEventListener('click', function () {
      const html = getHTML();
      if (!html) { toast('编辑器还没就绪'); return; }
      if (!confirm('覆盖 page-' + page + '/index.html 并重建 PNG/WebP？旧版会备份到 out/。')) return;
      const old = saveBtn.textContent;
      saveBtn.disabled = true; saveBtn.textContent = '保存中…';
      fetch('/api/save', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ page: page, html: html })
      }).then(function (r) { return r.json(); }).then(function (res) {
        if (!res.ok) { toast('保存失败：' + (res.error || '未知错误')); return; }
        toast('已覆盖保存；' + ((res.messages || []).join('；') || '重建完成'));
      }).catch(function (e) {
        toast('保存请求失败：' + e.message + '（请确认用 toolbox/scripts/design-serve.py 启动服务）');
      }).finally(function () {
        saveBtn.disabled = false; saveBtn.textContent = old;
      });
    });

    if (zoom) { bar.insertBefore(asBtn, zoom); bar.insertBefore(saveBtn, zoom); }
    else { bar.appendChild(asBtn); bar.appendChild(saveBtn); }
    return true;
  }

  let tries = 0;
  const timer = setInterval(function () {
    if (mount() || ++tries > 400) clearInterval(timer);
  }, 250);
  window.addEventListener('load', mount);
})();
