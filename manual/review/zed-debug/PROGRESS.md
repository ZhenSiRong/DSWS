# Zed 调试器路径进度（分段落盘）

- [x] 项目级配置样例 `debug.json`（Debugpy / launch / pdb_step_demo.py / cwd 仓库根 / stopOnEntry），`python3 -m json.tool` 通过
- [x] debugpy 1.8.22 装进 `backend/.venv`，`import debugpy` 通过；adapter 用 `--listen 127.0.0.1:5679 --wait-for-client` 起监听成功
- [x] 最小 DAP 客户端：initialize 通过；手写 launch 被 adapter 拒（参数不全，非配置问题）
- [ ] GUI 实拍：**未成**。无 xdotool/wmctrl；python-xlib XTEST 向 Zed(GPUI) 窗口注入 F4/Ctrl+P 画面无变化，
      打不开「新建调试会话」弹窗；不截整个桌面 → 不出 `manual/images/gui-zed-debug.png`
- [x] 自己启动的 Zed 进程已按 PID kill（107692/107698），临时 `.zed/debug.json` 已删
