#!/usr/bin/env python3
"""
usage-gauge  —  a Claude Code statusLine that shows how well you're pacing your
subscription usage.

It reads the `rate_limits` block Claude Code pipes in on stdin (the same data the
/usage command shows) and renders a white/green/yellow/red pace gauge for the
5-hour session window and the 7-day (all-models) weekly window, sharing one bar.

The bar's axis is PROJECTED utilization at reset time:
    projected% = used% / (elapsed_fraction_of_window)
i.e. "if I keep this pace, where will I land when the window resets?"

    white  (<green_lo)          under-using   — wasting budget
    green  (green_lo..green_hi)  on pace       — land ~exactly at reset  ✅
    yellow (green_hi..yellow_hi) too hot        — ok IF you slow down
    red    (>yellow_hi)          over           — will run out before reset

Layout: one shared bar; the 5h pointer rides above (▼), the weekly below (▲).

            5h▼112%
    ████████████████████
        wk▲41%

Paths (works both as a loose script and as an installed plugin):
  - config : $USAGE_GAUGE_CONFIG  ->  ~/.claude/usage-gauge/config.json  ->  bundled config.json
  - state  : $CLAUDE_PLUGIN_DATA  ->  ~/.claude/usage-gauge/   (writable, survives updates)
"""

import json
import os
import sys
import time

# Windows consoles default to cp1252, which can't encode the gauge glyphs
# (▼ ▲ █). Force UTF-8 on stdout so the statusLine output never crashes.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _config_path():
    """User override wins; otherwise the config bundled next to the script."""
    env = os.environ.get("USAGE_GAUGE_CONFIG")
    if env and os.path.exists(env):
        return env
    user = os.path.expanduser("~/.claude/usage-gauge/config.json")
    if os.path.exists(user):
        return user
    return os.path.join(SCRIPT_DIR, "config.json")


def _state_dir():
    """A writable dir that persists across plugin updates."""
    d = os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.expanduser("~/.claude/usage-gauge")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        d = os.path.expanduser("~")
    return d


CONFIG_PATH = _config_path()
STATE_PATH = os.path.join(_state_dir(), ".usage-gauge-state.json")

# ----------------------------------------------------------------------------- config
DEFAULTS = {
    # how often (seconds) the rendered gauge actually recomputes. Claude Code calls
    # the statusLine often; within this window we just reprint the cached render so
    # the readout is stable and cheap. Tunable: bump to 300 for a 5-min cadence.
    "refresh_seconds": 60,

    "bar_width": 20,         # cells in the shared bar
    "axis_max": 200,         # right edge of the projection axis (%)
    "green_lo": 80,          # white -> green boundary (%)
    "green_hi": 110,         # green -> yellow boundary (%)
    "yellow_hi": 150,        # yellow -> red boundary (%)

    # ignore the first slice of a window so a couple of early tokens don't divide by
    # a near-zero elapsed fraction and scream red. 0.03 == ~9 min into a 5h window.
    "min_elapsed_frac": 0.03,

    "block": "█",            # bar cell glyph
    "arrow_session": "▼",    # 5-hour pointer (above the bar); set "v" for ASCII
    "arrow_weekly": "▲",     # weekly pointer (below the bar); set "^" for ASCII
    "show_session": True,    # the 5-hour window (▼ above)
    "show_weekly": True,     # the 7-day all-models window (▲ below)
}

WINDOW_LEN = {            # seconds
    "five_hour": 5 * 3600,
    "seven_day": 7 * 86400,
}

# bright ANSI foreground colors + reset
C_WHITE = "\033[97m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"
C_DIM = "\033[90m"
RESET = "\033[0m"


def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    return cfg


def load_state():
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    try:
        tmp = STATE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp, STATE_PATH)
    except Exception:
        pass


def color_for(value, cfg):
    if value < cfg["green_lo"]:
        return C_WHITE
    if value < cfg["green_hi"]:
        return C_GREEN
    if value < cfg["yellow_hi"]:
        return C_YELLOW
    return C_RED


def projected_pct(used, resets_at, window_len, cfg, now):
    """used% extrapolated to the end of the window. Returns (projected, secs_left)."""
    secs_left = max(0.0, resets_at - now)
    elapsed = window_len - secs_left
    frac = max(cfg["min_elapsed_frac"], min(1.0, elapsed / window_len))
    return used / frac, secs_left


def build_bar(cfg):
    """Return the colored bar string (zones fixed; shared by both windows)."""
    width = cfg["bar_width"]
    axis = cfg["axis_max"]
    block = cfg["block"]
    out = []
    cur = None
    run = 0
    for i in range(width):
        v = (i + 0.5) / width * axis
        col = color_for(v, cfg)
        if col != cur:
            if run:
                out.append(cur + block * run)
            cur, run = col, 1
        else:
            run += 1
    if run:
        out.append(cur + block * run)
    return "".join(out) + RESET


def pointer_col(proj, cfg):
    width = cfg["bar_width"]
    frac = min(1.0, max(0.0, proj / cfg["axis_max"]))
    return min(width - 1, int(round(frac * (width - 1))))


def caret_label(name, arrow, proj, col):
    """Place 'NN<arrow>PP%' so <arrow> sits at column `col` of the bar."""
    label = f"{name}{arrow}{int(round(proj))}%"
    start = max(0, col - len(name))   # arrow is right after the 2-char name
    return " " * start + label


def render(limits, cfg, now):
    """One shared bar; 5h pointer above (▼), weekly pointer below (▲)."""
    bar = build_bar(cfg)
    top = bottom = None

    if cfg["show_session"] and "five_hour" in limits:
        w = limits["five_hour"]
        proj, _ = projected_pct(w["used"], w["resets_at"], WINDOW_LEN["five_hour"], cfg, now)
        col = pointer_col(proj, cfg)
        top = color_for(proj, cfg) + caret_label("5h", cfg["arrow_session"], proj, col) + RESET

    if cfg["show_weekly"] and "seven_day" in limits:
        w = limits["seven_day"]
        proj, _ = projected_pct(w["used"], w["resets_at"], WINDOW_LEN["seven_day"], cfg, now)
        col = pointer_col(proj, cfg)
        bottom = color_for(proj, cfg) + caret_label("wk", cfg["arrow_weekly"], proj, col) + RESET

    if top is None and bottom is None:
        return f"{C_DIM}usage gauge: waiting for first response…{RESET}"

    rows = []
    if top is not None:
        rows.append(top)
    rows.append(bar)
    if bottom is not None:
        rows.append(bottom)
    return "\n".join(rows)


def extract_limits(data):
    """Pull a normalized limits dict from statusLine stdin JSON, or {} if absent."""
    rl = data.get("rate_limits") or data.get("data", {}).get("rate_limits") or {}
    out = {}
    for win in ("five_hour", "seven_day"):
        w = rl.get(win)
        if w and w.get("used_percentage") is not None and w.get("resets_at"):
            out[win] = {"used": float(w["used_percentage"]), "resets_at": float(w["resets_at"])}
    return out


def main():
    cfg = load_config()
    now = time.time()

    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        data = {}

    state = load_state()
    fresh_limits = extract_limits(data)

    # remember the most recent real limits so the gauge keeps rendering even on the
    # calls where Claude Code didn't include rate_limits.
    known = state.get("limits", {})
    if fresh_limits:
        known.update(fresh_limits)
        state["limits"] = known

    # throttle: within refresh_seconds, reprint the cached render verbatim.
    if state.get("out") and (now - state.get("render_ts", 0)) < cfg["refresh_seconds"]:
        sys.stdout.write(state["out"])
        return

    out = render(known, cfg, now)
    state["out"] = out
    state["render_ts"] = now
    save_state(state)
    sys.stdout.write(out)


if __name__ == "__main__":
    main()
