import json
import os
import subprocess
import sys
import threading
import time

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

import webview

# ── System API exposed to JavaScript ─────────────────────────────────────────
class JarvisAPI:
    def __init__(self):
        self._win = None
        self._last_net = None
        self._last_time = None

    def set_window(self, window):
        self._win = window

    def get_stats(self):
        if not HAS_PSUTIL:
            return json.dumps({"cpu": 23, "ram": 45, "disk": 62, "net": 120.4})
        try:
            cpu  = psutil.cpu_percent(interval=None)
            ram  = psutil.virtual_memory().percent
            disk = psutil.disk_usage("/").percent

            # Network Mbps calculation
            net = psutil.net_io_counters()
            now = time.time()
            total_bytes = net.bytes_sent + net.bytes_recv

            if self._last_net is None:
                mbps = 0.0
            else:
                dt = now - self._last_time
                mbps = round(((total_bytes - self._last_net) * 8) / (dt * 1e6), 1)

            self._last_net = total_bytes
            self._last_time = now

            return json.dumps({"cpu": cpu, "ram": ram, "disk": disk, "net": mbps})
        except Exception:
            return json.dumps({"cpu": 0, "ram": 0, "disk": 0, "net": 0})

    def minimize(self):
        if self._win:
            self._win.minimize()

    def close_app(self):
        if self._win:
            self._win.destroy()

    def open_file_dialog(self):
        if not self._win: return json.dumps("")
        result = self._win.create_file_dialog(webview.OPEN_DIALOG)
        return json.dumps(result[0] if result else "")

    def open_folder_dialog(self):
        if not self._win: return json.dumps("")
        result = self._win.create_file_dialog(webview.FOLDER_DIALOG)
        return json.dumps(result[0] if result else "")

    def execute_action(self, action_type):
        """Execute system level actions."""
        try:
            if action_type == 'terminal':
                if sys.platform == "win32":
                    subprocess.Popen(["start", "cmd"], shell=True)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", "-a", "Terminal"])
                else:
                    for term in ["gnome-terminal", "xterm", "konsole", "xfce4-terminal"]:
                        try:
                            subprocess.Popen([term])
                            return json.dumps({"status": "success", "action": action_type})
                        except FileNotFoundError:
                            continue
            elif action_type == 'files':
                if sys.platform == "win32":
                    os.startfile(".")
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", "."])
                else:
                    subprocess.Popen(["xdg-open", "."])
            elif action_type == 'browser':
                import webbrowser
                webbrowser.open("https://www.google.com")
            elif action_type == 'camera':
                if sys.platform == "win32":
                    subprocess.Popen(["start", "microsoft.windows.camera:"], shell=True)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", "-a", "Photo Booth"])
                else:
                    subprocess.Popen(["cheese"])
            elif action_type == 'notes':
                if sys.platform == "win32":
                    subprocess.Popen(["notepad.exe"])
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", "-a", "Notes"])
                else:
                    subprocess.Popen(["gedit"])
            elif action_type == 'calc':
                if sys.platform == "win32":
                    subprocess.Popen(["calc.exe"])
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", "-a", "Calculator"])
                else:
                    subprocess.Popen(["gnome-calculator"])
            elif action_type == 'shutdown':
                self.close_app()
            return json.dumps({"status": "success", "action": action_type})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

# ── HTML / CSS / JS ───────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>JARVIS OS</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700;900&family=Rajdhani:wght@400;500;600&display=swap');

  :root {
    --bg:      #06090f;
    --bg2:     #080d18;
    --panel:   #0c1525;
    --panel2:  #0f1c30;
    --border:  #1a3356;
    --border2: #1e4a72;
    --cyan:    #64f1ff; /* Tony Stark Cyan */
    --cyan2:   #00a8cc;
    --cyan3:   #004466;
    --text:    #ddeeff;
    --muted:   #5a8aaa;
    --green:   #00e5a0;
    --red:     #ff3b30;
    --orange:  #ff8c42;
    --yellow:  #ffd740;
    --font-mono: 'Consolas', 'Bahnschrift', monospace;
  }

  * { margin:0; padding:0; box-sizing:border-box; }

  body {
    font-family: 'Rajdhani', 'Courier New', monospace;
    background: var(--bg);
    color: var(--text);
    height: 100vh;
    overflow: hidden;
    user-select: none;
    cursor: default;
  }

  /* ── SCROLLBAR ── */
  ::-webkit-scrollbar { width:4px; }
  ::-webkit-scrollbar-track { background: var(--bg2); }
  ::-webkit-scrollbar-thumb { background: var(--border2); border-radius:2px; }

  /* ── LAYOUT ── */
  #app { display:flex; flex-direction:column; height:100vh; border: 1px solid var(--border); }

  /* ── TITLEBAR ── */
  #titlebar {
    height: 52px;
    background: var(--bg2);
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    padding: 0 16px;
    flex-shrink: 0;
    -webkit-app-region: drag;
    position: relative;
    z-index: 100;
  }
  #titlebar * { -webkit-app-region: no-drag; }

  .brand { display:flex; align-items:center; gap:10px; }
  .brand-icon {
    width:32px; height:32px; position:relative;
    display:flex; align-items:center; justify-content:center;
  }
  .brand-icon svg { width:32px; height:32px; }
  .brand-text h1 { font-family:'Orbitron',sans-serif; font-size:13px; font-weight:700; color:var(--text); letter-spacing:2px; }
  .online-badge { display:flex; align-items:center; gap:4px; margin-top:1px; }
  .online-dot { width:7px; height:7px; background:var(--green); border-radius:50%;
                box-shadow:0 0 6px var(--green); animation:pulse-dot 2s infinite; }
  @keyframes pulse-dot { 0%,100%{opacity:1} 50%{opacity:0.5} }
  .online-text { font-size:10px; color:var(--green); font-weight:600; letter-spacing:1px; }

  .title-center {
    position:absolute; left:50%; transform:translateX(-50%);
    text-align:center; pointer-events:none;
  }
  .title-center h2 {
    font-family:'Orbitron',sans-serif; font-size:22px; font-weight:900;
    color:var(--cyan); letter-spacing:6px;
    text-shadow:0 0 20px rgba(100,241,255,0.6), 0 0 40px rgba(100,241,255,0.3);
  }
  .title-center span { font-size:10px; color:var(--muted); letter-spacing:3px; }

  /* connector lines on sides of title */
  .title-center::before, .title-center::after {
    content:''; position:absolute; top:50%; height:1px; width:60px;
    background:linear-gradient(90deg, transparent, var(--cyan2));
  }
  .title-center::before { right:100%; margin-right:8px; }
  .title-center::after  { left:100%;  margin-left:8px; background:linear-gradient(90deg,var(--cyan2),transparent); }

  .nav { display:flex; align-items:center; gap:4px; margin-left:auto; margin-right:16px; }
  .nav-btn {
    display:flex; align-items:center; gap:6px; padding:6px 14px;
    background:transparent; border:none; color:var(--muted); cursor:pointer;
    font-family:'Rajdhani',sans-serif; font-size:13px; font-weight:600;
    border-radius:4px; transition:all 0.2s; letter-spacing:0.5px;
  }
  .nav-btn:hover { color:var(--cyan); }
  .nav-btn.active { color:var(--text); border-bottom: 2px solid var(--cyan); border-radius: 0; }
  .nav-btn svg { width:14px; height:14px; }

  .win-btns { display:flex; gap:2px; }
  .win-btn {
    width:28px; height:28px; display:flex; align-items:center; justify-content:center;
    background:transparent; border:none; cursor:pointer; border-radius:4px;
    font-size:14px; color:var(--muted); transition:all 0.2s;
  }
  .win-btn:hover { background:rgba(255,255,255,0.1); color:var(--text); }
  .win-btn.close:hover { background:var(--red); color:#fff; }

  /* ── VIEWS ── */
  #content { flex:1; overflow:hidden; position:relative; }
  .view {
    position: absolute; inset: 0;
    display: none;
    grid-template-columns: 292px 1fr 300px;
    gap:8px; padding:8px;
    overflow:hidden;
  }
  .view.active { display: grid; }

  /* ── PANELS ── */
  .panel {
    background:var(--panel);
    border:1px solid var(--border);
    border-radius:8px;
    overflow:hidden;
    position:relative;
    display: flex;
    flex-direction: column;
  }
  .panel::before {
    content:''; position:absolute; top:0;left:0;right:0; height:1px;
    background:linear-gradient(90deg,transparent,var(--cyan2),transparent);
    opacity:0.4;
  }
  /* corner accents */
  .panel::after {
    content:''; position:absolute; top:0;left:0;right:0;bottom:0;
    border-radius:8px; pointer-events:none;
    box-shadow:inset 0 0 30px rgba(0,50,100,0.2);
  }

  .panel-header {
    padding:8px 14px 7px;
    background:var(--panel2);
    border-bottom:1px solid var(--border);
    display:flex; align-items:center; gap:8px;
    font-family:'Orbitron',sans-serif; font-size:10px; font-weight:600;
    color:var(--cyan); letter-spacing:2px;
  }
  .panel-header::before {
    content:''; width:3px; height:16px; background:var(--cyan); border-radius:2px;
    box-shadow:0 0 8px var(--cyan);
  }

  /* ── COLUMN LAYOUTS ── */
  .col-side { display:flex; flex-direction:column; gap:8px; overflow:hidden; }
  .col-center { display:flex; flex-direction:column; gap:8px; overflow:hidden; }

  /* ── COMPONENTS ── */
  #jarvis-circle-panel { height:220px; flex-shrink:0; }
  #jarvis-canvas { width:100%; height:100%; display:block; }

  .metric-row { padding:5px 14px; }
  .metric-top { display:flex; align-items:center; justify-content:space-between; margin-bottom:3px; }
  .metric-icon { width:16px; height:16px; opacity:0.7; }
  .metric-label { font-size:11px; color:var(--muted); font-weight:500; flex:1; margin-left:6px; }
  .metric-val { font-size:11px; color:var(--text); font-weight:600; }
  .sparkline-wrap { height:16px; position:relative; }
  canvas.sparkline { width:100%; height:16px; display:block; }

  .qa-grid {
    display:grid; grid-template-columns:repeat(3,1fr);
    gap:6px; padding:10px;
  }
  .qa-btn {
    background:var(--panel2); border:1px solid var(--border);
    border-radius:8px; padding:12px 6px; display:flex;
    flex-direction:column; align-items:center; gap:6px;
    cursor:pointer; transition:all 0.2s;
  }
  .qa-btn:hover {
    border-color:var(--cyan2); background:rgba(0,100,150,0.2);
    box-shadow:0 0 12px rgba(0,150,200,0.2);
  }
  .qa-btn svg { width:24px; height:24px; color:var(--cyan); }
  .qa-btn span { font-size:10px; color:var(--muted); font-weight:600; letter-spacing:0.5px; }

  #greeting-panel { flex-shrink:0; height:220px; }
  #greeting-inner {
    display:flex; flex-direction:column; align-items:center;
    justify-content:center; height:100%; padding:10px 20px;
  }
  #greeting-inner h2 {
    font-family:'Orbitron',sans-serif; font-size:22px; font-weight:700;
    color:var(--text); letter-spacing:1px; margin-bottom:6px;
    text-shadow:0 0 20px rgba(200,240,255,0.3);
  }
  #greeting-inner p { font-size:13px; color:var(--muted); margin-bottom:14px; letter-spacing:0.5px; }
  #wave-canvas { width:100%; height:52px; display:block; margin-bottom:12px; }
  #mic-btn {
    width:54px; height:54px; border-radius:50%; border:2px solid var(--cyan);
    background:var(--panel2); display:flex; align-items:center; justify-content:center;
    cursor:pointer; transition:all 0.3s; position:relative;
    box-shadow:0 0 16px rgba(0,212,255,0.3);
  }
  #mic-btn:hover { box-shadow:0 0 24px rgba(0,212,255,0.6); transform:scale(1.05); }
  #mic-btn.active { background:rgba(0,212,255,0.2); box-shadow:0 0 30px rgba(0,212,255,0.8); }
  #mic-btn svg { width:22px; height:22px; color:var(--cyan); }

  .activities-row {
    display:flex; gap:6px; padding:10px 12px;
    overflow-x:auto; scrollbar-width:none;
  }
  .activities-row::-webkit-scrollbar { display:none; }
  .activity-btn {
    display:flex; flex-direction:column; align-items:center; gap:8px;
    min-width:90px; padding:12px 8px; background:var(--panel2);
    border:1px solid var(--border); border-radius:8px;
    cursor:pointer; transition:all 0.2s; flex:1;
  }
  .activity-btn:hover {
    border-color:var(--cyan2); background:rgba(0,80,120,0.3);
    box-shadow:0 0 16px rgba(0,150,200,0.2);
  }
  .act-icon {
    width:46px; height:46px; background:var(--panel);
    border:1px solid var(--border2); border-radius:10px;
    display:flex; align-items:center; justify-content:center;
  }
  .act-icon svg { width:22px; height:22px; color:var(--cyan); }
  .activity-btn span { font-size:10px; color:var(--muted); text-align:center; font-weight:600; }

  #chat-panel { flex:1; display:flex; flex-direction:column; overflow:hidden; }
  #chat-area {
    flex:1; overflow-y:auto; padding:10px 14px;
    display:flex; flex-direction:column; gap:10px;
  }
  .msg-user { display:flex; flex-direction:column; align-items:flex-end; }
  .msg-user .bubble {
    background:var(--panel2); border:1px solid var(--border2);
    border-radius:12px 12px 2px 12px; padding:8px 14px;
    max-width:70%; font-size:12px; color:var(--text);
  }
  .msg-meta { font-size:10px; color:var(--muted); margin-top:3px; }
  .msg-sender-label { font-size:10px; color:var(--muted); margin-bottom:2px; font-weight:600; }

  .msg-jarvis { display:flex; flex-direction:column; align-items:flex-start; }
  .jarvis-label { font-size:11px; color:var(--cyan); font-weight:700; letter-spacing:1px; margin-bottom:3px; }
  .msg-jarvis .bubble {
    background:var(--panel2); border:1px solid var(--border);
    border-radius:2px 12px 12px 12px; padding:10px 14px;
    max-width:80%; font-size:12px; color:var(--text);
    display:flex; gap:12px; align-items:flex-start;
  }

  #chat-input-row {
    padding:8px 12px; display:flex; align-items:center; gap:8px;
    border-top:1px solid var(--border);
  }
  #chat-input {
    flex:1; background:var(--panel2); border:1px solid var(--border);
    border-radius:24px; padding:9px 18px; color:var(--text);
    font-family:'Rajdhani',sans-serif; font-size:13px; outline:none;
    transition:border-color 0.2s;
  }
  #chat-input::placeholder { color:var(--muted); }
  #chat-input:focus { border-color:var(--cyan2); }
  #send-btn {
    width:36px; height:36px; border-radius:50%;
    background:var(--cyan2); border:none; cursor:pointer;
    display:flex; align-items:center; justify-content:center;
    transition:all 0.2s; flex-shrink:0;
  }
  #send-btn:hover { background:var(--cyan); box-shadow:0 0 12px rgba(0,212,255,0.5); }
  #send-btn svg { width:16px; height:16px; color:#fff; margin-left:2px; }

  /* Clock */
  #clock-panel { flex-shrink:0; height:130px; }
  #clock-inner {
    display:flex; align-items:center; justify-content:space-between;
    padding:10px 16px; height:100%;
  }
  .clock-left { }
  .clock-time { display:flex; align-items:baseline; gap:6px; }
  .clock-digits {
    font-family:'Orbitron',sans-serif; font-size:38px; font-weight:900;
    color:var(--text); line-height:1; letter-spacing:2px;
  }
  .clock-ampm { font-family:'Orbitron',sans-serif; font-size:13px; color:var(--muted); font-weight:600; }
  .clock-date { font-size:12px; color:var(--muted); margin-top:6px; letter-spacing:0.5px; }
  #analog-canvas { width:88px; height:88px; flex-shrink:0; }

  /* System Controls */
  #sys-ctrl { flex-shrink:0; }
  .ctrl-row { display:flex; justify-content:space-around; padding:10px 12px; }
  .ctrl-btn { display:flex; flex-direction:column; align-items:center; gap:6px; cursor:pointer; }
  .ctrl-circle {
    width:46px; height:46px; border-radius:50%;
    border:2px solid var(--border2); background:var(--panel2);
    display:flex; align-items:center; justify-content:center;
    transition:all 0.2s;
  }
  .ctrl-btn:hover .ctrl-circle { box-shadow:0 0 16px currentColor; }
  .ctrl-btn.power .ctrl-circle { border-color:var(--red); color:var(--red); }
  .ctrl-btn.power .ctrl-circle svg { color:var(--red); }
  .ctrl-btn.power:hover .ctrl-circle { background:rgba(255,59,48,0.15); }
  .ctrl-btn:not(.power) .ctrl-circle { border-color:var(--cyan2); color:var(--cyan); }
  .ctrl-btn:not(.power) .ctrl-circle svg { color:var(--cyan); }
  .ctrl-btn:not(.power):hover .ctrl-circle { background:rgba(0,150,200,0.15); }
  .ctrl-circle svg { width:20px; height:20px; }
  .ctrl-btn span { font-size:9px; color:var(--muted); font-weight:600; letter-spacing:0.5px; }

  /* JARVIS Core */
  #jarvis-core { flex:1; overflow:hidden; }
  .core-inner { display:flex; align-items:flex-start; padding:10px 14px; gap:10px; height:100%; }
  .ironman-figure { flex-shrink:0; width:70px; }
  #ironman-canvas { width:70px; height:130px; display:block; }
  .core-status { flex:1; }
  .status-item {
    display:flex; align-items:center; justify-content:space-between;
    padding:5px 0; border-bottom:1px solid rgba(26,51,86,0.5);
  }
  .status-item:last-child { border-bottom:none; }
  .status-name { font-size:11px; color:var(--muted); font-weight:500; }
  .status-online {
    font-size:10px; color:var(--green); font-weight:700; letter-spacing:1px;
    text-shadow:0 0 8px rgba(0,229,160,0.5);
    animation:flicker 4s infinite;
  }
  @keyframes flicker { 0%,95%,100%{opacity:1} 97%{opacity:0.7} }

  /* ── BOTTOM BAR ── */
  #bottombar {
    height:40px; background:var(--bg2); border-top:1px solid var(--border);
    display:flex; align-items:center; padding:0 16px; flex-shrink:0;
    position:relative;
  }
  .bar-left { display:flex; align-items:center; gap:8px; }
  .bar-left svg { width:14px; height:14px; color:var(--muted); }
  .bar-left span { font-size:11px; color:var(--muted); }
  .bar-dot { width:7px; height:7px; background:var(--green); border-radius:50%;
             box-shadow:0 0 6px var(--green); }
  .bar-center {
    position:absolute; left:50%; transform:translateX(-50%);
  }
  #center-ring-canvas { width:36px; height:36px; display:block; }

  /* ── TOOLS VIEW ── */
  .tools-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(160px, 1fr)); gap:15px; padding:20px; }
  .tool-card { background:var(--panel2); border:1px solid var(--border); border-radius:12px; padding:25px; display:flex; flex-direction:column; align-items:center; gap:15px; cursor:pointer; transition:all 0.3s; }
  .tool-card:hover { border-color:var(--cyan); transform:translateY(-5px); box-shadow:0 10px 20px rgba(0,0,0,0.4); }
  .tool-card svg { width:40px; height:40px; color:var(--cyan); }
  .tool-card h3 { font-size:14px; color:var(--text); letter-spacing:1px; font-family: 'Orbitron'; }

  /* ── MEMORY VIEW ── */
  .memory-container { padding: 20px; display: flex; flex-direction: column; gap: 10px; overflow-y: auto; }
  .mem-entry { background: var(--panel2); border-left: 4px solid var(--orange); padding: 15px; border-radius: 4px; }
  .mem-time { font-family: var(--font-mono); font-size: 11px; color: var(--orange); margin-bottom: 5px; }
  .mem-text { font-size: 14px; color: var(--text); }

  /* ── SYSTEM VIEW ── */
  .sys-info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; padding: 25px; }
  .sys-info-item { background: var(--panel2); padding: 20px; border-radius: 8px; border: 1px solid var(--border); }
  .sys-info-label { font-family: 'Orbitron'; font-size: 11px; color: var(--muted); margin-bottom: 8px; }
  .sys-info-val { font-family: var(--font-mono); font-size: 18px; color: var(--cyan); }

  #toast { position:fixed; bottom:56px; left:50%; transform:translateX(-50%);
      background:#0f2540; border:1px solid #1e4a72; color:#00d4ff; padding:8px 20px;
      border-radius:20px; font-size:12px; font-family:Rajdhani,monospace;
      box-shadow:0 0 16px rgba(0,150,200,0.3); z-index:9999; letter-spacing:1px;
      transition:opacity 0.3s; opacity: 0; pointer-events: none; }
</style>
</head>
<body>
<div id="app">

  <!-- ── TITLE BAR ── -->
  <div id="titlebar">
    <div class="brand">
      <div class="brand-icon">
        <svg viewBox="0 0 32 32" fill="none">
          <polygon points="16,2 28,8 28,24 16,30 4,24 4,8" fill="#1a0505" stroke="#ff4422" stroke-width="1.5"/>
          <text x="16" y="21" text-anchor="middle" fill="white" font-size="12" font-weight="bold" font-family="monospace">J</text>
        </svg>
      </div>
      <div class="brand-text">
        <h1>JARVIS OS</h1>
        <div class="online-badge"><div class="online-dot"></div><span class="online-text">ONLINE</span></div>
      </div>
    </div>

    <div class="title-center">
      <h2>JARVIS</h2>
      <span>v2.5.0</span>
    </div>

    <nav class="nav">
      <button class="nav-btn active" onclick="switchTab(this,'Main')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/></svg>
        Main
      </button>
      <button class="nav-btn" onclick="switchTab(this,'Tools')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/></svg>
        Tools
      </button>
      <button class="nav-btn" onclick="switchTab(this,'Memory')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 8v4l3 3"/></svg>
        Memory
      </button>
      <button class="nav-btn" onclick="switchTab(this,'System')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.07 4.93l-1.41 1.41M4.93 4.93l1.41 1.41M12 2v2m0 18v-2"/></svg>
        System
      </button>
    </nav>

    <div class="win-btns">
      <button class="win-btn" onclick="window.pywebview.api.minimize()" title="Minimize">&#8722;</button>
      <button class="win-btn close" onclick="window.pywebview.api.close_app()" title="Close">&#10005;</button>
    </div>
  </div>

  <!-- ── CONTENT ── -->
  <div id="content">

    <!-- MAIN VIEW -->
    <div id="view-Main" class="view active">
      <div class="col-side">
        <div class="panel" id="jarvis-circle-panel"><canvas id="jarvis-canvas"></canvas></div>
        <div class="panel">
          <div class="panel-header">SYSTEM STATUS</div>
          <div class="metric-row">
            <div class="metric-top"><span class="metric-label">CPU Usage</span><span class="metric-val" id="cpu-val">23%</span></div>
            <div class="sparkline-wrap"><canvas class="sparkline" id="spark-cpu"></canvas></div>
          </div>
          <div class="metric-row">
            <div class="metric-top"><span class="metric-label">RAM Usage</span><span class="metric-val" id="ram-val">45%</span></div>
            <div class="sparkline-wrap"><canvas class="sparkline" id="spark-ram"></canvas></div>
          </div>
          <div class="metric-row" style="padding-bottom:8px">
            <div class="metric-top"><span class="metric-label">Network</span><span class="metric-val" id="net-val">120.4 Mbps</span></div>
            <div class="sparkline-wrap"><canvas class="sparkline" id="spark-net"></canvas></div>
          </div>
        </div>
        <div class="panel">
          <div class="panel-header">QUICK ACCESS</div>
          <div class="qa-grid">
            <div class="qa-btn" onclick="qaAction('files')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/></svg><span>Files</span></div>
            <div class="qa-btn" onclick="qaAction('terminal')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg><span>Term</span></div>
            <div class="qa-btn" onclick="qaAction('browser')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 014 10"/></svg><span>Web</span></div>
          </div>
        </div>
      </div>

      <div class="col-center">
        <div class="panel" id="greeting-panel">
          <div id="greeting-inner">
            <h2 id="greeting-text">Good Evening, Tony Stark</h2>
            <p>How can I help you today?</p>
            <canvas id="wave-canvas"></canvas>
            <div id="mic-btn" onclick="toggleMic()">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z"/><path d="M19 10v2a7 7 0 01-14 0v-2"/></svg>
            </div>
          </div>
        </div>
        <div class="panel">
          <div class="panel-header">JARVIS ACTIVITIES</div>
          <div class="activities-row">
            <div class="activity-btn" onclick="activity('chat')"><div class="act-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg></div><span>AI Chat</span></div>
            <div class="activity-btn" onclick="activity('search')"><div class="act-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg></div><span>Web Search</span></div>
            <div class="activity-btn" onclick="activity('code')"><div class="act-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg></div><span>Code Assistant</span></div>
          </div>
        </div>
        <div class="panel" id="chat-panel">
          <div class="panel-header">CONVERSATION</div>
          <div id="chat-area"></div>
          <div id="chat-input-row">
            <input id="chat-input" type="text" placeholder="Ask anything..." onkeydown="if(event.key==='Enter')sendMsg()">
            <button id="send-btn" onclick="sendMsg()"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M22 2L11 13 2 9l20-7z"/></svg></button>
          </div>
        </div>
      </div>

      <div class="col-side">
        <div class="panel" id="clock-panel">
          <div id="clock-inner">
            <div class="clock-left">
              <div class="clock-time"><div class="clock-digits" id="clock-h">09:35</div><div class="clock-ampm" id="clock-ampm">PM</div></div>
              <div class="clock-date" id="clock-date">Friday, 24 May 2024</div>
            </div>
            <canvas id="analog-canvas" width="88" height="88"></canvas>
          </div>
        </div>
        <div class="panel" id="sys-ctrl">
          <div class="panel-header">SYSTEM CONTROLS</div>
          <div class="ctrl-row">
            <div class="ctrl-btn power" onclick="sysAction('shutdown')"><div class="ctrl-circle"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18.36 6.64a9 9 0 11-12.73 0"/><line x1="12" y1="2" x2="12" y2="12"/></svg></div><span>Shut Down</span></div>
            <div class="ctrl-btn" onclick="sysAction('restart')"><div class="ctrl-circle"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 102.13-9.36L1 10"/></svg></div><span>Restart</span></div>
          </div>
        </div>
        <div class="panel" id="jarvis-core">
          <div class="panel-header">JARVIS CORE</div>
          <div class="core-inner">
            <div class="ironman-figure"><canvas id="ironman-canvas" width="70" height="130"></canvas></div>
            <div class="core-status">
              <div class="status-item"><span class="status-name">AI System</span><span class="status-online">ONLINE</span></div>
              <div class="status-item"><span class="status-name">Memory System</span><span class="status-online">ONLINE</span></div>
              <div class="status-item"><span class="status-name">Vision System</span><span class="status-online">ONLINE</span></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- TOOLS VIEW -->
    <div id="view-Tools" class="view">
      <div style="grid-column: span 3;">
        <div class="panel" style="height: 100%;">
          <div class="panel-header">ADVANCED SYSTEM TOOLS</div>
          <div class="tools-grid">
            <div class="tool-card" onclick="qaAction('terminal')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg><h3>TERMINAL</h3></div>
            <div class="tool-card" onclick="qaAction('files')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/></svg><h3>FILE SYSTEM</h3></div>
            <div class="tool-card" onclick="qaAction('browser')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 014 10"/></svg><h3>WEB ACCESS</h3></div>
            <div class="tool-card" onclick="activity('Scanner')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg><h3>SCANNER</h3></div>
          </div>
        </div>
      </div>
    </div>

    <!-- MEMORY VIEW -->
    <div id="view-Memory" class="view">
      <div style="grid-column: span 3;">
        <div class="panel" style="height: 100%;">
          <div class="panel-header">NEURAL MEMORY LOGS</div>
          <div class="memory-container" id="memory-list"></div>
        </div>
      </div>
    </div>

    <!-- SYSTEM VIEW -->
    <div id="view-System" class="view">
      <div style="grid-column: span 3;">
        <div class="panel" style="height: 100%;">
          <div class="panel-header">STARK INDUSTRIES SYSTEM SPECS</div>
          <div class="sys-info-grid">
            <div class="sys-info-item"><div class="sys-info-label">PROCESSOR</div><div class="sys-info-val">STARK-X9 NEURAL</div></div>
            <div class="sys-info-item"><div class="sys-info-label">OS VERSION</div><div class="sys-info-val">v2.5.0-JARVIS</div></div>
            <div class="sys-info-item"><div class="sys-info-label">ENCRYPTION</div><div class="sys-info-val">AES-1024 QUANTUM</div></div>
            <div class="sys-info-item"><div class="sys-info-label">LOCATION</div><div class="sys-info-val">MALIBU HQ</div></div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- BOTTOM BAR -->
  <div id="bottombar">
    <div class="bar-left">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/></svg>
      <span>Jarvis Main Interface</span>
      <div class="bar-dot"></div>
    </div>
    <div class="bar-center"><canvas id="center-ring-canvas" width="36" height="36"></canvas></div>
  </div>

</div>
<div id="toast"></div>

<script>
// ── State ──────────────────────────────────────────────────────────────────
let micActive = false, animTick = 0;
let sparkData = { cpu: Array(40).fill(20), ram: Array(40).fill(40), net: Array(40).fill(10) };
let waveHistory = Array(120).fill(0);

// ── Clock ──────────────────────────────────────────────────────────────────
function updateClock() {
  const now = new Date();
  let h = now.getHours() % 12 || 12;
  let m = String(now.getMinutes()).padStart(2,'0');
  let ampm = now.getHours() < 12 ? 'AM' : 'PM';
  document.getElementById('clock-h').textContent = `${String(h).padStart(2,'0')}:${m}`;
  document.getElementById('clock-ampm').textContent = ampm;
  const days = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  document.getElementById('clock-date').textContent = `${days[now.getDay()]}, ${now.getDate()} ${months[now.getMonth()]} ${now.getFullYear()}`;
  const greet = now.getHours() < 12 ? 'Good Morning' : now.getHours() < 18 ? 'Good Afternoon' : 'Good Evening';
  document.getElementById('greeting-text').textContent = `${greet}, Tony Stark`;
}
setInterval(updateClock, 1000); updateClock();

// ── Analog Clock ──────────────────────────────────────────────────────────
function drawAnalog() {
  const c = document.getElementById('analog-canvas'); if (!c) return;
  const ctx = c.getContext('2d'), cx = 44, cy = 44, r = 40, now = new Date();
  ctx.clearRect(0,0,88,88);
  ctx.beginPath(); ctx.arc(cx,cy,r,0,Math.PI*2); ctx.strokeStyle='#1e4a72'; ctx.lineWidth=1.5; ctx.stroke();
  ctx.beginPath(); ctx.arc(cx,cy,r-1,0,Math.PI*2); ctx.fillStyle='#06090f'; ctx.fill();
  for (let i=0; i<12; i++) {
    const a = (i/12)*Math.PI*2 - Math.PI/2, r1 = i%3===0 ? r-6 : r-4;
    ctx.beginPath(); ctx.moveTo(cx+r1*Math.cos(a), cy+r1*Math.sin(a)); ctx.lineTo(cx+(r-1)*Math.cos(a), cy+(r-1)*Math.sin(a));
    ctx.strokeStyle = i%3===0 ? '#1e4a72' : '#0f2a40'; ctx.lineWidth = i%3===0 ? 2 : 1; ctx.stroke();
  }
  const ha = ((now.getHours()%12 + now.getMinutes()/60)/12)*Math.PI*2 - Math.PI/2;
  ctx.beginPath(); ctx.moveTo(cx,cy); ctx.lineTo(cx+22*Math.cos(ha), cy+22*Math.sin(ha)); ctx.strokeStyle='#ff6030'; ctx.lineWidth=2.5; ctx.stroke();
  const ma = (now.getMinutes()/60)*Math.PI*2 - Math.PI/2;
  ctx.beginPath(); ctx.moveTo(cx,cy); ctx.lineTo(cx+30*Math.cos(ma), cy+30*Math.sin(ma)); ctx.strokeStyle='#ff4020'; ctx.lineWidth=1.5; ctx.stroke();
  const sa = (now.getSeconds()/60)*Math.PI*2 - Math.PI/2;
  ctx.beginPath(); ctx.moveTo(cx,cy); ctx.lineTo(cx+33*Math.cos(sa), cy+33*Math.sin(sa)); ctx.strokeStyle='#ff2000'; ctx.lineWidth=1; ctx.stroke();
  ctx.beginPath(); ctx.arc(cx,cy,3,0,Math.PI*2); ctx.fillStyle='#ff4020'; ctx.fill();
}

// ── JARVIS Circle ─────────────────────────────────────────────────────────
function drawJarvisCircle() {
  const c = document.getElementById('jarvis-canvas'); if (!c) return;
  const w = c.width = c.offsetWidth, h = c.height = c.offsetHeight, ctx = c.getContext('2d'), cx = w/2, cy = h/2, t = animTick * 0.04;
  ctx.clearRect(0,0,w,h);
  const rings = [{r:82, s:0.4, d:[4,8], c:'rgba(0,180,220,0.35)'}, {r:68, s:-0.6, d:[8,4], c:'rgba(0,150,200,0.45)'}, {r:54, s:0.8, d:[3,6], c:'rgba(0,180,220,0.3)'}, {r:40, s:-1.1, d:[6,3], c:'rgba(0,212,255,0.4)'}];
  rings.forEach(r => {
    ctx.save(); ctx.translate(cx, cy); ctx.rotate(t * r.s); ctx.beginPath(); ctx.arc(0,0,r.r,0,Math.PI*2); ctx.setLineDash(r.d); ctx.strokeStyle=r.c; ctx.lineWidth=1; ctx.stroke();
    ctx.beginPath(); ctx.arc(r.r,0,3,0,Math.PI*2); ctx.fillStyle='#00d4ff'; ctx.fill(); ctx.restore();
  });
  ctx.font='bold 11px Orbitron'; ctx.fillStyle='#00d4ff'; ctx.textAlign='center'; ctx.fillText('JARVIS', cx, cy);
}

// ── Waveform ───────────────────────────────────────────────────────────────
function drawWave() {
  const c = document.getElementById('wave-canvas'); if (!c) return;
  const ctx = c.getContext('2d'), w = c.width = c.offsetWidth, h = 52, mid = 26;
  waveHistory.shift(); waveHistory.push(micActive ? (Math.random()-0.5)*38 : Math.sin(animTick*0.08)*10 + Math.sin(animTick*0.16)*5);
  ctx.clearRect(0,0,w,h); ctx.beginPath(); ctx.moveTo(0,mid);
  waveHistory.forEach((v,i)=> ctx.lineTo(i*(w/120), mid-v));
  ctx.strokeStyle='rgba(0,212,255,0.8)'; ctx.lineWidth=1.5; ctx.stroke();
}

// ── Iron Man ───────────────────────────────────────────────────────────────
function drawIronMan() {
  const c = document.getElementById('ironman-canvas'); if (!c) return;
  const ctx = c.getContext('2d'); ctx.clearRect(0,0,70,130);
  const bodyFill = '#0c1a2e', lineC = '#1a5080';
  ctx.beginPath(); ctx.roundRect(22,4,26,26,4); ctx.fillStyle=bodyFill; ctx.strokeStyle=lineC; ctx.fill(); ctx.stroke();
  ctx.beginPath(); ctx.roundRect(25,10,20,10,3); ctx.fillStyle='#006aaa'; ctx.stroke();
  [[27,13],[43,13]].forEach(([x,y])=>{ ctx.beginPath(); ctx.ellipse(x,y,4,2.5,0,0,Math.PI*2); ctx.fillStyle='#00d4ff'; ctx.fill(); });
  ctx.beginPath(); ctx.roundRect(14,32,42,38,3); ctx.fillStyle=bodyFill; ctx.strokeStyle=lineC; ctx.fill(); ctx.stroke();
  ctx.beginPath(); ctx.arc(35,52,8,0,Math.PI*2); ctx.fillStyle='#00d4ff33'; ctx.strokeStyle='#00d4ff'; ctx.fill(); ctx.stroke();
}

// ── Helpers ───────────────────────────────────────────────────────────────
function drawSparkline(id, data, color) {
  const c = document.getElementById(id); if (!c) return;
  const ctx = c.getContext('2d'), w = c.width = c.offsetWidth, h = 16;
  ctx.clearRect(0,0,w,h); ctx.beginPath();
  data.slice(-40).forEach((v,i) => { const x = i*(w/39), y = h - (v/100)*12 - 2; i===0 ? ctx.moveTo(x,y) : ctx.lineTo(x,y); });
  ctx.strokeStyle=color; ctx.lineWidth=1.5; ctx.stroke();
}

function drawCenterRing() {
  const c = document.getElementById('center-ring-canvas'); if (!c) return;
  const ctx = c.getContext('2d'), cx=18,cy=18,r=15; ctx.clearRect(0,0,36,36);
  ctx.beginPath(); ctx.arc(cx,cy,r,0,Math.PI*2); ctx.strokeStyle='#1e4a72'; ctx.stroke();
  ctx.beginPath(); ctx.arc(cx,cy,r,-Math.PI/2, -Math.PI/2+(animTick*0.05)); ctx.strokeStyle='#00d4ff'; ctx.lineWidth=2; ctx.stroke();
}

function updateStats() {
  if (window.pywebview) {
    window.pywebview.api.get_stats().then(raw => {
      const s = JSON.parse(raw);
      sparkData.cpu.push(s.cpu); sparkData.cpu.shift();
      sparkData.ram.push(s.ram); sparkData.ram.shift();
      sparkData.net.push(Math.min(s.net,100)); sparkData.net.shift();
      document.getElementById('cpu-val').textContent = s.cpu.toFixed(0)+'%';
      document.getElementById('ram-val').textContent = s.ram.toFixed(0)+'%';
      document.getElementById('net-val').textContent = s.net.toFixed(1)+' Mbps';
    });
  }
  drawSparkline('spark-cpu', sparkData.cpu, '#00d4ff');
  drawSparkline('spark-ram', sparkData.ram, '#00d4ff');
  drawSparkline('spark-net', sparkData.net, '#ff8c42');
}
setInterval(updateStats, 2000);

function animate() { animTick++; drawJarvisCircle(); drawWave(); drawCenterRing(); if (animTick%60===0) drawAnalog(); requestAnimationFrame(animate); }
animate(); drawIronMan();

function switchTab(el, name) {
  document.querySelectorAll('.nav-btn').forEach(b=>b.classList.remove('active'));
  el.classList.add('active');
  document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));
  document.getElementById('view-' + name).classList.add('active');
  showToast('ACCESSING ' + name.toUpperCase() + '...');
}

function escHtml(t) {
  return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function sendMsg() {
  const i = document.getElementById('chat-input'), t = i.value.trim(); if (!t) return; i.value = '';
  const a = document.getElementById('chat-area'), ts = new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});
  const u = document.createElement('div'); u.className = 'msg-user';
  u.innerHTML = `<div class="msg-sender-label">You</div><div class="bubble">${escHtml(t)}</div><div class="msg-meta">${ts}</div>`;
  a.appendChild(u);
  addMemoryEntry('User Command: ' + t);
  setTimeout(() => {
    const j = document.createElement('div'); j.className = 'msg-jarvis';
    j.innerHTML = `<div class="jarvis-label">JARVIS</div><div class="bubble">Processing: "${escHtml(t)}". All systems nominal, sir.</div><div class="msg-meta">${ts}</div>`;
    a.appendChild(j); a.scrollTop = a.scrollHeight;
  }, 800); a.scrollTop = a.scrollHeight;
}

function addMemoryEntry(text) {
  const m = document.getElementById('memory-list'), e = document.createElement('div'), ts = new Date().toLocaleTimeString();
  e.className = 'mem-entry'; e.innerHTML = `<div class="mem-time">${ts}</div><div class="mem-text">${escHtml(text)}</div>`;
  m.prepend(e);
}

function qaAction(t) { if (window.pywebview) window.pywebview.api.execute_action(t); showToast('Opening ' + t + '...'); addMemoryEntry('System Action: ' + t); }
function activity(t) { showToast(t + ' ready'); addMemoryEntry('Module Activated: ' + t); }
function sysAction(t) { if (t==='shutdown' && confirm('Shut down?')) window.pywebview.api.close_app(); else showToast('Executing ' + t + '...'); }
function toggleMic() { micActive = !micActive; document.getElementById('mic-btn').classList.toggle('active', micActive); }
function showToast(m) { const t = document.getElementById('toast'); t.textContent = m; t.style.opacity='1'; setTimeout(()=>t.style.opacity='0', 2000); }

addMemoryEntry('JARVIS OS v2.5.0 Boot Sequence Complete.');
</script>
</body>
</html>
"""

# ── Bootstrap ────────────────────────────────────────────────────────────────
def main():
    api = JarvisAPI()

    # In headless environments, we might not be able to actually start the window,
    # but we can verify everything is set up correctly.

    window = webview.create_window(
        "JARVIS OS v2.5.0",
        html=HTML,
        js_api=api,
        width=1400,
        height=860,
        min_size=(1100, 700),
        frameless=True,
        background_color="#06090f",
    )
    api.set_window(window)

    # Start the application
    webview.start(debug=False)

if __name__ == "__main__":
    main()
