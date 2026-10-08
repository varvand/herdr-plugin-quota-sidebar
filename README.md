# Quota in the Agents sidebar

<img width="625" height="188" alt="image" src="https://github.com/user-attachments/assets/b1940d9f-41b2-4874-84f9-5f618de3d214" />

Account quota lines on the last Agents-sidebar card. Herdr 0.9 has no free-standing block under the agents header, so the lines are pane metadata. Every other card stays clear. Hairlines use the same `─` rule as the Spaces and Agents sections.

The numbers come from [kwanwooi25/herdr-plugin-agent-quota](https://github.com/kwanwooi25/herdr-plugin-agent-quota) (`node index.js --limits`). Claude Code, Codex, and Grok are covered. Install that plugin first.

This copy is not linked in the current Herdr config. `prefix+u` opens that plugin's bottom usage pane instead. Link this one when the lines should sit on the last agent card.

Requires Herdr 0.9.0 or newer, `python3` on `PATH`, and Node on `PATH` (or `/opt/homebrew/bin/node`).

## Install

```bash
herdr plugin install kwanwooi25/herdr-plugin-agent-quota
git clone https://github.com/varvand/herdr-plugin-quota-sidebar.git ~/.config/herdr/plugins/quota-sidebar
herdr plugin link ~/.config/herdr/plugins/quota-sidebar --enabled
```

Toggle it with:

```bash
herdr plugin action invoke local.quota-sidebar.toggle
```

```toml
[[keys.command]]
key = "prefix+u"
type = "plugin_action"
command = "local.quota-sidebar.toggle"
description = "toggle agent usage in the sidebar"
```

The card needs `$qtop`, `$q0`, `$qbot`, and `$q1` through `$q6` with variants `ok`, `warn`, `bad`, and `na`. Empty tokens disappear. Put the four variants of a slot on one row. Herdr allows 16 sidebar rows, and a row per variant does not fit. The worker refreshes about every 45 seconds and removes the lines on toggle-off.

```toml
[{ token = "$qtop", fg = "#3b4261" }],
[{ token = "$q0", fg = "#565f89" }],
[
  { token = "$q1_ok", fg = "#9ece6a" },
  { token = "$q1_warn", fg = "#e0af68" },
  { token = "$q1_bad", fg = "#f7768e" },
  { token = "$q1_na", fg = "#565f89" },
],
[{ token = "$qbot", fg = "#3b4261" }],
```

Repeat the slot row for `$q2` through `$q6`. `$qbot` uses the same color as `$qtop`.
