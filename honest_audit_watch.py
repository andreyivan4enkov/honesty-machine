#!/usr/bin/env python3
"""
honest_audit_watch.py — watcher: catches fraud right after a file is written.
Usage:
    python3 honest_audit_watch.py [paths...] [--interval SEC] [--log FILE] [--once]
Modes:
    --once   single pass (initial sweep), no watching;
    default  watches continuously, reports NEW findings to console and log.
State is kept in honest_audit_state.json next to this script (verdict per file),
so a file that was already reported is not re-reported until its verdict changes.
"""
import os, sys, time, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from honest_audit import audit_path, severity, skip_dir, skip_file

def collect_files(paths):
    files = set()
    for path in paths:
        if os.path.isfile(path):
            if not skip_file(os.path.basename(path)):
                files.add(os.path.abspath(path))
        else:
            for root, dirs, names in os.walk(path):
                dirs[:] = [d for d in dirs if not skip_dir(d)]
                for name in names:
                    if not skip_file(name):
                        files.add(os.path.abspath(os.path.join(root, name)))
    return sorted(files)

def main():
    argv = sys.argv[1:]
    once = "--once" in argv
    interval = 3.0
    log_path = "honest_audit.log"
    if "--interval" in argv:
        interval = float(argv[argv.index("--interval") + 1])
    if "--log" in argv:
        log_path = argv[argv.index("--log") + 1]
    paths = [a for a in argv if not a.startswith("--") and a not in (str(interval), log_path)]
    paths = [p for p in paths if p not in ("--once",)]
    if not paths:
        paths = ["."]

    here = os.path.dirname(os.path.abspath(__file__))
    state_file = os.path.join(here, "honest_audit_state.json")
    state = {}
    if os.path.exists(state_file):
        try:
            state = json.load(open(state_file, encoding="utf-8"))
        except Exception:
            state = {}

    def report(f, hits):
        sev, _ = severity(hits)
        if sev == "ok":
            return
        detail = ", ".join(f"{c}x{n}" for c, n in sorted(hits.items()))
        line = f"{time.strftime('%H:%M:%S')} [{sev.upper()}] {f} | {detail}"
        print(line, flush=True)
        with open(log_path, "a", encoding="utf-8") as fp:
            fp.write(line + "\n")

    def sweep(files, mtimes):
        for f in files:
            try:
                mtimes[f] = (os.path.getmtime(f), os.path.getsize(f))
            except OSError:
                mtimes[f] = None
            hits = audit_path(f)[0][1] if os.path.isfile(f) else {}
            sev, _ = severity(hits)
            v = sev
            if v != "ok" and v != state.get(f, {}).get("verdict", ""):
                report(f, hits)
            state[f] = {"verdict": v, "hits": hits}

    files = collect_files(paths)
    print(f"[watch] files under watch: {len(files)}, interval {interval}s, log: {log_path}", flush=True)
    mtimes = {}
    sweep(files, mtimes)
    json.dump(state, open(state_file, "w", encoding="utf-8"))
    print("[watch] initial sweep done.", flush=True)
    if once:
        return
    while True:
        time.sleep(interval)
        new_files = collect_files(paths)
        changed = [f for f in new_files
                   if f not in mtimes
                   or (os.path.isfile(f) and mtimes.get(f) != (os.path.getmtime(f), os.path.getsize(f)))]
        sweep([f for f in changed if os.path.isfile(f)], mtimes)
        json.dump(state, open(state_file, "w", encoding="utf-8"))

if __name__ == "__main__":
    main()
