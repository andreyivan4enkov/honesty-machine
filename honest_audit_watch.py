#!/usr/bin/env python3
"""
honest_audit_watch.py — watcher: catches fraud right after a file is written.
Uses the SAME config resolver as the CLI (resolve_config) and reloads the rules
whenever honesty_patterns.json changes on disk (no restart needed).

Usage:
    python3 honest_audit_watch.py [paths...] [--interval SEC] [--log FILE]
                                  [--patterns PATH] [--once]
State: honest_audit_state.json next to this script (verdict per file); files
deleted from disk are pruned from the state.
"""
import argparse, os, sys, time, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import honest_audit as ha


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="honesty gate watcher")
    p.add_argument("paths", nargs="*", default=["."], help="files/dirs to watch")
    p.add_argument("--interval", type=float, default=3.0)
    p.add_argument("--log", default="honest_audit.log")
    p.add_argument("--patterns", default=None)
    p.add_argument("--once", action="store_true")
    return p.parse_args(argv)


def collect_files(paths):
    files = set()
    for path in paths:
        if os.path.isfile(path):
            if not ha.skip_file(os.path.basename(path)):
                files.add(os.path.abspath(path))
        else:
            for root, dirs, names in os.walk(path):
                dirs[:] = [d for d in dirs if not ha.skip_dir(d)]
                for name in names:
                    if not ha.skip_file(name):
                        files.add(os.path.abspath(os.path.join(root, name)))
    return sorted(files)


def main(argv=None):
    args = parse_args(argv)
    config, config_src = ha.resolve_config(args.patterns)
    config_mtime = os.path.getmtime(config_src) if config_src else None

    here = os.path.dirname(os.path.abspath(__file__))
    state_file = os.path.join(here, "honest_audit_state.json")
    state = {}
    if os.path.exists(state_file):
        try:
            state = json.load(open(state_file, encoding="utf-8"))
        except Exception:
            state = {}

    def report(f, hits):
        sev, _ = ha.severity(hits, config)
        if sev == "ok":
            return
        detail = ", ".join(f"{c}x{n}" for c, n in sorted(hits.items()))
        line = f"{time.strftime('%H:%M:%S')} [{sev.upper()}] {f} | {detail}"
        print(line, flush=True)
        with open(args.log, "a", encoding="utf-8") as fp:
            fp.write(line + "\n")

    def sweep(files, mtimes):
        for f in files:
            try:
                mtimes[f] = (os.path.getmtime(f), os.path.getsize(f))
            except OSError:
                mtimes[f] = None
            hits = ha.audit_path(f, config)[0][1] if os.path.isfile(f) else {}
            sev, _ = ha.severity(hits, config)
            if sev != "ok" and sev != state.get(f, {}).get("verdict", ""):
                report(f, hits)
            state[f] = {"verdict": sev, "hits": hits}

    files = collect_files(args.paths)
    print(f"[watch] files: {len(files)}, interval {args.interval}s, log: {args.log}, rules: {config_src or 'built-in'}",
          flush=True)
    mtimes = {}
    sweep(files, mtimes)
    json.dump(state, open(state_file, "w", encoding="utf-8"))
    print("[watch] initial sweep done.", flush=True)
    if args.once:
        return

    while True:
        time.sleep(args.interval)
        # hot-reload rules
        if config_src and os.path.isfile(config_src):
            m = os.path.getmtime(config_src)
            if m != config_mtime:
                config_mtime = m
                config, config_src = ha.resolve_config(args.patterns)
                print("[watch] rules reloaded — full resweep", flush=True)
                sweep(collect_files(args.paths), mtimes)
        new_files = collect_files(args.paths)
        changed = []
        for f in new_files:
            try:
                cur = (os.path.getmtime(f), os.path.getsize(f))
            except OSError:
                continue
            if mtimes.get(f) != cur:
                changed.append(f)
        sweep(changed, mtimes)
        # prune deleted files from state
        for f in [f for f in state if not os.path.exists(f)]:
            del state[f]
            mtimes.pop(f, None)
        json.dump(state, open(state_file, "w", encoding="utf-8"))


if __name__ == "__main__":
    main()
