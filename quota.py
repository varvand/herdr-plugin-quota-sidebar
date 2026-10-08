#!/usr/bin/python3
"""Toggle the account quota lines inside the Agents sidebar.

Herdr has no free-standing sidebar widget, so the lines are metadata on the
first agent card. Empty tokens disappear, and every other card stays as it was.
Ctrl-b u calls --toggle. The numbers come from herdr-plugin-agent-quota.
"""

import glob
import json
import os
import signal
import socket
import subprocess
import sys
import time

SOURCE = "local.quota-sidebar"
SHORT = {"claude": "CC", "codex": "CDX", "grok": "GRX"}
SLOTS = 6
VARIANTS = ("ok", "warn", "bad", "na")
GAUGE_W = 5
TTL_MS = 180000
INTERVAL_S = 45
SOCKET_PATH = os.environ.get("HERDR_SOCKET_PATH") or os.path.expanduser(
    "~/.config/herdr/herdr.sock"
)

STOP = False


def state_dir():
    path = os.environ.get("HERDR_PLUGIN_STATE_DIR")
    if not path:
        path = os.path.expanduser("~/.local/state/herdr/plugins/local.quota-sidebar")
    os.makedirs(path, exist_ok=True)
    return path


def flag_path():
    return os.path.join(state_dir(), "enabled")


def pid_path():
    return os.path.join(state_dir(), "worker.pid")


def holders_path():
    return os.path.join(state_dir(), "holders.json")


def log(message):
    try:
        path = os.path.join(state_dir(), "quota.log")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(time.strftime("%H:%M:%S ") + message + "\n")
    except OSError:
        pass


def token_names():
    names = ["qtop", "q0", "qbot"]
    for slot in range(1, SLOTS + 1):
        for variant in VARIANTS:
            names.append("q%d_%s" % (slot, variant))
    return names


NAMES = token_names()


class Herdr:
    def __init__(self):
        self.sock = None
        self.seq = time.time_ns() // 1000000

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

    def call(self, method, params):
        payload = json.dumps({"id": "quota", "method": method, "params": params}).encode() + b"\n"
        last = None
        for _attempt in (1, 2):
            try:
                if self.sock is None:
                    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    sock.settimeout(3.0)
                    sock.connect(SOCKET_PATH)
                    self.sock = sock
                self.sock.sendall(payload)
                buf = b""
                while b"\n" not in buf:
                    chunk = self.sock.recv(1 << 20)
                    if not chunk:
                        raise ConnectionError("socket closed")
                    buf += chunk
                message = json.loads(buf.split(b"\n", 1)[0])
                if "error" in message:
                    raise RuntimeError(json.dumps(message["error"])[:240])
                return message.get("result")
            except (OSError, ConnectionError, json.JSONDecodeError, RuntimeError) as exc:
                last = exc
                self.close()
        raise last

    def next_seq(self):
        self.seq += 1
        return self.seq


def quota_index():
    matches = sorted(
        glob.glob(
            os.path.expanduser(
                "~/.config/herdr/plugins/github/herdr-plugin-agent-quota-*/index.js"
            )
        )
    )
    if not matches:
        raise RuntimeError("herdr-plugin-agent-quota is not installed")
    return matches[-1]


def collect_limits():
    node = "/opt/homebrew/bin/node"
    if not os.path.isfile(node):
        node = "node"
    result = subprocess.run(
        [node, quota_index(), "--limits"],
        capture_output=True,
        text=True,
        timeout=25,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "limits failed").strip()[:240])
    return json.loads(result.stdout)


def fmt_reset(ms):
    if not ms:
        return None
    reset = time.localtime(ms / 1000.0)
    now = time.localtime()
    hour24 = reset.tm_hour
    hour = hour24 % 12 or 12
    minute = "%02d" % reset.tm_min
    period = "am" if hour24 < 12 else "pm"
    same_day = (
        reset.tm_year == now.tm_year
        and reset.tm_yday == now.tm_yday
    )
    if same_day:
        return "%d:%s%s" % (hour, minute, period)
    clock = "%d%s" % (hour, period) if minute == "00" else "%d:%s%s" % (hour, minute, period)
    return "%s %d %s" % (time.strftime("%b", reset), reset.tm_mday, clock)


def gauge(pct):
    filled = 0 if pct <= 0 else max(1, int(round((pct / 100.0) * GAUGE_W)))
    filled = min(GAUGE_W, filled)
    return ("━" * filled) + ("─" * (GAUGE_W - filled))


def severity(used):
    if used >= 80:
        return "bad"
    if used >= 50:
        return "warn"
    return "ok"


def quota_rows(limits):
    rows = []
    for agent in ("claude", "codex", "grok"):
        snap = limits.get(agent) or {}
        for window in snap.get("windows") or []:
            label = str(window.get("label") or "?")[:3]
            used = window.get("pct")
            try:
                used = max(0, min(100, float(used)))
            except (TypeError, ValueError):
                continue
            resets = window.get("resetsAt") or 0
            if resets and resets < time.time() * 1000:
                text = "%-3s %-3s %s  -%%" % (SHORT[agent], label, "─" * GAUGE_W)
                rows.append(("na", text))
                continue
            reset = fmt_reset(resets)
            suffix = (" ↻%s" % reset) if reset else ""
            text = "%-3s %-3s %s %3d%%%s" % (SHORT[agent], label, gauge(used), int(round(used)), suffix)
            rows.append((severity(used), text))
            if len(rows) >= SLOTS:
                return rows
    return rows


def desired_tokens(rows):
    tokens = {}
    if not rows:
        return tokens
    # Same hairline the Spaces and Agents sections use.
    rule = "─" * 40
    tokens["qtop"] = rule
    tokens["q0"] = "quota  ·  used"
    for index, (kind, text) in enumerate(rows, 1):
        tokens["q%d_%s" % (index, kind)] = text
    tokens["qbot"] = rule
    return tokens


def load_holders():
    try:
        data = json.load(open(holders_path(), encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_holders(holders):
    with open(holders_path(), "w", encoding="utf-8") as handle:
        json.dump(holders, handle)


def agent_pane_ids(client):
    result = client.call("session.snapshot", {})
    snapshot = result.get("snapshot") if isinstance(result, dict) else None
    agents = snapshot.get("agents") if isinstance(snapshot, dict) else None
    if not isinstance(agents, list):
        return []
    return [agent["pane_id"] for agent in agents if isinstance(agent, dict) and agent.get("pane_id")]


def send_tokens(client, pane_id, tokens):
    if not tokens:
        return
    # The API accepts at most 16 token fields per call.
    items = list(tokens.items())
    for start in range(0, len(items), 16):
        chunk = dict(items[start : start + 16])
        client.call(
            "pane.report_metadata",
            {
                "pane_id": pane_id,
                "source": SOURCE,
                "tokens": chunk,
                "ttl_ms": TTL_MS,
                "seq": client.next_seq(),
            },
        )


def clear_pane(client, pane_id, previous):
    tokens = {name: None for name in previous}
    tokens["q0"] = None
    send_tokens(client, pane_id, tokens)


def publish(client):
    rows = quota_rows(collect_limits())
    wanted = desired_tokens(rows)
    panes = agent_pane_ids(client)
    # Under the last listed agent, so the block sits at the bottom of the list.
    anchor = panes[-1] if panes else None
    holders = load_holders()
    seen = set(holders)
    if anchor:
        seen.add(anchor)
    for pane_id in seen:
        if pane_id == anchor:
            previous = set(holders.get(pane_id) or [])
            tokens = dict(wanted)
            for name in previous:
                tokens.setdefault(name, None)
            send_tokens(client, pane_id, tokens)
            holders[pane_id] = sorted(wanted)
        elif pane_id in holders:
            clear_pane(client, pane_id, holders.get(pane_id) or [])
            holders.pop(pane_id, None)
    if anchor is None:
        holders = {}
    save_holders(holders)
    log("anchor %s lines %d" % (anchor, len(rows)))


def clear_all():
    client = Herdr()
    try:
        holders = load_holders()
        for pane_id, names in list(holders.items()):
            try:
                clear_pane(client, pane_id, names or [])
            except (OSError, ConnectionError, RuntimeError) as exc:
                log("clear %s failed: %s" % (pane_id, exc))
        save_holders({})
    finally:
        client.close()


def request_stop(_signum, _frame):
    global STOP
    STOP = True


def run_worker():
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    with open(pid_path(), "w", encoding="utf-8") as handle:
        handle.write(str(os.getpid()))
    log("started pid %s" % os.getpid())
    client = Herdr()
    while not STOP and os.path.exists(flag_path()):
        try:
            publish(client)
        except (OSError, ConnectionError, RuntimeError, subprocess.TimeoutExpired, ValueError) as exc:
            log("refresh failed: %s" % exc)
        deadline = time.monotonic() + INTERVAL_S
        while time.monotonic() < deadline and not STOP and os.path.exists(flag_path()):
            time.sleep(0.2)
    try:
        clear_all()
    except (OSError, ConnectionError, RuntimeError) as exc:
        log("shutdown clear failed: %s" % exc)
    client.close()
    log("stopped")
    return 0


def alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def read_pid():
    try:
        return int(open(pid_path(), encoding="utf-8").read().strip())
    except (OSError, ValueError):
        return None


def stop_worker():
    try:
        os.remove(flag_path())
    except OSError:
        pass
    pid = read_pid()
    if pid and alive(pid):
        os.kill(pid, signal.SIGTERM)
        for _ in range(20):
            if not alive(pid):
                break
            time.sleep(0.05)
    clear_all()


def start_worker():
    open(flag_path(), "a").close()
    pid = read_pid()
    if pid and alive(pid):
        return
    subprocess.Popen(
        [sys.executable, os.path.abspath(__file__), "--worker"],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=os.environ.copy(),
    )


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--toggle"
    if mode == "--worker":
        return run_worker()
    if mode == "--resume":
        if os.path.exists(flag_path()):
            start_worker()
        return 0
    if mode == "--toggle":
        pid = read_pid()
        if os.path.exists(flag_path()) and pid and alive(pid):
            stop_worker()
            sys.stdout.write("hidden\n")
        else:
            start_worker()
            sys.stdout.write("shown\n")
        return 0
    sys.stderr.write("usage: quota.py [--toggle|--resume|--worker]\n")
    return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
