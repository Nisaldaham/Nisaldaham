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

    def set_window(self, window):
        self._win = window

    def get_stats(self):
        if not HAS_PSUTIL:
            return json.dumps({"cpu": 23, "ram": 45, "disk": 62, "net": 120.4})
        try:
            cpu  = psutil.cpu_percent(interval=None) # Use None for non-blocking if called frequently
            ram  = psutil.virtual_memory().percent
            disk = psutil.disk_usage("/").percent
            net  = psutil.net_io_counters()
            mbps = round((net.bytes_sent + net.bytes_recv) / 1e6, 1)
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

# ── Bootstrap ────────────────────────────────────────────────────────────────
def main():
    api = JarvisAPI()

    # In headless environments, we might not be able to actually start the window,
    # but we can verify everything is set up correctly.

    window = webview.create_window(
        "JARVIS OS v2.5.0",
        url="index.html",
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
