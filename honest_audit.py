#!/usr/bin/env python3
"""
honest_audit.py — honesty gate: static audit of (AI-generated) code for hidden
forbidden mechanisms. Zero dependencies, Python 3.8+.

Scanning rules:
- Python: comments/docstrings/strings stripped via the `tokenize` module — code
  between tokens is NEVER touched. On 3.12+ f-string expressions are scanned
  (FSTRING_* tokens); on 3.8–3.11 expressions inside f-strings are not scanned
  (documented limitation). Unparseable files are scanned RAW and flagged WARN
  (UNPARSEABLE FILE) — never silently CLEAN.
- C family (.c/.cpp/.metal/.glsl/…): comments stripped by a state lexer;
  string literal contents ARE scanned (GPU kernels hide in C strings — real
  case, 2026-11-18). C++ raw strings R"(...)" are a documented limitation.

Every category is a kind of fraud actually caught in the wild. Your invariants
live in honesty_patterns.json — no code changes needed to adapt.

Usage:  python3 honest_audit.py [file_or_dir ...] [--patterns PATH] [--lang en|ru]
Exit:   0 clean · 1 BLOCK-severity finding · 2 config error (all fail CI/hooks)
"""
import io, os, re, sys, json, subprocess, tokenize

# ---------------------------------------------------------------------------
# Built-in default rule set (proven in a real research project, 2026-11).
# Overridden entirely by honesty_patterns.json (see resolve_config).
# ---------------------------------------------------------------------------
DEFAULT_CONFIG = {
    "skip_dirs": [".git", ".venv", "venv", "node_modules", "__pycache__",
                  "site-packages", "dist-info", ".venv_bench", "examples"],
    "skip_dir_suffixes": ["_env", ".egg-info", ".dist-info"],
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
                # C/GPU kernels (blind spot found 2026-11-18)
                r"_grad\b", r"\bgrad_\w+", r"\bgradient\w*\b", r"\bбэкпроп\w*\b",
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
            "why": "global argmax/top-k as a selector; legal in measurement harnesses — context is judged by a human",
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
            "why": "vector normalization is legal on the unit sphere; batch normalization is not",
            "patterns": [r"\bnormaliz\w*\b"],
        },
        "tanh (rejected formula)": {
            "severity": "warn",
            "why": "tanh rejected in this project except legal cases (Poincare) — human judges context",
            "patterns": [r"\btanh\b"],
        },
        "MAGIC CONSTANTS (candidates)": {
            "severity": "warn",
            "why": "thresholds must be derived from state, not invented",
            "patterns": [r"\b0\.[13579]\d*\b", r"\b[1-9]\.[13579]\d*\b"],
        },
        "DYNAMIC CODE EXECUTION": {
            "severity": "warn",
            "why": "exec/eval/dynamic import can smuggle any forbidden mechanism past a static gate",
            "patterns": [r"\bexec\s*\(", r"\beval\s*\(", r"__import__",
                         r"\bimportlib\b", r"\bcompile\s*\("],
        },
    },
}

SELF_EXCLUDE = {"honest_audit.py", "honest_audit_watch.py"}

STRINGS = {
    "en": {
        "verdict_clean": "CLEAN", "verdict_block": "FRAUD: ", "verdict_warn": "SUSPICIOUS: ",
        "header_v": "VERDICT", "header_h": "FINDINGS",
        "summary": "clean files: {c}, files with findings: {b}",
        "blocked": "FRAUD PRESENT (block-severity categories) — blocking.",
        "config_from": "rules: {src}", "config_builtin": "built-in defaults",
    },
    "ru": {
        "verdict_clean": "ЧИСТО", "verdict_block": "ПОДЛОГ: ", "verdict_warn": "ПОДОЗРИТЕЛЬНО: ",
        "header_v": "ВЕРДИКТ", "header_h": "НАХОДКИ",
        "summary": "чистых файлов: {c}, с находками: {b}",
        "blocked": "ЕСТЬ ПОДЛОГ (block-категории) — блокирую.",
        "config_from": "правила: {src}", "config_builtin": "встроенные по умолчанию",
    },
}

LANG = "en"
def S(key, **kw):
    s = STRINGS[LANG][key]
    return s.format(**kw) if kw else s

# ---------------------------------------------------------------------------
# Config: unified resolver (T9) + validation (T8)
# ---------------------------------------------------------------------------
KNOWN_KEYS = {"skip_dirs", "skip_dir_suffixes", "file_extensions", "categories"}

def _config_error(msg):
    print(f"[honesty] CONFIG ERROR: {msg}", file=sys.stderr)
    sys.exit(2)

def validate_config(cfg):
    """Normalize severity, compile patterns, reject unknown severities.
    Exit code 2 on any config error (fail-closed for CI/hooks)."""
    if not isinstance(cfg, dict) or "categories" not in cfg:
        _config_error("config must be an object with 'categories'")
    for key in cfg:
        if key.startswith("_"):
            continue
        if key not in KNOWN_KEYS:
            print(f"[honesty] warning: unknown top-level key {key!r} (ignored)", file=sys.stderr)
    cats = cfg["categories"]
    if not isinstance(cats, dict):
        _config_error("'categories' must be an object")
    for cat, spec in cats.items():
        sev = str(spec.get("severity", "")).lower()
        if sev not in ("block", "warn"):
            _config_error(f"category {cat!r}: unknown severity {spec.get('severity')!r} (use block|warn)")
        spec["severity"] = sev
        if "why" not in spec:
            print(f"[honesty] warning: category {cat!r} has no 'why'", file=sys.stderr)
        for p in spec.get("patterns", []):
            try:
                re.compile(p)
            except re.error as e:
                _config_error(f"category {cat!r}: bad regex {p!r}: {e}")
    merged = dict(DEFAULT_CONFIG)
    merged.update({k: v for k, v in cfg.items() if k in KNOWN_KEYS and k != "categories"})
    merged["categories"] = cats
    return merged

def load_config_from_dict(cfg):
    return validate_config(cfg)

def resolve_config(cli_path=None, start_dir=None):
    """Priority: --patterns > repo root of start_dir > script dir > start_dir > builtin.
    Returns (config, source_path_or_None)."""
    start_dir = os.path.abspath(start_dir or os.getcwd())
    candidates = [cli_path] if cli_path else []
    try:
        root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start_dir, stderr=subprocess.DEVNULL).decode().strip()
        candidates.append(os.path.join(root, "honesty_patterns.json"))
    except Exception:
        pass
    candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "honesty_patterns.json"))
    candidates.append(os.path.join(start_dir, "honesty_patterns.json"))
    for p in candidates:
        if p and os.path.isfile(p):
            try:
                with open(p, encoding="utf-8") as f:
                    cfg = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                _config_error(f"{p}: {e}")
            return validate_config(cfg), p
    return DEFAULT_CONFIG, None

CONFIG, CONFIG_SRC = DEFAULT_CONFIG, None  # resolved properly in main()

# ---------------------------------------------------------------------------
# Stripping (T1): Python via tokenize; C family via state lexer
# ---------------------------------------------------------------------------
def _blank(grid, srow, scol, erow, ecol, placeholder=None):
    for r in range(srow, erow + 1):
        if r - 1 >= len(grid):
            break
        row = grid[r - 1]
        a = scol if r == srow else 0
        b = ecol if r == erow else len(row)
        for i in range(a, min(b, len(row))):
            row[i] = " "
    if placeholder and srow - 1 < len(grid):
        row = grid[srow - 1]
        for i, ch in enumerate(placeholder):
            if scol + i < len(row):
                row[scol + i] = ch

def strip_python(text):
    """Return code with comments/strings blanked, or None if unparseable."""
    grid = [list(l) for l in text.split("\n")]
    fstring_middle = getattr(tokenize, "FSTRING_MIDDLE", None)
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except Exception:
        return None
    try:
        for tok in toks:
            t = tok.type
            if t == tokenize.COMMENT:
                _blank(grid, *tok.start, *tok.end)
            elif t == tokenize.STRING:
                _blank(grid, tok.start[0], tok.start[1], tok.end[0], tok.end[1], '""')
            elif fstring_middle is not None and t == fstring_middle:
                _blank(grid, tok.start[0], tok.start[1], tok.end[0], tok.end[1])
    except Exception:
        return None
    return "\n".join("".join(r) for r in grid)

def strip_c(text):
    """Strip // and /* */ comments; KEEP string/char literal contents (scanned)."""
    out = []
    i, n = 0, len(text)
    state = "code"
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if state == "code":
            if c == "/" and nxt == "/":
                state = "line"; i += 2; continue
            if c == "/" and nxt == "*":
                state = "block"; i += 2; continue
            if c == '"':
                state = "string"
            elif c == "'":
                state = "char"
            out.append(c); i += 1
        elif state == "line":
            if c == "\n":
                state = "code"; out.append("\n")
            i += 1
        elif state == "block":
            if c == "*" and nxt == "/":
                state = "code"; i += 2; continue
            if c == "\n":
                out.append("\n")  # keep line numbering stable
            i += 1
        else:  # string | char — contents preserved, escapes honoured
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1]); i += 2; continue
            if (state == "string" and c == '"') or (state == "char" and c == "'"):
                state = "code"
            i += 1
    return "".join(out)

C_EXTS = {".c", ".cc", ".cpp", ".mm", ".m", ".glsl", ".comp", ".metal", ".swift"}

def audit_text(text, ext=".py", config=None):
    config = config or CONFIG
    unparseable = False
    if ext in C_EXTS:
        code = strip_c(text)
    elif ext == ".py":
        code = strip_python(text)
        if code is None:
            code = text
            unparseable = True
    else:
        code = text
    hits = {}
    for cat, spec in config["categories"].items():
        n = 0
        for p in spec["patterns"]:
            n += len(re.findall(p, code))
        if n:
            hits[cat] = n
    if unparseable:
        hits["UNPARSEABLE FILE (scanned raw)"] = 1
    return hits

def severity(hits, config=None):
    """('block'|'warn'|'ok', category)."""
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
    if name in SELF_EXCLUDE:
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
            LANG = args[i + 1]; i += 2
        elif args[i] == "--patterns" and i + 1 < len(args):
            cli_patterns = args[i + 1]; i += 2
        elif not args[i].startswith("--"):
            paths.append(args[i]); i += 1
        else:
            i += 1
    CONFIG, CONFIG_SRC = resolve_config(cli_patterns)
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
