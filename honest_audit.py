#!/usr/bin/env python3
"""
honest_audit.py — honesty gate: static audit of (AI-generated) code for hidden
forbidden mechanisms. Zero dependencies, Python 3.8+.

The auditor scans code WITHOUT comments and docstrings (words in comments are not
code). For C-family files (.c/.cpp/.metal/.glsl/...) string literals ARE scanned,
because GPU kernels hide inside C strings (real case, 2026-11-18).

Every category is a concrete kind of fraud that was actually caught in the wild —
not a theoretical list. You define your own invariants in honesty_patterns.json.

Usage:
    python3 honest_audit.py [file_or_dir ...] [--patterns PATH] [--lang en|ru]

Exit code: 1 if any BLOCK-severity category is found (for CI / pre-commit), else 0.

Adaptation (5 minutes): copy honesty_patterns.json to your repo, replace the
categories with YOUR project invariants (regex lists), done. No code changes.
"""
import re, sys, os, json

# ---------------------------------------------------------------------------
# Built-in default rule set (proven in a real research project, 2026-11).
# Overridden entirely by honesty_patterns.json if present.
# ---------------------------------------------------------------------------
DEFAULT_CONFIG = {
    "skip_dirs": [".git", ".venv", "venv", "node_modules", "__pycache__",
                  "site-packages", "dist-info", ".venv_bench"],
    "skip_dir_suffixes": ["_env", ".egg-info"],
    "file_extensions": [".py", ".c", ".cc", ".cpp", ".mm", ".m",
                        ".glsl", ".comp", ".metal", ".swift"],
    "categories": {
        "BACKPROP / gradient": {
            "severity": "block",
            "why": "hidden gradient training inside code that claims to be gradient-free",
            "patterns": [
                r"\bimport\s+torch\b", r"\btorch\.", r"\bautograd\b", r"\.backward\s*\(",
                r"\bloss\s*\.backward\b", r"\boptim\s*\.", r"\bAdam\b", r"\bSGD\b",
                r"\bzero_grad\b", r"\.grad\b",
                # C/GPU kernels (blind spot found 2026-11-18: a "full GPU backprop"
                # inside a .c file passed the audit when only Python patterns existed)
                r"_grad\b", r"\bgrad_\w+", r"\bgradient\w*\b",
                r"\bбэкпроп\w*\b",
                r"\blearning_rate\b", r"\bmomentum\b",
            ],
        },
        "SOFTMAX": {
            "severity": "block",
            "why": "softmax where the design forbids it (allowed only as a labeled baseline)",
            "patterns": [r"\bsoftmax\b"],
        },
        "BATCH-NORM / normalization": {
            "severity": "block",
            "why": "batch-norm/layer-norm/dropout normalize over the current batch",
            "patterns": [r"\bbatch_?norm\b", r"\blayer_?norm\b", r"\bdropout\b"],
        },
        "GLOBAL SELECTION (argmax/topk)": {
            "severity": "warn",
            "why": "global argmax/top-k as a selector; a local-dynamics selector is required",
            "patterns": [r"\bargmax\b", r"\btopk\b", r"\btop_k\b"],
        },
        "RANDOMNESS IN FORWARD": {
            "severity": "warn",
            "why": "forward pass must be deterministic (seeds in test harness are fine)",
            "patterns": [r"\brandn\b", r"\bmanual_seed\b", r"\bnp\.random\b",
                         r"\bdefault_rng\b", r"\brandom\.\w+\b"],
        },
        "MEAN / averaging": {
            "severity": "warn",
            "why": "averaging destroys source identity (project principle)",
            "patterns": [r"\bnp\.mean\b", r"\.mean\s*\(\s*\)", r"\baverage\b"],
        },
        "SIGMOID": {"severity": "warn", "why": "sigmoid", "patterns": [r"\bsigmoid\b"]},
        "normalize (vector — check context)": {
            "severity": "warn",
            "why": "vector normalization is legal on the unit sphere; batch normalization is not — context decides",
            "patterns": [r"\bnormaliz\w*\b"],
        },
        "tanh (rejected formula)": {
            "severity": "warn",
            "why": "tanh was rejected for this project (context decides: Poincare tanh is legal)",
            "patterns": [r"\btanh\b"],
        },
        "MAGIC CONSTANTS (candidates)": {
            "severity": "warn",
            "why": "thresholds must be derived from state, not invented",
            "patterns": [r"\b0\.[13579]\d*\b", r"\b[1-9]\.[13579]\d*\b"],
        },
    },
}

STRINGS = {
    "en": {
        "verdict_clean": "CLEAN",
        "verdict_block": "FRAUD: ",
        "verdict_warn": "SUSPICIOUS: ",
        "header_v": "VERDICT", "header_h": "FINDINGS",
        "summary": "clean files: {c}, files with findings: {b}",
        "blocked": "FRAUD PRESENT (block-severity categories) — blocking.",
        "config_from": "rules: {src}",
        "config_builtin": "built-in defaults",
    },
    "ru": {
        "verdict_clean": "ЧИСТО",
        "verdict_block": "ПОДЛОГ: ",
        "verdict_warn": "ПОДОЗРИТЕЛЬНО: ",
        "header_v": "ВЕРДИКТ", "header_h": "НАХОДКИ",
        "summary": "чистых файлов: {c}, с находками: {b}",
        "blocked": "ЕСТЬ ПОДЛОГ (block-категории) — блокирую.",
        "config_from": "правила: {src}",
        "config_builtin": "встроенные по умолчанию",
    },
}

LANG = "en"
def S(key, **kw):
    s = STRINGS[LANG][key]
    return s.format(**kw) if kw else s

# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------
def load_config(cli_path=None):
    """Priority: --patterns PATH > ./honesty_patterns.json > built-in defaults."""
    candidates = [cli_path] if cli_path else []
    candidates.append(os.path.join(os.getcwd(), "honesty_patterns.json"))
    for p in candidates:
        if p and os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                cfg = json.load(f)
            merged = dict(DEFAULT_CONFIG)
            merged.update({k: v for k, v in cfg.items() if k != "categories"})
            if "categories" in cfg:
                merged["categories"] = cfg["categories"]
            return merged, p
    return DEFAULT_CONFIG, None

CONFIG, CONFIG_SRC = DEFAULT_CONFIG, None  # reloaded properly in main()

# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------
def strip_comments(text, keep_strings=False):
    # Block comments /* ... */ first (words in comments can hide or fake code).
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    out = []
    in_doc = None
    for line in text.split("\n"):
        s = line.strip()
        if in_doc:
            if in_doc in s:
                in_doc = None
            continue
        if s.startswith("#") or s.startswith("//"):
            continue
        s = re.sub(r"\s//.*$", "", s)
        for q in ('"""', "'''"):
            if q in s:
                parts = s.split(q)
                if len(parts) >= 3:
                    continue
                in_doc = q
                s = parts[0]
                break
        if in_doc:
            continue
        s = re.sub(r"\s#.*$", "", s)
        if not keep_strings:
            s = re.sub(r"(['\"])(?:\\.|(?!\1).)*\1", '""', s)
        out.append(s)
    return "\n".join(out)

C_EXTS = {".c", ".cc", ".cpp", ".mm", ".m", ".glsl", ".comp", ".metal", ".swift"}

def audit_text(text, ext=".py", config=None):
    config = config or CONFIG
    code = strip_comments(text, keep_strings=(ext in C_EXTS))
    hits = {}
    for cat, spec in config["categories"].items():
        n = 0
        for p in spec["patterns"]:
            n += len(re.findall(p, code))
        if n:
            hits[cat] = n
    return hits

def severity(hits, config=None):
    """('block'|'warn'|'ok', category) — what blocks the commit vs what warns."""
    config = config or CONFIG
    if not hits:
        return "ok", ""
    for cat in hits:
        if config["categories"].get(cat, {}).get("severity") == "block":
            return "block", cat
    for cat in sorted(hits):
        return "warn", cat
    return "ok", ""

def verdict(hits, config=None):
    sev, cat = severity(hits, config)
    if sev == "ok":
        return S("verdict_clean")
    if sev == "block":
        return S("verdict_block") + cat
    return S("verdict_warn") + cat

# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------
def skip_dir(d, config=None):
    config = config or CONFIG
    if d in set(config["skip_dirs"]):
        return True
    return any(d.endswith(suf) for suf in config.get("skip_dir_suffixes", []))

def skip_file(name, config=None):
    config = config or CONFIG
    if name.startswith("honest_audit"):
        return True
    return os.path.splitext(name)[1].lower() not in set(config["file_extensions"])

def audit_path(path, config=None):
    config = config or CONFIG
    results = []
    if os.path.isfile(path):
        files = [path] if not skip_file(os.path.basename(path), config) else []
    else:
        files = []
        for root, dirs, names in os.walk(path):
            dirs[:] = [d for d in dirs if not skip_dir(d, config)]
            for name in names:
                if not skip_file(name, config):
                    files.append(os.path.join(root, name))
    for f in sorted(files):
        try:
            text = open(f, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        hits = audit_text(text, os.path.splitext(f)[1].lower(), config)
        results.append((f, hits))
    return results

# ---------------------------------------------------------------------------
def main(argv):
    global LANG, CONFIG, CONFIG_SRC
    args = argv[1:]
    cli_patterns = None
    paths = []
    i = 0
    while i < len(args):
        if args[i] == "--lang" and i + 1 < len(args):
            LANG = args[i + 1]
            i += 2
        elif args[i] == "--patterns" and i + 1 < len(args):
            cli_patterns = args[i + 1]
            i += 2
        elif not args[i].startswith("--"):
            paths.append(args[i])
            i += 1
        else:
            i += 1
    CONFIG, CONFIG_SRC = load_config(cli_patterns)
    paths = paths or ["."]

    clean = bad = 0
    blocked = False
    print(S("config_from", src=CONFIG_SRC or S("config_builtin")))
    print(f"{S('header_v'):45s} {S('header_h')}")
    print("-" * 90)
    for path in paths:
        for f, hits in audit_path(path):
            v = verdict(hits)
            sev, _ = severity(hits)
            if sev == "block":
                blocked = True
            if sev == "ok":
                clean += 1
                continue
            bad += 1
            detail = ", ".join(f"{c}x{n}" for c, n in sorted(hits.items()))
            rel = os.path.relpath(f) if not os.path.isabs(f) else f
            print(f"{v:45s} {rel}")
            print(f"{'':45s}   {detail}")
    print("-" * 90)
    print(S("summary", c=clean, b=bad))
    if blocked:
        print(S("blocked"))
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main(sys.argv)
