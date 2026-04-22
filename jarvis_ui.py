import json
import math
import os
import random
import time
import tkinter as tk
from collections import deque
from pathlib import Path
import sys
from tkinter import filedialog

from PIL import Image, ImageDraw, ImageTk
import psutil


def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR = get_base_dir()
CONFIG_DIR = BASE_DIR / "config"
API_FILE = CONFIG_DIR / "api_keys.json"

SYSTEM_NAME = "J.A.R.V.I.S"
MODEL_BADGE = "MARK XXX COMMAND CENTER"

C_BG = "#02070d"
C_BG2 = "#051521"
C_PANEL = "#07131b"
C_PANEL_ALT = "#0b1b26"
C_PRI = "#64f1ff"
C_PRI_SOFT = "#25bfd1"
C_TEXT = "#e8fbff"
C_MUTED = "#79a7b5"
C_DIM = "#173849"
C_LINE = "#123242"
C_ACC = "#ffc857"
C_RED = "#ff5d5d"
C_GREEN = "#2ef0a3"
# ── HUD v3.1 TOKENS ──
C_GLOW = "#1a8694"
C_STREAM = "#0a222e"
C_HEX = "#081b26"
C_BRACKET = "#123242"
C_GRID = "#061822"


class JarvisUI:
    def __init__(self, face_path, size=None, sfx=None):
        self.sfx = sfx
        self.root = tk.Tk()
        self.root.title("J.A.R.V.I.S Command Center")
        self.root.resizable(False, False)

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.W = min(sw, 1380)
        self.H = min(sh, 920)
        self.root.geometry(f"{self.W}x{self.H}+{(sw-self.W)//2}+{(sh-self.H)//2}")
        self.root.configure(bg=C_BG)

        self.FACE_SZ = 360
        self.FCX = self.W // 2
        self.FCY = self.H // 2 - 30

        self.speaking = False
        self.is_muted = False
        self.is_sleeping = False
        self.status_text = "COMMAND CENTER READY"
        self.mode_title = "Adaptive Intelligence"
        self.mode_detail = "Awaiting directives."
        self.tick = 0
        self.scale = 1.0
        self.target_scale = 1.0
        self.angle_1 = 0.0
        self.angle_2 = 0.0
        self.angle_3 = 0.0
        self.angle_4 = 0.0
        self.angle_5 = 0.0
        self.globe_angle = 0.0
        self.scan_y = 0.0
        self.grid_offset = 0.0
        self.stream_pts = []
        self._init_data_streams()
        self.last_traffic = psutil.net_io_counters()
        self.brainwave_pts = deque([self.H - 175] * 60, maxlen=60)
        self.mission_items = []
        self.recommendations = [
            "Use /status for a full system snapshot.",
            "Use /focus to engage Focus Protocol.",
            "Use 'note ...' to save a mission item instantly.",
        ]
        self.quick_action_callback = None
        self.clock_text = time.strftime("%H:%M:%S")
        self.date_text = time.strftime("%d %b %Y").upper()
        self.glitch_tick = 0
        self.boot_tick = 100
        self.snapshot = {}

        self.on_text_submit = None
        self.on_file_upload = None
        self.on_mute_toggle = None

        self._face_pil = None
        self._face_scale_cache = None
        self._has_face = False
        self._load_face(face_path)

        self.bg = tk.Canvas(self.root, width=self.W, height=self.H, bg=C_BG, highlightthickness=0)
        self.bg.place(x=0, y=0)

        self._setup_panels()
        self._setup_bindings()

        self._api_key_ready = self._api_keys_exist()
        if not self._api_key_ready:
            self._show_setup_ui()

        self._animate()
        self._update_live_metrics()
        self._update_clock()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_panels(self):
        left_x = 20
        right_x = self.W - 370
        top_y = 105
        column_h = self.H - 245

        self.left_frame = self._make_panel(left_x, top_y, 320, column_h, "SYSTEM TELEMETRY")
        self.right_frame = self._make_panel(right_x, top_y, 350, 300, "NEURAL DIALOGUE")
        self.mission_frame = self._make_panel(right_x, top_y + 315, 350, 150, "MISSION BOARD")
        self.sat_frame = self._make_panel(right_x, top_y + 480, 350, 140, "ORBITAL TELEMETRY")
        self.quick_frame = self._make_panel(355, self.H - 190, self.W - 745, 70, "QUICK ACTION DOCK")
        self.bottom_frame = self._make_panel(20, self.H - 105, self.W - 40, 78, "COMMAND INPUT")

        self._build_left_panel()
        self._build_right_panel()
        self._build_mission_panel()
        self._build_sat_panel()
        self._build_quick_dock()
        self._build_bottom_bar()

    def _make_panel(self, x, y, width, height, title):
        # Main panel container with subtle glass-like border
        frame = tk.Frame(self.root, bg=C_PANEL, highlightbackground=C_LINE, highlightthickness=1)
        frame.place(x=x, y=y, width=width, height=height)

        # High-tech corner brackets (Canvas for vector precision)
        ornament = tk.Canvas(frame, bg=C_PANEL, height=height, width=width, highlightthickness=0)
        ornament.place(x=0, y=0, relwidth=1, relheight=1)

        def _draw_brackets(e=None):
            ornament.delete("orn")
            w, h = ornament.winfo_width(), ornament.winfo_height()
            ext = 12
            # Corner Brackets
            for x1, y1, x2, y2 in [(0,0,ext,0), (0,0,0,ext), (w-ext,0,w,0), (w,0,w,ext), (0,h-ext,0,h), (0,h,ext,h), (w-ext,h,w,h), (w,h-ext,w,h)]:
                ornament.create_line(x1, y1, x2, y2, fill=C_PRI_SOFT, width=2, tags="orn")
        ornament.bind("<Configure>", _draw_brackets)

        header = tk.Frame(frame, bg=C_PANEL_ALT, height=32)
        header.pack(fill="x", pady=(2, 0))
        tk.Label(
            header,
            text=f"// {title}",
            fg=C_PRI,
            bg=C_PANEL_ALT,
            font=("Bahnschrift SemiBold", 10),
            anchor="w",
            padx=12,
        ).pack(fill="both", expand=True)
        return frame

    def _build_left_panel(self):
        body = tk.Frame(self.left_frame, bg=C_PANEL)
        body.pack(fill="both", expand=True, padx=12, pady=12)

        self.metric_vars = {
            "CPU": tk.StringVar(value="0%"),
            "RAM": tk.StringVar(value="0%"),
            "NET": tk.StringVar(value="0 MB/s"),
            "TEMP": tk.StringVar(value="N/A"),
        }
        self.metric_bars = {}

        for name, var in self.metric_vars.items():
            row = tk.Frame(body, bg=C_PANEL)
            row.pack(fill="x", pady=(0, 10))
            tk.Label(row, text=name, fg=C_MUTED, bg=C_PANEL, font=("Consolas", 9, "bold")).pack(side="left")
            tk.Label(row, textvariable=var, fg=C_TEXT, bg=C_PANEL, font=("Consolas", 9, "bold")).pack(side="right")
            bar_bg = tk.Frame(body, bg=C_DIM, height=4)
            bar_bg.pack(fill="x", pady=(2, 10))
            bar = tk.Frame(bar_bg, bg=C_PRI, height=4, width=0)
            bar.place(x=0, y=0)
            self.metric_bars[name] = (bar, 292)

        mode_wrap = tk.Frame(body, bg=C_PANEL_ALT, highlightbackground=C_LINE, highlightthickness=1)
        mode_wrap.pack(fill="x", pady=(4, 12))
        tk.Label(mode_wrap, text="ACTIVE MODE", fg=C_MUTED, bg=C_PANEL_ALT, font=("Consolas", 8)).pack(anchor="w", padx=10, pady=(8, 0))
        self.mode_title_var = tk.StringVar(value=self.mode_title)
        self.mode_detail_var = tk.StringVar(value=self.mode_detail)
        tk.Label(mode_wrap, textvariable=self.mode_title_var, fg=C_ACC, bg=C_PANEL_ALT, font=("Bahnschrift SemiBold", 13)).pack(anchor="w", padx=10, pady=(2, 0))
        tk.Label(mode_wrap, textvariable=self.mode_detail_var, fg=C_TEXT, bg=C_PANEL_ALT, wraplength=280, justify="left", font=("Consolas", 9)).pack(anchor="w", padx=10, pady=(0, 10))

        detail_wrap = tk.Frame(body, bg=C_PANEL)
        detail_wrap.pack(fill="x", pady=(0, 10))
        self.detail_vars = {
            "HOST": tk.StringVar(value="Standby"),
            "POWER": tk.StringVar(value="Unknown"),
            "UPTIME": tk.StringVar(value="Tracking"),
            "DISK": tk.StringVar(value="Waiting"),
        }
        for key, var in self.detail_vars.items():
            row = tk.Frame(detail_wrap, bg=C_PANEL)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=key, fg=C_MUTED, bg=C_PANEL, font=("Consolas", 8)).pack(side="left")
            tk.Label(row, textvariable=var, fg=C_PRI, bg=C_PANEL, font=("Consolas", 8, "bold")).pack(side="right")

        tk.Label(body, text="ACTIVITY FEED", fg=C_MUTED, bg=C_PANEL, font=("Consolas", 9, "bold")).pack(anchor="w", pady=(8, 5))
        self.log_text = tk.Text(
            body,
            fg=C_TEXT,
            bg=C_BG2,
            font=("Consolas", 8),
            borderwidth=0,
            wrap="word",
            padx=10,
            pady=10,
            height=13,
        )
        self.log_text.pack(fill="both", expand=True)
        self.log_text.configure(state="disabled")

    def _build_right_panel(self):
        body = tk.Frame(self.right_frame, bg=C_PANEL)
        body.pack(fill="both", expand=True, padx=12, pady=12)

        self.ai_text = tk.Text(
            body,
            fg=C_TEXT,
            bg=C_BG2,
            font=("Consolas", 10),
            borderwidth=0,
            wrap="word",
            padx=12,
            pady=12,
            insertbackground=C_PRI,
        )
        self.ai_text.pack(fill="both", expand=True)
        self.ai_text.configure(state="disabled")
        self.ai_text.tag_config("ai", foreground=C_PRI, font=("Bahnschrift SemiBold", 10))
        self.ai_text.tag_config("user", foreground=C_ACC, font=("Bahnschrift SemiBold", 10))
        self.ai_text.tag_config("sys", foreground=C_GREEN, font=("Bahnschrift SemiBold", 10))

    def _build_mission_panel(self):
        body = tk.Frame(self.mission_frame, bg=C_PANEL)
        body.pack(fill="both", expand=True, padx=12, pady=12)

        tk.Label(body, text="OPEN MISSIONS", fg=C_MUTED, bg=C_PANEL, font=("Consolas", 9, "bold")).pack(anchor="w")
        self.mission_list = tk.Listbox(
            body,
            bg=C_BG2,
            fg=C_TEXT,
            borderwidth=0,
            highlightthickness=0,
            selectbackground=C_DIM,
            selectforeground=C_TEXT,
            font=("Consolas", 9),
            height=3,
        )
        self.mission_list.pack(fill="x", pady=(6, 12))

        tk.Label(body, text="RECOMMENDATIONS", fg=C_MUTED, bg=C_PANEL, font=("Consolas", 9, "bold")).pack(anchor="w")
        self.reco_text = tk.Text(
            body,
            bg=C_BG2,
            fg=C_PRI,
            borderwidth=0,
            highlightthickness=0,
            height=2,
            wrap="word",
            padx=10,
            pady=10,
            font=("Consolas", 8),
        )
        self.reco_text.pack(fill="both", expand=True, pady=(6, 0))
        self.reco_text.configure(state="disabled")
        self._render_recommendations()

    def _build_sat_panel(self):
        body = tk.Frame(self.sat_frame, bg=C_PANEL)
        body.pack(fill="both", expand=True, padx=12, pady=12)

        self.sat_vars = {
            "ID": tk.StringVar(value="STARK-01"),
            "ALT": tk.StringVar(value="35,786 km"),
            "LAT": tk.StringVar(value="0.00°"),
            "LON": tk.StringVar(value="0.00°"),
            "STATUS": tk.StringVar(value="SYNCHRONIZED")
        }

        for key, var in self.sat_vars.items():
            row = tk.Frame(body, bg=C_PANEL)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=key, fg=C_MUTED, bg=C_PANEL, font=("Consolas", 8)).pack(side="left")
            tk.Label(row, textvariable=var, fg=C_ACC, bg=C_PANEL, font=("Consolas", 8, "bold")).pack(side="right")

    def _build_quick_dock(self):
        dock = tk.Frame(self.quick_frame, bg=C_PANEL)
        dock.pack(fill="both", expand=True, padx=10, pady=10)
        actions = [
            ("SYSTEM SCAN", "/status"),
            ("CLIPBOARD AI", "/clipboard"),
            ("FOCUS MODE", "/focus"),
            ("SESSION BRIEF", "/brief"),
            ("MISSION LOG", "/notes"),
            ("CREATOR MODE", "/creator"),
        ]
        for label, command in actions:
            btn = tk.Button(
                dock,
                text=label,
                command=lambda c=command: self._trigger_quick_action(c),
                bg=C_BG2,
                fg=C_PRI,
                activebackground=C_DIM,
                activeforeground=C_TEXT,
                font=("Bahnschrift SemiBold", 9),
                borderwidth=0,
                padx=10,
                pady=7,
                cursor="hand2",
            )
            btn.pack(side="left", padx=4)

    def _build_bottom_bar(self):
        body = tk.Frame(self.bottom_frame, bg=C_PANEL)
        body.pack(fill="both", expand=True, padx=12, pady=10)

        btn_style = {
            "bg": C_BG2,
            "fg": C_PRI,
            "activebackground": C_DIM,
            "activeforeground": C_TEXT,
            "font": ("Bahnschrift SemiBold", 9),
            "borderwidth": 0,
            "padx": 12,
            "cursor": "hand2",
        }

        tk.Button(body, text="PDF", command=lambda: self._upload("pdf"), **btn_style).pack(side="left", padx=(0, 6), fill="y")
        tk.Button(body, text="IMAGE", command=lambda: self._upload("image"), **btn_style).pack(side="left", padx=(0, 12), fill="y")

        input_wrap = tk.Frame(body, bg=C_BG2, highlightbackground=C_LINE, highlightthickness=1)
        input_wrap.pack(side="left", fill="both", expand=True, padx=(0, 12))
        self.cmd_entry = tk.Entry(
            input_wrap,
            fg=C_TEXT,
            bg=C_BG2,
            insertbackground=C_PRI,
            borderwidth=0,
            relief="flat",
            font=("Consolas", 12),
        )
        self.cmd_entry.pack(fill="both", expand=True, padx=12, pady=10)
        self.cmd_entry.bind("<Return>", lambda e: self._on_send())

        self.mute_btn = tk.Button(body, text="MIC ACTIVE", command=self._on_mute_click, **btn_style)
        self.mute_btn.pack(side="right", padx=(6, 0), fill="y")
        self.send_btn = tk.Button(
            body,
            text="EXECUTE",
            command=self._on_send,
            bg=C_PRI,
            fg=C_BG,
            activebackground=C_PRI_SOFT,
            activeforeground=C_BG,
            font=("Bahnschrift SemiBold", 10),
            borderwidth=0,
            padx=18,
            cursor="hand2",
        )
        self.send_btn.pack(side="right", fill="y")

    def _setup_bindings(self):
        self.root.bind("<Control-l>", lambda e: self._clear_conversation())
        self.root.bind("<Escape>", lambda e: self._trigger_quick_action("/brief"))

    def _clear_conversation(self):
        self.ai_text.configure(state="normal")
        self.ai_text.delete("1.0", tk.END)
        self.ai_text.configure(state="disabled")
        self.write_log("Dialogue pane cleared.")

    def _on_close(self):
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass

    def set_sleep_mode(self, active: bool):
        self.is_sleeping = active
        if active:
            self.status_text = "SLEEP MODE ACTIVE"
            self.set_mode("Sleep Protocol", "Listening for wake directives only.")
            self.write_log("Sleep protocol engaged.")
        else:
            self.status_text = "COMMAND CENTER READY"
            self.set_mode("Adaptive Intelligence", "Systems active and standing by.")
            self.write_log("Systems restored from sleep mode.")
            if self.sfx:
                try:
                    self.sfx.play_boot()
                except Exception:
                    pass

    def set_mute_state(self, active: bool):
        self.is_muted = active

        def _task():
            self.mute_btn.configure(text="MIC MUTED" if active else "MIC ACTIVE", fg=C_RED if active else C_PRI)
        self.root.after(0, _task)
        self.write_log("Microphone muted." if active else "Microphone active.")

    def set_mode(self, title: str, detail: str = ""):
        self.mode_title = title
        self.mode_detail = detail or "Ready for the next directive."

        def _task():
            self.mode_title_var.set(self.mode_title)
            self.mode_detail_var.set(self.mode_detail)
        self.root.after(0, _task)

    def set_system_snapshot(self, snapshot: dict):
        self.snapshot = snapshot or {}

        def _task():
            host = snapshot.get("hostname", "Unknown")
            battery = snapshot.get("battery") or {}
            power = battery.get("state", "Unavailable")
            if battery.get("percent") is not None:
                power = f"{battery['percent']}% {power}"
            self.detail_vars["HOST"].set(host)
            self.detail_vars["POWER"].set(power)
            self.detail_vars["UPTIME"].set(snapshot.get("uptime", "Tracking"))
            free = snapshot.get("disk_free_gb")
            total = snapshot.get("disk_total_gb")
            if free is not None and total is not None:
                self.detail_vars["DISK"].set(f"{free} / {total} GB free")
            self.status_text = "SYSTEM SNAPSHOT REFRESHED"
        self.root.after(0, _task)

    def set_mission_items(self, items):
        self.mission_items = list(items or [])

        def _task():
            self.mission_list.delete(0, tk.END)
            if not self.mission_items:
                self.mission_list.insert(tk.END, "No open missions.")
                return
            for item in self.mission_items:
                text = item.get("text", "")
                kind = item.get("kind", "note").upper()
                label = f"[{kind}] {text}"
                self.mission_list.insert(tk.END, label[:80])
        self.root.after(0, _task)

    def set_recommendations(self, items):
        self.recommendations = list(items or [])[:5]
        self.root.after(0, self._render_recommendations)

    def _render_recommendations(self):
        self.reco_text.configure(state="normal")
        self.reco_text.delete("1.0", tk.END)
        for item in self.recommendations:
            self.reco_text.insert(tk.END, f"- {item}\n")
        self.reco_text.configure(state="disabled")

    def register_tool_result(self, name: str, result: str):
        pretty = name.replace("_", " ").title()
        self.write_log(f"{pretty}: complete.")
        if name == "system_dashboard":
            self.status_text = "COMMAND CENTER SYNCHRONIZED"
        elif name == "routine_manager":
            self.status_text = "ROUTINE ENGAGED"
        elif name == "mission_journal":
            self.status_text = "MISSION BOARD UPDATED"
        elif name == "clipboard_brain":
            self.status_text = "CLIPBOARD ANALYZED"

    def bind_quick_action(self, callback):
        self.quick_action_callback = callback

    def _trigger_quick_action(self, command: str):
        self.write_ai_response(command, sender="user")
        if self.quick_action_callback:
            self.quick_action_callback(command)
        elif self.on_text_submit:
            self.on_text_submit(command)

    def _on_mute_click(self):
        if self.on_mute_toggle:
            self.on_mute_toggle()

    def _upload(self, upload_type):
        if upload_type == "image":
            path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.png *.jpeg *.webp")])
        else:
            path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])

        if path and self.on_file_upload:
            self.write_log(f"Analyzing {upload_type.upper()} upload.")
            self.on_file_upload(upload_type, path)

    def _on_send(self):
        text = self.cmd_entry.get().strip()
        if not text:
            return
        self.cmd_entry.delete(0, tk.END)
        self.write_ai_response(text, sender="user")
        if self.sfx:
            try:
                self.sfx.play_ping()
            except Exception:
                pass
        if self.on_text_submit:
            self.on_text_submit(text)

    def _load_face(self, path):
        try:
            full_path = Path(BASE_DIR) / path
            if not full_path.exists():
                full_path = Path(path)
            image = Image.open(full_path).convert("RGBA").resize((self.FACE_SZ, self.FACE_SZ), Image.LANCZOS)
            mask = Image.new("L", (self.FACE_SZ, self.FACE_SZ), 0)
            ImageDraw.Draw(mask).ellipse((12, 12, self.FACE_SZ - 12, self.FACE_SZ - 12), fill=255)
            image.putalpha(mask)
            self._face_pil = image
            self._has_face = True
        except Exception:
            self._has_face = False

    def _update_live_metrics(self):
        try:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            net_now = psutil.net_io_counters()
            delta_mb = ((net_now.bytes_recv - self.last_traffic.bytes_recv) + (net_now.bytes_sent - self.last_traffic.bytes_sent)) / (1024 * 1024 * 2)
            self.last_traffic = net_now
            temp = 40 + int(cpu / 6)

            self.metric_vars["CPU"].set(f"{cpu:.0f}%")
            self.metric_vars["RAM"].set(f"{ram:.0f}%")
            self.metric_vars["NET"].set(f"{max(delta_mb, 0):.1f} MB/s")
            self.metric_vars["TEMP"].set(f"{temp} C")

            values = {"CPU": cpu, "RAM": ram, "NET": min(delta_mb * 12, 100), "TEMP": min(temp, 100)}
            for key, val in values.items():
                bar, max_width = self.metric_bars[key]
                bar.configure(width=int(max_width * (val / 100)), bg=C_RED if val > 80 else C_PRI)
        except Exception:
            pass
        self.root.after(1400, self._update_live_metrics)

    def _update_clock(self):
        self.clock_text = time.strftime("%H:%M:%S")
        self.date_text = time.strftime("%d %b %Y").upper()
        self.root.after(1000, self._update_clock)

    def _init_data_streams(self):
        """Initialize falling data column metadata."""
        for _ in range(25):
            x = random.randint(50, self.W - 50)
            y = random.randint(-self.H, 0)
            self.stream_pts.append({
                "x": x,
                "y": y,
                "speed": random.uniform(2.5, 6.0),
                "chars": [random.choice("01ABCDEF") for _ in range(8)]
            })

    def _animate(self):
        self.tick += 1
        if self.boot_tick > 0:
            self.boot_tick -= 1
        self.glitch_tick = max(0, self.glitch_tick - 1)
        if random.random() < 0.005:
            self.glitch_tick = random.randint(2, 5)

        if self.is_sleeping:
            self.target_scale = 0.97
        else:
            self.target_scale = 1.04 if self.speaking else 1.0 + math.sin(self.tick * 0.05) * 0.01
        self.scale += (self.target_scale - self.scale) * (0.25 if self.speaking else 0.07)
        speed = 0.35 if self.is_sleeping else (1.8 if self.speaking else 0.85)
        self.angle_1 = (self.angle_1 + speed) % 360
        self.angle_2 = (self.angle_2 - speed * 1.4) % 360
        self.angle_3 = (self.angle_3 + speed * 2.2) % 360
        self.angle_4 = (self.angle_4 + speed * 0.8) % 360
        self.angle_5 = (self.angle_5 - speed * 3.5) % 360
        self.globe_angle = (self.globe_angle + 0.02) % (2 * math.pi)

        # Grid and Stream motion
        self.grid_offset = (self.grid_offset + (speed * 0.5)) % 36
        self.scan_y = (self.scan_y + speed * 2) % (self.H + 200)
        for pt in self.stream_pts:
            pt["y"] += pt["speed"]
            if pt["y"] > self.H:
                pt["y"] = -100
                pt["x"] = random.randint(50, self.W - 50)

        baseline = self.H - 170
        amplitude = 22 if self.speaking else 7
        self.brainwave_pts.append(baseline + math.sin(self.tick * 0.22) * amplitude + random.uniform(-2.0, 2.0))
        self._draw_scene()
        self.root.after(25, self._animate)

    def _draw_scene(self):
        c = self.bg
        c.delete("render")

        # Glitch Offset
        gx, gy = 0, 0
        if self.glitch_tick > 0:
            gx, gy = random.randint(-3, 3), random.randint(-3, 3)

        # ── 1. BACKGROUND GRID & DATA ──
        # Infinite scrolling 3D perspective floor/grid
        horizon_y = self.H // 2 + 100
        for i in range(-25, 25):
            x_start = self.FCX + i * 180 + gx
            x_end = self.FCX + i * 900 + gx
            c.create_line(x_start, horizon_y + gy, x_end, self.H + 400 + gy, fill=C_GRID, width=1, tags="render")

        # Orbital data rings
        for i in range(2):
            r = 300 + i * 40
            c.create_arc(self.FCX - r, self.FCY - r, self.FCX + r, self.FCY + r, start=self.angle_1 * (1 + i), extent=60, outline=C_LINE, width=1, style="arc", tags="render")

        # Horizontal scrolling grid lines
        for i in range(15):
            y = horizon_y + (i * 45 + self.grid_offset) % (self.H - horizon_y + 200)
            alpha_ratio = (y - horizon_y) / (self.H - horizon_y + 200)
            color = f"#{int(8*alpha_ratio):01x}{int(24*alpha_ratio):02x}{int(34*alpha_ratio):02x}"
            c.create_line(0, y, self.W, y, fill=C_GRID, width=1, tags="render")

        # Hexagonal holographic overlay
        for x in range(0, self.W, 140):
            for y in range(0, self.H, 120):
                if (x+y) % 280 == 0:
                    c.create_text(x, y, text="⬡", fill=C_HEX, font=("Consolas", 28), tags="render")

        # ── 2. DATA STREAMS ( falling code ) ──
        for pt in self.stream_pts:
            char_str = "".join(pt["chars"])
            c.create_text(pt["x"], pt["y"], text=char_str, fill=C_STREAM, font=("Consolas", 9), anchor="n", tags="render")

        # ── 3. TOP COMMAND BAR ──
        c.create_rectangle(0, 0, self.W, 88, fill="#030a10", outline="", tags="render")
        c.create_line(0, 88, self.W, 88, fill=C_LINE, width=1, tags="render")
        c.create_text(self.W // 2, 30, text=SYSTEM_NAME, fill=C_PRI, font=("Bahnschrift SemiBold", 28), tags="render")
        c.create_text(self.W // 2, 58, text=MODEL_BADGE, fill=C_MUTED, font=("Consolas", 9, "bold"), tags="render")
        c.create_text(self.W - 40, 30, text=self.clock_text, fill=C_TEXT, font=("Consolas", 18, "bold"), anchor="e", tags="render")
        c.create_text(self.W - 40, 55, text=self.date_text, fill=C_MUTED, font=("Consolas", 9), anchor="e", tags="render")

        # Scanning Line
        sy = self.scan_y - 100
        if 0 < sy < self.H:
            c.create_line(0, sy, self.W, sy, fill=C_PRI_SOFT, width=1, dash=(4, 4), tags="render")
            c.create_rectangle(0, sy-2, self.W, sy+2, fill=C_GLOW, stipple="gray25", outline="", tags="render")

        # Status HUD
        c.create_text(34, 30, text="SYSTEM STATUS", fill=C_MUTED, font=("Consolas", 8, "bold"), anchor="w", tags="render")
        status_color = C_RED if self.is_sleeping else (C_ACC if self.speaking else C_GREEN)
        c.create_text(34, 52, text=self.status_text, fill=status_color, font=("Bahnschrift SemiBold", 12), anchor="w", tags="render")

        # Decorative Coordinates/Data
        if self.tick % 10 == 0:
            self.dec_data = [f"SEC_{i+1}: {random.randint(100, 999)}.{random.randint(0,99)}" for i in range(3)]

        if hasattr(self, 'dec_data'):
            for i, canvas_text in enumerate(self.dec_data):
                tx = 34 + i * 100
                c.create_text(tx, 75, text=canvas_text, fill=C_DIM, font=("Consolas", 7), anchor="w", tags="render")

        self._draw_globe(c)
        self._draw_reactor(c)
        self._draw_hud_badges(c)
        self._draw_brainwave(c)
        self._draw_side_telemetry(c)

        # ── 4. BOOT OVERLAY ──
        if self.boot_tick > 0:
            alpha = self.boot_tick / 100
            # Tkinter doesn't do alpha well on canvas without images, so we simulate with C_GRID/C_BG
            if self.boot_tick % 2 == 0:
                c.create_rectangle(0, 0, self.W, self.H, fill=C_BG, tags="render")
                c.create_text(self.FCX, self.FCY, text="INITIALIZING MARK XXX...", fill=C_PRI, font=("Bahnschrift SemiBold", 20), tags="render")

    def _draw_globe(self, canvas):
        R = 140 * self.scale
        dist = 500
        zoom = 500

        # Draw 3D Wireframe Globe
        points = []

        # Latitudes
        for lat in range(-90, 91, 15):
            phi = math.radians(lat)
            ring = []
            for lon in range(0, 361, 10):
                theta = math.radians(lon) + self.globe_angle

                x = R * math.cos(phi) * math.cos(theta)
                y = R * math.sin(phi)
                z = R * math.cos(phi) * math.sin(theta)

                # Projection
                z_eff = z + dist
                px = self.FCX + (x * zoom / z_eff)
                py = self.FCY + (y * zoom / z_eff)

                if z < 0: # Front side
                    ring.append((px, py))
                else:
                    if len(ring) > 1:
                        canvas.create_line(ring, fill=C_GRID, width=1, tags="render")
                    ring = []
            if len(ring) > 1:
                canvas.create_line(ring, fill=C_GRID, width=1, tags="render")

        # Longitudes
        for lon in range(0, 181, 20):
            theta_base = math.radians(lon) + self.globe_angle
            line = []
            for lat in range(-90, 91, 5):
                phi = math.radians(lat)
                theta = theta_base

                x = R * math.cos(phi) * math.cos(theta)
                y = R * math.sin(phi)
                z = R * math.cos(phi) * math.sin(theta)

                z_eff = z + dist
                px = self.FCX + (x * zoom / z_eff)
                py = self.FCY + (y * zoom / z_eff)

                if z < 0:
                    line.append((px, py))
                else:
                    if len(line) > 1:
                        canvas.create_line(line, fill=C_GRID, width=1, tags="render")
                    line = []
            if len(line) > 1:
                canvas.create_line(line, fill=C_GRID, width=1, tags="render")

        # Satellite Orbits
        orbit_colors = [C_PRI_SOFT, C_ACC, C_GREEN]

        # Threat Zones (Simulated)
        for i in range(2):
            t_lat = math.radians(30 + i*20)
            t_lon = math.radians(45 + i*60) + self.globe_angle
            tx = R * math.cos(t_lat) * math.cos(t_lon)
            ty = R * math.sin(t_lat)
            tz = R * math.cos(t_lat) * math.sin(t_lon)

            z_eff = tz + dist
            if tz < 0:
                px = self.FCX + (tx * zoom / z_eff)
                py = self.FCY + (ty * zoom / z_eff)
                canvas.create_oval(px-10, py-10, px+10, py+10, outline=C_RED, width=1, tags="render")
                if self.tick % 20 < 10:
                    canvas.create_text(px, py-15, text="THREAT DETECTED", fill=C_RED, font=("Consolas", 6, "bold"), tags="render")
        for i in range(3):
            orbit_angle = self.globe_angle * (1.2 + i * 0.3)
            tilt = math.radians(45 + i * 30)

            orbit_pts = []
            for a in range(0, 361, 5):
                rad = math.radians(a)
                # Planar orbit
                ox = (R + 40 + i*20) * math.cos(rad)
                oy = (R + 40 + i*20) * math.sin(rad)
                oz = 0

                # Rotate orbit (tilt)
                ry = oy * math.cos(tilt) - oz * math.sin(tilt)
                rz = oy * math.sin(tilt) + oz * math.cos(tilt)

                # Rotate orbit (time)
                rx = ox * math.cos(self.globe_angle * 0.5) - rz * math.sin(self.globe_angle * 0.5)
                rz2 = ox * math.sin(self.globe_angle * 0.5) + rz * math.cos(self.globe_angle * 0.5)

                z_eff = rz2 + dist
                px = self.FCX + (rx * zoom / z_eff)
                py = self.FCY + (ry * zoom / z_eff)

                if rz2 < 0:
                    orbit_pts.append((px, py))
                    # Draw satellite ping
                    if abs(a - (self.tick * 2 + i * 120) % 360) < 5:
                        canvas.create_oval(px-4, py-4, px+4, py+4, fill=orbit_colors[i], outline=C_TEXT, width=1, tags="render")
                        canvas.create_text(px+10, py-10, text=f"SAT-{i+1}", fill=orbit_colors[i], font=("Consolas", 7, "bold"), tags="render")
                        if i == 0:
                            # Targeting Reticle
                            canvas.create_line(px-15, py, px-8, py, fill=C_PRI, width=1, tags="render")
                            canvas.create_line(px+8, py, px+15, py, fill=C_PRI, width=1, tags="render")
                            canvas.create_line(px, py-15, px, py-8, fill=C_PRI, width=1, tags="render")
                            canvas.create_line(px, py+8, px, py+15, fill=C_PRI, width=1, tags="render")

                            # Use satellite specific coordinates 'rad' and 'tilt'
                            # This is a simplification for visual effect
                            sat_lat = math.degrees(rad) % 180 - 90
                            sat_lon = math.degrees(rad + tilt) % 360 - 180
                            self.sat_vars["LAT"].set(f"{sat_lat:.2f}°")
                            self.sat_vars["LON"].set(f"{sat_lon:.2f}°")

                            # Satellite Link Flicker
                            link_status = "STABLE" if self.tick % 50 > 5 else "RESYNC..."
                            link_color = C_ACC if link_status == "STABLE" else C_RED
                            self.sat_vars["STATUS"].set(link_status)
                else:
                    if len(orbit_pts) > 1:
                        canvas.create_line(orbit_pts, fill=C_DIM, width=1, dash=(2, 4), tags="render")
                    orbit_pts = []
            if len(orbit_pts) > 1:
                canvas.create_line(orbit_pts, fill=C_DIM, width=1, dash=(2, 4), tags="render")

    def _draw_reactor(self, canvas):
        color = "#3f4b52" if self.is_muted else (C_RED if self.is_sleeping else C_PRI)
        radius = int(150 * self.scale)

        # ── v6 Engine: Ultra-HD Arc Reactor ──
        # Outer decorative hexagonal orbit
        for i in range(6):
            angle = math.radians(self.angle_3 + i * 60)
            hx = self.FCX + math.cos(angle) * (radius + 120)
            hy = self.FCY + math.sin(angle) * (radius + 120)
            canvas.create_text(hx, hy, text="⬡", fill=C_DIM, font=("Consolas", 14), tags="render")

        # Layer 1: Outermost static shroud
        canvas.create_oval(self.FCX - radius - 85, self.FCY - radius - 85, self.FCX + radius + 85, self.FCY + radius + 85, outline=C_DIM, width=1, tags="render")

        # Technical Labels around reactor
        labels = ["THRM", "CORE", "SYNC", "FLUX", "ORBT", "SENS"]
        for i, label in enumerate(labels):
            angle = math.radians(self.angle_4 * 0.5 + i * 90)
            dist = radius + 95
            lx = self.FCX + math.cos(angle) * dist
            ly = self.FCY + math.sin(angle) * dist
            canvas.create_text(lx, ly, text=label, fill=C_DIM, font=("Consolas", 6, "bold"), tags="render")

        # Layer 2: Primary Arc segments (Angle 1)
        for i in range(12):
            start = self.angle_1 + i * 30
            canvas.create_arc(self.FCX - radius - 60, self.FCY - radius - 60, self.FCX + radius + 60, self.FCY + radius + 60, start=start, extent=18, outline=color, width=3, style="arc", tags="render")

        # Layer 3: Technical ring with notches (Angle 2)
        for i in range(60):
            if i % 5 == 0:
                start = self.angle_2 + i * 6
                canvas.create_arc(self.FCX - radius - 40, self.FCY - radius - 40, self.FCX + radius + 40, self.FCY + radius + 40, start=start, extent=2, outline=C_PRI_SOFT, width=5, style="arc", tags="render")

        # Layer 4: Pulse ring (Angle 4)
        for i in range(8):
            start = self.angle_4 + i * 45
            canvas.create_arc(self.FCX - radius - 10, self.FCY - radius - 10, self.FCX + radius + 10, self.FCY + radius + 10, start=start, extent=20, outline=C_ACC if self.speaking else color, width=2, style="arc", tags="render")

        # Layer 5: Inner High-Speed Ring (Angle 5)
        canvas.create_oval(self.FCX - 60, self.FCY - 60, self.FCX + 60, self.FCY + 60, outline=C_DIM, width=1, tags="render")
        for i in range(3):
            start = self.angle_5 + i * 120
            canvas.create_arc(self.FCX - 58, self.FCY - 58, self.FCX + 58, self.FCY + 58, start=start, extent=40, outline=C_ACC if self.speaking else C_PRI, width=1, style="arc", tags="render")

        # ── CORE RADIANCE (Faded for Globe focus) ──
        color = C_DIM if not self.speaking else color
        pulse = 42 + (6 if self.speaking else 0)
        glow_color = C_ACC if (self.speaking and self.tick % 2 == 0) else C_GLOW
        for glow, outline, w in ((pulse + 32, C_DIM, 1), (pulse + 20, glow_color, 2), (pulse + 8, color, 3), (pulse, C_TEXT, 4)):
            canvas.create_oval(self.FCX - glow, self.FCY - glow, self.FCX + glow, self.FCY + glow, outline=outline, width=w, tags="render")

        # HUD Brackets (Corner focus)
        for sx, sy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
            cx, cy = self.FCX + sx * (radius + 110), self.FCY + sy * (radius + 110)
            canvas.create_line(cx, cy, cx - sx * 30, cy, fill=C_LINE, width=2, tags="render")
            canvas.create_line(cx, cy, cx, cy - sy * 30, fill=C_LINE, width=2, tags="render")

        if self.speaking:
            ripple = radius + 100 + int((self.tick % 18) * 4)
            canvas.create_oval(self.FCX - ripple, self.FCY - ripple, self.FCX + ripple, self.FCY + ripple, outline=C_ACC, width=1, tags="render")

        if self._has_face and self._face_pil and self.speaking:
            scaled_size = int(self.FACE_SZ * self.scale * 0.45) # Smaller face to fit in globe
            if self._face_scale_cache is None or abs(self._face_scale_cache[0] - scaled_size) > 2:
                # Use NEAREST for faster scaling during animation, or only resize when delta > 2
                scaled = self._face_pil.resize((scaled_size, scaled_size), Image.BILINEAR)
                self._face_scale_cache = (scaled_size, ImageTk.PhotoImage(scaled))
            # Subtle blend
            canvas.create_image(self.FCX, self.FCY, image=self._face_scale_cache[1], tags="render")

    def _draw_hud_badges(self, canvas):
        badges = [
            ("VOICE", "LIVE" if self.speaking else "READY", C_ACC if self.speaking else C_GREEN),
            ("MIC", "MUTED" if self.is_muted else "OPEN", C_RED if self.is_muted else C_PRI),
            ("MODE", self.mode_title[:18].upper(), C_ACC),
        ]
        x = self.W // 2 - 210
        for label, value, color in badges:
            canvas.create_rectangle(x, 102, x + 132, 142, outline=C_LINE, fill=C_PANEL, width=1, tags="render")
            canvas.create_text(x + 10, 115, text=label, fill=C_MUTED, font=("Consolas", 8), anchor="w", tags="render")
            canvas.create_text(x + 10, 132, text=value, fill=color, font=("Bahnschrift SemiBold", 10), anchor="w", tags="render")
            x += 145

    def _draw_brainwave(self, canvas):
        points = []
        for i, y in enumerate(self.brainwave_pts):
            points.extend([360 + i * 8, y])
        if len(points) > 4:
            canvas.create_line(*points, fill=C_ACC if self.speaking else C_PRI, width=2, smooth=True, tags="render")
        canvas.create_text(360, self.H - 202, text="NEURAL ACTIVITY", fill=C_MUTED, font=("Consolas", 8, "bold"), anchor="w", tags="render")

    def _draw_side_telemetry(self, canvas):
        # Background "Code Stream" labels
        for i in range(5):
            y = 150 + i*150
            canvas.create_text(50, y, text="0x"+hex(random.randint(0x1000, 0xFFFF))[2:].upper(), fill=C_STREAM, font=("Consolas", 7), anchor="w", tags="render")
            canvas.create_text(self.W-50, y, text="LINK_ID:"+str(random.randint(1000, 9999)), fill=C_STREAM, font=("Consolas", 7), anchor="e", tags="render")

        # Left side circular stats
        lx, ly = 180, self.H - 450
        canvas.create_arc(lx-50, ly-50, lx+50, ly+50, start=self.angle_1, extent=270, outline=C_LINE, width=2, style="arc", tags="render")
        canvas.create_text(lx, ly, text=f"{int(self.angle_1)}°", fill=C_PRI, font=("Consolas", 10, "bold"), tags="render")
        canvas.create_text(lx, ly+65, text="GLOBAL ORIENTATION", fill=C_MUTED, font=("Consolas", 7), tags="render")

        # Scanning Radar
        rx_c, ry_c = 180, 250
        canvas.create_oval(rx_c-60, ry_c-60, rx_c+60, ry_c+60, outline=C_GRID, width=1, tags="render")
        canvas.create_line(rx_c, ry_c, rx_c + 60*math.cos(self.globe_angle*5), ry_c + 60*math.sin(self.globe_angle*5), fill=C_PRI_SOFT, tags="render")
        canvas.create_text(rx_c, ry_c+75, text="SURVEILLANCE RADAR", fill=C_MUTED, font=("Consolas", 7), tags="render")

        # Right side vertical bars
        rx, ry = self.W - 150, self.H - 450
        for i in range(5):
            h = 40 + math.sin(self.tick * 0.1 + i) * 20
            canvas.create_rectangle(rx + i*15, ry + 50, rx + i*15 + 8, ry + 50 - h, fill=C_PRI_SOFT, outline="", tags="render")
        canvas.create_text(rx + 35, ry + 65, text="SIGNAL FLUX", fill=C_MUTED, font=("Consolas", 7), tags="render")

    def write_log(self, text: str):
        def _task():
            self.log_text.configure(state="normal")
            self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {text}\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state="disabled")
        self.root.after(0, _task)

    def write_ai_response(self, text: str, sender="ai"):
        def _task():
            self.ai_text.configure(state="normal")
            if sender == "user":
                self.ai_text.insert(tk.END, "YOU\n", "user")
                self.ai_text.insert(tk.END, f"{text}\n\n")
            elif sender == "sys":
                self.ai_text.insert(tk.END, "SYSTEM\n", "sys")
                self.ai_text.insert(tk.END, f"{text}\n\n")
            else:
                self.ai_text.insert(tk.END, "JARVIS\n", "ai")
                self.ai_text.insert(tk.END, f"{text}\n\n")
            self.ai_text.see(tk.END)
            self.ai_text.configure(state="disabled")
        self.root.after(0, _task)

    def start_speaking(self):
        self.speaking = True
        self.status_text = "UPLINK ACTIVE"

    def stop_speaking(self):
        self.speaking = False
        self.status_text = "COMMAND CENTER READY" if not self.is_sleeping else "SLEEP MODE ACTIVE"

    def _api_keys_exist(self):
        return API_FILE.exists()

    def _show_setup_ui(self):
        self.setup_frame = tk.Frame(self.root, bg=C_PANEL, highlightbackground=C_PRI, highlightthickness=2)
        self.setup_frame.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(self.setup_frame, text="VANGUARD INITIALIZATION", fg=C_PRI, bg=C_PANEL, font=("Bahnschrift SemiBold", 16)).pack(pady=24, padx=40)
        tk.Label(self.setup_frame, text="Enter Gemini API key", fg=C_MUTED, bg=C_PANEL, font=("Consolas", 10)).pack()
        self.gemini_entry = tk.Entry(
            self.setup_frame,
            width=50,
            fg=C_TEXT,
            bg=C_BG2,
            borderwidth=0,
            show="*",
            insertbackground=C_PRI,
            font=("Consolas", 11),
        )
        self.gemini_entry.pack(pady=12, padx=40)
        tk.Button(
            self.setup_frame,
            text="AUTHENTICATE AND BOOT",
            command=self._save_api_keys,
            bg=C_PRI,
            fg=C_BG,
            activebackground=C_PRI_SOFT,
            activeforeground=C_BG,
            font=("Bahnschrift SemiBold", 10),
            pady=10,
            padx=18,
            borderwidth=0,
            cursor="hand2",
        ).pack(pady=22)

    def _save_api_keys(self):
        gemini = self.gemini_entry.get().strip()
        if gemini:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(API_FILE, "w", encoding="utf-8") as file:
                json.dump({"gemini_api_key": gemini}, file)
            self.setup_frame.destroy()
            self._api_key_ready = True
            self.write_log("Encryption key accepted. Command Center online.")

    def wait_for_api_key(self):
        while not self._api_key_ready:
            time.sleep(0.1)


if __name__ == "__main__":
    ui = JarvisUI("face_v2.png")
    ui.root.mainloop()
