# Quota in the Agents sidebar

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

The card needs tokens `$qtop`, `$q0`, `$qbot`, and `$q1_ok` through `$q6_bad` (variants `ok`, `warn`, `bad`, `na`). Empty tokens disappear. The worker refreshes about every 45 seconds and removes the lines on toggle-off.
