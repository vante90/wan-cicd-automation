#!/usr/bin/env python3
"""Push a bootstrap config to a router through its GNS3 console (telnet).

Needed only for the first configuration. B1/B2/C1/C2 have no SSH until the
bootstrap is applied; afterwards Ansible takes over.

Setup:
    python3 -m venv .venv && . .venv/bin/activate
    pip install netmiko

Usage (console ports are shown in the GNS3 Topology Summary / node info):
    export LAB_ADMIN_PASSWORD='choose-a-password'      # never commit this
    python3 scripts/push_bootstrap.py A1 5000 --stages 1,2,3
    python3 scripts/push_bootstrap.py B1 5004 --stages 1-3

Run stages in order and verify between them (see docs/addressing.md).
Stage 1 replaces CHANGE_ME with $LAB_ADMIN_PASSWORD.
"""
import argparse
import os
import re
import sys
from pathlib import Path

from netmiko import ConnectHandler

STAGE_RE = re.compile(r"^! ===== STAGE (\d+):")


def parse_stages(text):
    stages, current = {}, None
    for line in text.splitlines():
        m = STAGE_RE.match(line)
        if m:
            current = int(m.group(1))
            stages[current] = []
            continue
        if current is not None:
            stages[current].append(line)
    return stages


def parse_range(spec):
    out = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def clean(lines, password):
    """Drop comments and the end/write lines, substitute the password."""
    cmds = []
    for line in lines:
        s = line.rstrip()
        if not s.strip() or s.lstrip().startswith("!"):
            continue
        if s.strip() in ("end", "write memory"):
            continue
        cmds.append(s.replace("CHANGE_ME", password))
    return cmds


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("router", help="A1, A2, B1, B2, C1 or C2")
    ap.add_argument("port", type=int, help="GNS3 console (telnet) port of that router")
    ap.add_argument("--host", default="127.0.0.1", help="GNS3 server address (default 127.0.0.1)")
    ap.add_argument("--stages", default="1-6", help="e.g. 1-3 or 1,2,5 (default all)")
    ap.add_argument("--cfg-dir", default="configs/bootstrap")
    ap.add_argument("--dry-run", action="store_true", help="print the commands, do not connect")
    ap.add_argument("--no-save", action="store_true", help="do not run 'write memory' at the end")
    args = ap.parse_args()

    password = os.environ.get("LAB_ADMIN_PASSWORD", "")
    if not password and not args.dry_run:
        sys.exit("Set LAB_ADMIN_PASSWORD first (it replaces CHANGE_ME, never commit it).")
    password = password or "CHANGE_ME"

    cfg = Path(args.cfg_dir) / f"{args.router}.cfg"
    if not cfg.is_file():
        sys.exit(f"{cfg} not found")
    stages = parse_stages(cfg.read_text())
    wanted = parse_range(args.stages)
    missing = [n for n in wanted if n not in stages]
    if missing:
        sys.exit(f"stage(s) {missing} not in {cfg}")

    if args.dry_run:
        for n in wanted:
            print(f"--- stage {n}")
            print("\n".join(clean(stages[n], password if password != "CHANGE_ME" else "<password>")))
        return

    conn = ConnectHandler(
        device_type="cisco_ios_telnet",
        host=args.host,
        port=args.port,
        username="",
        password="",
        secret="",
        global_delay_factor=2,
        fast_cli=False,
    )
    try:
        conn.write_channel("\r\n")
        conn.find_prompt()
        conn.enable()
        for n in wanted:
            cmds = clean(stages[n], password)
            print(f"[{args.router}] stage {n}: {len(cmds)} commands")
            # crypto key generation takes a while on IOSv
            out = conn.send_config_set(cmds, cmd_verify=False, read_timeout=240)
            for bad in ("% Invalid", "% Incomplete", "% Ambiguous", "% Unknown"):
                if bad in out:
                    print(f"[{args.router}] WARNING stage {n}: output contains '{bad}':")
                    print(out)
                    break
        if not args.no_save:
            print(conn.send_command_timing("write memory"))
    finally:
        conn.disconnect()


if __name__ == "__main__":
    main()
