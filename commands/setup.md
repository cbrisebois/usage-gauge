---
description: Wire the usage-gauge into your Claude Code footer (statusLine)
---

Set up the **usage-gauge** status line. This is a one-time step (plugins can't
declare a `statusLine` natively, so we add it to `~/.claude/settings.json`).

## Steps

1. **Locate the bundled script.** Use Glob to find `gauge.py` under
   `~/.claude/plugins/` recursively — pattern `**/gauge.py`, taking the result whose
   path contains `usage-gauge`. Save it as SCRIPT_PATH. (At runtime the plugin also
   exposes this directory as `${CLAUDE_PLUGIN_ROOT}`, but Glob is the reliable way to
   discover the concrete install path from a command.)

2. **Pick the Python interpreter.** Run `command -v python3`. If it resolves, use
   `python3`. Otherwise tell the user they need Python 3 on their PATH and stop.

3. **Read** `~/.claude/settings.json` (create `{}` if missing). Check whether a
   `statusLine` key already exists:
   - If it points at another tool (e.g. `claude_status.py`/claude-pulse), tell the
     user it will be replaced and ask them to confirm before overwriting.

4. **Write** this key into `~/.claude/settings.json`, preserving all other keys, and
   using the concrete SCRIPT_PATH you found (NOT the literal `${CLAUDE_PLUGIN_ROOT}`,
   which a hand-edited settings.json won't expand):

   ```json
   "statusLine": {
     "type": "command",
     "command": "python3 \"<SCRIPT_PATH>\""
   }
   ```

5. **Confirm to the user:**
   - "usage-gauge is wired up — restart Claude Code (or start a new session) to see it."
   - "Until the first model response of a session, it shows a placeholder; the limit
     data (`rate_limits`) only arrives after the first turn, and only on Pro/Max plans."
   - "Tune it by copying the plugin's `config.json` to `~/.claude/usage-gauge/config.json`
     and editing thresholds / `refresh_seconds` there (your copy overrides the bundled one)."
