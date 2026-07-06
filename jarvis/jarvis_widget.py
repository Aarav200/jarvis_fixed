"""
jarvis_widget.py — Siri-quality floating orb UI for Jarvis.
"""

import threading
import time
import tkinter as tk
import math
import queue
import random

_widget_queue = queue.Queue()
_widget_instance = None


def notify(event, data=None):
    _widget_queue.put({"event": event, "data": data or {}})


def start_widget():
    t = threading.Thread(target=_run_widget, daemon=True, name="jarvis-widget")
    t.start()


def _run_widget():
    global _widget_instance
    try:
        root = tk.Tk()
        _widget_instance = JarvisWidget(root)
        root.mainloop()
    except Exception as e:
        print(f"[Jarvis Widget] Error: {e}")


C = {
    "bg":          "#06090f",
    "orb_dark":    "#0b1628",
    "orb_mid":     "#0d2040",
    "orb_light":   "#1a3a6e",
    "rim_idle":    "#1565a0",
    "rim_listen":  "#00b4d8",
    "rim_speak":   "#90e0ef",
    "rim_think":   "#7c6fcd",
    "dot":         "#90e0ef",
    "dot_bright":  "#caf0f8",
    "bar_lo":      "#00b4d8",
    "bar_hi":      "#caf0f8",
    "arc":         "#caf0f8",
    "orbit":       "#a48fff",
    "card_bg":     "#080e1c",
    "card_border": "#1a3a6e",
    "card_hdr":    "#0a1220",
    "cyan":        "#00d4ff",
    "text":        "#c8e6f5",
    "muted":       "#3a5570",
    "transparent": "#000001",
}

TAU = math.pi * 2


def _lerp(a, b, t):
    return a + (b - a) * t


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _hex_lerp(c1, c2, t):
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    return f"#{int(_lerp(r1,r2,t)):02x}{int(_lerp(g1,g2,t)):02x}{int(_lerp(b1,b2,t)):02x}"


class Particle:
    def __init__(self, cx, cy):
        angle = random.uniform(0, TAU)
        speed = random.uniform(1.5, 4.5)
        self.x, self.y = cx, cy
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.life = 1.0
        self.decay = random.uniform(0.025, 0.06)
        self.r = random.uniform(1.5, 3.5)

    def update(self):
        self.x += self.vx; self.y += self.vy
        self.vx *= 0.93;   self.vy *= 0.93
        self.life -= self.decay

    @property
    def alive(self):
        return self.life > 0


class JarvisWidget:
    ORB_SIZE = 120
    CARD_W   = 360
    CARD_H   = 300

    def __init__(self, root):
        self.root = root
        self.state = "idle"
        self._t = 0.0
        self._particles = []
        self._prev_state = "idle"
        self._pulse_rings = []
        self._card_visible = False
        self._drag_x = self._drag_y = 0
        self._fade_alpha = 0.0
        self._card_alpha = 0.0

        self._setup_orb_window()
        self._build_orb_canvas()
        self._setup_card_window()
        self._build_card()
        self._schedule_frame()
        self._poll_queue()

    def _setup_orb_window(self):
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.title("Jarvis")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.0)
        self.root.configure(bg=C["transparent"])
        self.root.attributes("-transparentcolor", C["transparent"])
        x = sw - self.ORB_SIZE - 20
        y = sh - self.ORB_SIZE - 50
        self.root.geometry(f"{self.ORB_SIZE}x{self.ORB_SIZE}+{x}+{y}")
        self.root.bind("<ButtonPress-1>", self._drag_start)
        self.root.bind("<B1-Motion>",     self._drag_move)
        self._fade_in()

    def _fade_in(self):
        self._fade_alpha = min(1.0, self._fade_alpha + 0.05)
        self.root.attributes("-alpha", self._fade_alpha)
        if self._fade_alpha < 1.0:
            self.root.after(20, self._fade_in)

    def _setup_card_window(self):
        self.card_win = tk.Toplevel(self.root)
        self.card_win.title("")
        self.card_win.overrideredirect(True)
        self.card_win.attributes("-topmost", True)
        self.card_win.attributes("-alpha", 0.0)
        self.card_win.configure(bg=C["card_bg"])
        orb_x = self.root.winfo_x()
        orb_y = self.root.winfo_y()
        cx = orb_x - self.CARD_W + self.ORB_SIZE
        cy = orb_y - self.CARD_H - 12
        self.card_win.geometry(f"{self.CARD_W}x{self.CARD_H}+{cx}+{cy}")
        self.card_win.withdraw()
        self.card_win.bind("<ButtonPress-1>", self._card_drag_start)
        self.card_win.bind("<B1-Motion>",     self._card_drag_move)
        self._cdrag_x = self._cdrag_y = 0

    def _build_orb_canvas(self):
        self.canvas = tk.Canvas(
            self.root, width=self.ORB_SIZE, height=self.ORB_SIZE,
            bg=C["transparent"], highlightthickness=0
        )
        self.canvas.pack()

    def _build_card(self):
        border = tk.Frame(self.card_win, bg=C["card_border"], padx=1, pady=1)
        border.pack(fill="both", expand=True)
        inner = tk.Frame(border, bg=C["card_bg"])
        inner.pack(fill="both", expand=True)

        hdr = tk.Frame(inner, bg=C["card_hdr"], height=38)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        dot_c = tk.Canvas(hdr, width=10, height=10, bg=C["card_hdr"], highlightthickness=0)
        dot_c.pack(side="left", padx=(14, 6), pady=14)
        dot_c.create_oval(1, 1, 9, 9, fill=C["cyan"], outline="")

        self.card_title_lbl = tk.Label(hdr, text="JARVIS", bg=C["card_hdr"],
                                        fg=C["cyan"], font=("Segoe UI", 9, "bold"))
        self.card_title_lbl.pack(side="left")

        close = tk.Label(hdr, text="  \u2715  ", bg=C["card_hdr"],
                         fg=C["muted"], font=("Segoe UI", 10), cursor="hand2")
        close.pack(side="right")
        close.bind("<Button-1>", lambda e: self._hide_card())
        close.bind("<Enter>",    lambda e: close.config(fg="#ffffff"))
        close.bind("<Leave>",    lambda e: close.config(fg=C["muted"]))

        div = tk.Canvas(inner, height=1, bg=C["card_bg"], highlightthickness=0)
        div.pack(fill="x")
        div.bind("<Configure>", lambda e: self._draw_gradient_div(div))

        content = tk.Frame(inner, bg=C["card_bg"], padx=16, pady=12)
        content.pack(fill="both", expand=True)

        self.card_text = tk.Text(content, bg=C["card_bg"], fg=C["text"],
                                  font=("Segoe UI", 9), wrap="word",
                                  relief="flat", borderwidth=0,
                                  state="disabled", cursor="arrow", height=10)
        self.card_text.pack(fill="both", expand=True)
        self.card_text.tag_configure("num",  foreground=C["cyan"],  font=("Segoe UI", 9, "bold"))
        self.card_text.tag_configure("head", foreground=C["cyan"],  font=("Segoe UI", 9, "bold"))
        self.card_text.tag_configure("body", foreground=C["text"],  font=("Segoe UI", 9))
        self.card_text.tag_configure("up",   foreground="#00e676",  font=("Segoe UI", 9, "bold"))
        self.card_text.tag_configure("down", foreground="#ff5252",  font=("Segoe UI", 9, "bold"))
        self.card_text.tag_configure("dim",  foreground=C["muted"], font=("Segoe UI", 8))

        ftr = tk.Frame(inner, bg=C["card_hdr"], height=26)
        ftr.pack(fill="x", side="bottom")
        ftr.pack_propagate(False)
        self.card_src_lbl = tk.Label(ftr, text="", bg=C["card_hdr"], fg=C["muted"],
                                      font=("Segoe UI", 7), padx=14)
        self.card_src_lbl.pack(side="left", pady=5)
        self.card_time_lbl = tk.Label(ftr, text="", bg=C["card_hdr"], fg=C["muted"],
                                       font=("Segoe UI", 7), padx=14)
        self.card_time_lbl.pack(side="right", pady=5)

    def _draw_gradient_div(self, canvas):
        w = canvas.winfo_width()
        canvas.delete("all")
        steps = max(w // 4, 1)
        for i in range(steps):
            frac = i / steps
            alpha = math.sin(frac * math.pi)
            g = int(0xb4 * alpha)
            b = int(0xd8 * alpha)
            canvas.create_rectangle(int(i*w/steps), 0, int((i+1)*w/steps)+1, 1,
                                     fill=f"#00{g:02x}{b:02x}", outline="")

    # ── Animation ─────────────────────────────────────────────────────────────

    def _schedule_frame(self):
        self.root.after(16, self._frame)

    def _frame(self):
        self._t += 0.016
        if self.state != self._prev_state:
            self._on_state_change()
        self._prev_state = self.state

        for p in self._particles:
            p.update()
        self._particles = [p for p in self._particles if p.alive]

        new_rings = []
        for ring in self._pulse_rings:
            ring["r"] += 1.4
            ring["alpha"] -= 0.022
            if ring["alpha"] > 0:
                new_rings.append(ring)
        self._pulse_rings = new_rings

        if self.state in ("listening", "thinking"):
            if random.random() < 0.08:
                self._pulse_rings.append({"r": 46.0, "alpha": 0.6})

        self._draw_orb()
        self._schedule_frame()

    def _on_state_change(self):
        cx, cy = self.ORB_SIZE / 2, self.ORB_SIZE / 2
        for _ in range(18):
            self._particles.append(Particle(cx, cy))

    def _draw_orb(self):
        c = self.canvas
        c.delete("all")
        cx, cy = self.ORB_SIZE / 2, self.ORB_SIZE / 2
        t = self._t
        state = self.state

        rim_col = {"idle": C["rim_idle"], "listening": C["rim_listen"],
                   "speaking": C["rim_speak"], "thinking": C["rim_think"]}.get(state, C["rim_idle"])

        # Pulse rings
        for ring in self._pulse_rings:
            alpha = int(_clamp(ring["alpha"] * 160, 0, 160))
            r = ring["r"]
            c.create_oval(cx-r, cy-r, cx+r, cy+r,
                          outline=self._alpha_hex(rim_col, alpha), width=1)

        # Ambient glow
        for dr, a in [(18, 25), (12, 40), (6, 55)]:
            pulse = 0.5 + 0.5 * math.sin(t * 1.2)
            alpha = int(a + pulse * 20)
            r = 46 + dr
            c.create_oval(cx-r, cy-r, cx+r, cy+r,
                          outline=self._alpha_hex(rim_col, alpha), width=1)

        # Glass orb layers
        base_r = self._orb_radius(t, state)
        self._oval(c, cx, cy, base_r, C["orb_dark"])
        self._oval(c, cx-4, cy-4, base_r*0.80, C["orb_mid"])
        self._oval(c, cx-10, cy-12, base_r*0.45, C["orb_light"])
        c.create_oval(cx-base_r, cy-base_r, cx+base_r, cy+base_r,
                      outline=rim_col, width=1)

        # State FX
        if state == "idle":
            self._draw_idle_dot(c, cx, cy, t)
        elif state == "listening":
            self._draw_eq_bars(c, cx, cy, t)
        elif state == "speaking":
            self._draw_wave_arcs(c, cx, cy, t)
        elif state == "thinking":
            self._draw_orbit(c, cx, cy, t)

        # Particles
        for p in self._particles:
            alpha = int(p.life * 200)
            col = self._alpha_hex(rim_col, alpha)
            r = p.r * p.life
            c.create_oval(p.x-r, p.y-r, p.x+r, p.y+r, fill=col, outline="")

        # Status label
        label = {"listening": "listening...", "speaking": "speaking...",
                 "thinking": "thinking..."}.get(state, "")
        if label:
            c.create_text(cx, cy + base_r + 10, text=label,
                          fill=rim_col, font=("Segoe UI", 7))

    def _orb_radius(self, t, state):
        base = 36.0
        if state == "idle":
            return base + 2.5 * math.sin(t * 0.9)
        elif state == "listening":
            return base + 5.5 * abs(math.sin(t * 3.8))
        elif state == "speaking":
            return base + 4.5 * abs(math.sin(t * 5.2))
        elif state == "thinking":
            return base + 2.0 * math.sin(t * 1.5)
        return base

    def _draw_idle_dot(self, c, cx, cy, t):
        pulse = 0.5 + 0.5 * math.sin(t * 1.8)
        r = 4.5 + pulse * 2.5
        for dr, a in [(r+8, 30), (r+4, 60)]:
            c.create_oval(cx-dr, cy-dr, cx+dr, cy+dr,
                          fill=self._alpha_hex(C["dot"], a), outline="")
        c.create_oval(cx-r, cy-r, cx+r, cy+r, fill=C["dot_bright"], outline="")

    def _draw_eq_bars(self, c, cx, cy, t):
        num_bars = 5
        bar_w = 3
        gap = 4
        total_w = num_bars * bar_w + (num_bars - 1) * gap
        bx = cx - total_w / 2
        for i in range(num_bars):
            phase = t * 4.5 + i * 0.85
            bh = 7 + 16 * abs(math.sin(phase))
            by = cy - bh / 2
            steps = max(int(bh), 1)
            for j in range(steps):
                col = _hex_lerp(C["bar_lo"], C["bar_hi"], j / steps)
                c.create_rectangle(bx, by+j, bx+bar_w, by+j+1, fill=col, outline="")
            c.create_oval(bx, by-1, bx+bar_w, by+bar_w-1, fill=C["bar_hi"], outline="")
            bx += bar_w + gap

    def _draw_wave_arcs(self, c, cx, cy, t):
        for i in range(5):
            phase = abs(math.sin(t * 4.0 + i * 0.9))
            r = 10 + i * 7
            alpha = int(_clamp((1 - i/5) * phase * 180, 0, 180))
            col = self._alpha_hex(C["arc"], alpha)
            for start in [-70, 110]:
                c.create_arc(cx-r, cy-r, cx+r, cy+r,
                             start=start, extent=140,
                             outline=col, width=1, style=tk.ARC)

    def _draw_orbit(self, c, cx, cy, t):
        num_dots = 7
        orbit_r = 19
        trail_len = 12
        for i in range(num_dots):
            base_angle = (i / num_dots) * TAU + t * 2.2
            brightness = (i / num_dots + t * 0.25) % 1.0
            dot_r = 1.5 + brightness * 2.0
            for j in range(trail_len):
                frac = j / trail_len
                angle = base_angle - frac * 0.6
                tx = cx + math.cos(angle) * orbit_r
                ty = cy + math.sin(angle) * orbit_r
                alpha = int((1 - frac) * brightness * 80)
                tr = max(dot_r * (1 - frac) * 0.5, 0.5)
                c.create_oval(tx-tr, ty-tr, tx+tr, ty+tr,
                              fill=self._alpha_hex(C["orbit"], alpha), outline="")
            dx = cx + math.cos(base_angle) * orbit_r
            dy = cy + math.sin(base_angle) * orbit_r
            alpha = int(brightness * 220)
            glow = self._alpha_hex(C["orbit"], int(alpha * 0.35))
            col  = self._alpha_hex(C["orbit"], alpha)
            c.create_oval(dx-dot_r*2, dy-dot_r*2, dx+dot_r*2, dy+dot_r*2,
                          fill=glow, outline="")
            c.create_oval(dx-dot_r, dy-dot_r, dx+dot_r, dy+dot_r,
                          fill=col, outline="")

    def _oval(self, c, cx, cy, r, fill):
        c.create_oval(cx-r, cy-r, cx+r, cy+r, fill=fill, outline="")

    @staticmethod
    def _alpha_hex(hex_col, alpha):
        r = int(hex_col[1:3], 16)
        g = int(hex_col[3:5], 16)
        b = int(hex_col[5:7], 16)
        a = alpha / 255
        return f"#{int(r*a):02x}{int(g*a):02x}{int(b*a):02x}"

    # ── Queue ─────────────────────────────────────────────────────────────────

    def _poll_queue(self):
        try:
            while not _widget_queue.empty():
                msg = _widget_queue.get_nowait()
                self._handle_event(msg["event"], msg["data"])
        except Exception:
            pass
        self.root.after(80, self._poll_queue)

    def _handle_event(self, event, data):
        if event == "listening":
            self.state = "listening"
        elif event == "speaking":
            self.state = "speaking"
            text = data.get("text", "")
            if text and len(text) >= 30:
                self._show_card("JARVIS", [("body", text)], "JARVIS")
        elif event == "thinking":
            self.state = "thinking"
        elif event == "idle":
            self.state = "idle"
        elif event == "news":
            headlines = data.get("headlines", [])
            items = []
            for i, h in enumerate(headlines, 1):
                items += [("num", f"{i:02d}  "), ("body", h + "\n\n")]
            self._show_card("TOP HEADLINES", items, "BBC News")
        elif event == "stocks":
            results = data.get("results", [])
            items = []
            for r in results:
                tag = "up" if "up" in r.lower() else "down"
                items += [(tag, "\u25b2  " if tag=="up" else "\u25bc  "), ("body", r + "\n\n")]
            self._show_card("MARKET UPDATE", items, "Yahoo Finance")
        elif event == "hide_card":
            self._hide_card()

    # ── Card ──────────────────────────────────────────────────────────────────

    def _show_card(self, title, items, source):
        self.card_title_lbl.config(text=title)
        self.card_text.config(state="normal")
        self.card_text.delete("1.0", "end")
        for tag, text in items:
            self.card_text.insert("end", text, tag)
        self.card_text.config(state="disabled")
        self.card_src_lbl.config(text=source)
        self.card_time_lbl.config(text=time.strftime("%H:%M"))
        orb_x = self.root.winfo_x()
        orb_y = self.root.winfo_y()
        cx = orb_x - self.CARD_W + self.ORB_SIZE
        cy = orb_y - self.CARD_H - 12
        self.card_win.geometry(f"{self.CARD_W}x{self.CARD_H}+{cx}+{cy}")
        self.card_win.deiconify()
        self.card_win.lift()
        self._card_visible = True
        self._card_alpha = 0.0
        self._fade_card_in()
        self.root.after(14000, self._hide_card)

    def _fade_card_in(self):
        self._card_alpha = min(0.96, self._card_alpha + 0.07)
        self.card_win.attributes("-alpha", self._card_alpha)
        if self._card_alpha < 0.96:
            self.root.after(16, self._fade_card_in)

    def _hide_card(self):
        if not self._card_visible:
            return
        self._card_visible = False
        self._fade_card_out()

    def _fade_card_out(self):
        alpha = self.card_win.attributes("-alpha")
        alpha -= 0.08
        if alpha <= 0:
            self.card_win.withdraw()
            return
        self.card_win.attributes("-alpha", alpha)
        self.root.after(16, self._fade_card_out)

    # ── Drag ──────────────────────────────────────────────────────────────────

    def _drag_start(self, event):
        self._drag_x = event.x; self._drag_y = event.y

    def _drag_move(self, event):
        x = self.root.winfo_x() + (event.x - self._drag_x)
        y = self.root.winfo_y() + (event.y - self._drag_y)
        self.root.geometry(f"+{x}+{y}")

    def _card_drag_start(self, event):
        self._cdrag_x = event.x; self._cdrag_y = event.y

    def _card_drag_move(self, event):
        x = self.card_win.winfo_x() + (event.x - self._cdrag_x)
        y = self.card_win.winfo_y() + (event.y - self._cdrag_y)
        self.card_win.geometry(f"+{x}+{y}")
