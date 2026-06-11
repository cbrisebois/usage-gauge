# usage-gauge

A Claude Code **footer pace gauge** for your subscription limits. One
white/green/yellow/red bar tells you, at a glance, whether you're using your
**5-hour session** and **7-day (all-models)** budgets *efficiently* — fully, but
without running out before they reset.

```
         5h▼112%          ← session pointer (▼ above) — here: yellow "too hot"
████████ ███ ████ █████
  wk▲41%                  ← weekly pointer (▲ below) — here: white "under-using"
```

Zero API calls: it reads the `rate_limits` block Claude Code already pipes to
statusLine scripts on stdin (the same data behind `/usage`).

## What the colors mean

The bar's axis is **projected utilization at reset** —
`projected% = used% ÷ fraction-of-window-elapsed`, i.e. *"if I keep this pace,
where will I land when the window resets?"* The pointer sits at that projection:

| Projected at reset | Zone | Meaning |
|---|---|---|
| `< green_lo` (80%) | ⬜ white | under-using — wasting budget |
| `green_lo..green_hi` (80–110%) | 🟩 green | on pace to land ~exactly at reset ✅ |
| `green_hi..yellow_hi` (110–150%) | 🟨 yellow | too hot — fine *if you slow down* |
| `> yellow_hi` (150%) | 🟥 red | will run out well before reset — stop |

The 5-hour session pointer rides **above** the bar (`5h▼`), the weekly pointer
**below** it (`wk▲`). Both share one bar because the zones are identical.

## Requirements

- Claude Code **v2.1.80+** (the `rate_limits` stdin field) — tested on v2.1.173
- **Python 3** on your `PATH`
- A **Pro / Max** plan (the `rate_limits` data isn't sent on other plans, and only
  appears after the first model response of a session)

## Install

```text
/plugin marketplace add cbrisebois/usage-gauge
/plugin install usage-gauge@cbrisebois
/usage-gauge:setup
```

`/usage-gauge:setup` adds the `statusLine` entry to `~/.claude/settings.json`
(plugins can't set a statusLine on their own). Then **restart Claude Code**.

## Configure

Copy the bundled `config.json` to `~/.claude/usage-gauge/config.json` and edit it —
your copy overrides the bundled defaults. Or point `USAGE_GAUGE_CONFIG` at any file.

| Key | Default | What it does |
|---|---|---|
| `refresh_seconds` | `60` | how often the gauge recomputes (e.g. `300` for 5-min cadence) |
| `green_lo` / `green_hi` / `yellow_hi` | `80` / `110` / `150` | zone boundaries (projected %) |
| `bar_width` | `20` | cells in the bar |
| `axis_max` | `200` | right edge of the projection axis (%) |
| `min_elapsed_frac` | `0.03` | early-window damping (~9 min into a 5h window) |
| `block` | `█` | bar glyph |
| `show_session` / `show_weekly` | `true` | toggle either pointer |

## Manual install (no plugin)

Drop `gauge.py` + `config.json` anywhere and add to `~/.claude/settings.json`:

```json
"statusLine": { "type": "command", "command": "python3 \"/abs/path/to/gauge.py\"" }
```

## License

MIT
