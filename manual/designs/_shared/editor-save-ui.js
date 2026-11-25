/* 编辑器的「另存为 / 覆盖保存」浮动面板（由 inject_save_ui.py 注入到 editor.html） */
(function () {
  'use strict';
  const page = (location.pathname.match(/page-(\d{2})/) || [])[1];
  if (!page) return;

  const css = `
  #ds-save-ui{position:fixed;right:18px;bottom:18px;z-index:2147483000;display:flex;flex-direction:column;gap:8px;
    background:#1a1a1a;color:#fff;padding:12px 14px;border-radius:6px;font:13px/1.4 "Noto Sans CJK SC",sans-serif;
    box-shadow:0 6px 24px rgba(0,0,0,.28);min-width:210px}
  #ds-save-ui .row{display:flex;gap:8px}
  #ds-save-ui button{flex:1;border:0;border-radius:4px;padding:8px 10px;font:inherit;font-weight:700;cursor:pointer}
  #ds-save-ui .as{background:#fff;color:#1a1a1a}
  #ds-save-ui .save{background:#E65100;color:#fff}
  #ds-save-ui .status{color:#cfcfcf;font-size:11px;min-height:16px;white-space:pre-wrap}
  `;
  const style = document.createElement('style'); style.textContent = css; document.head.appendChild(style);
  const box = document.createElement('div'); box.id = 'ds-save-ui';
  box.innerHTML = '<div class="row"><button class="as" type="button">另存为 HTML</button>' +
                  '<button class="save" type="button">覆盖保存到项目</button></div>' +
                  '<div class="status">改完先点「覆盖保存」，会自动重建 PNG/WebP</div>';
  document.body.appendChild(box);
  const status = box.querySelector('.status');

  function getHTML() {
    if (window.__layerEditor && typeof window.__layerEditor.fullHTML === 'function') {
      return window.__layerEditor.fullHTML();
    }
    return null;
  }
  function setStatus(t) { status.textContent = t; }

  box.querySelector('.as').addEventListener('click', function () {
    const html = getHTML();
    if (!html) { setStatus('编辑器还没就绪，稍等一秒再试'); return; }
    const name = prompt('另存文件名（保存到浏览器下载目录）', 'page-' + page + '-edited.html');
    if (!name) return;
    const url = URL.createObjectURL(new Blob([html], { type: 'text/html;charset=utf-8' }));
    const a = Object.assign(document.createElement('a'), { href: url, download: name });
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
    setStatus('已另存：' + name);
  });

  box.querySelector('.save').addEventListener('click', function () {
    const html = getHTML();
    if (!html) { setStatus('编辑器还没就绪，稍等一秒再试'); return; }
    if (!confirm('覆盖 page-' + page + '/index.html 并重建 PNG/WebP？旧版会自动备份。')) return;
    setStatus('正在保存并重建，约 5–10 秒…');
    fetch('/api/save', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ page: page, html: html })
    }).then(r => r.json()).then(function (res) {
      if (!res.ok) { setStatus('保存失败：' + (res.error || '未知错误')); return; }
      setStatus('已覆盖保存并重建：\n' + (res.messages || []).join('\n'));
    }).catch(function (e) { setStatus('保存请求失败：' + e.message); });
  });
})();
