# T0: test scaffold for Honesty Machine fixes (branch fix/audit-findings-2026-11-18).
# Red->Green per docs/FIX_SPEC.md: each test cites the task it proves.
# Fixtures with fraud live as .txt so the pre-commit gate does not block the tests.
import io, os, sys, unittest
from contextlib import redirect_stderr, redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import honest_audit as ha


def fx(name):
    with open(os.path.join(ROOT, "tests", "fixtures", name), encoding="utf-8") as f:
        return f.read()


class TestStripTokenizer(unittest.TestCase):
    """T1: comment/string stripping must never eat real code."""

    def test_poc1_code_between_strings_kept(self):
        # Qwen PoC1 — регрессионный контроль: старый код это ловил, новый обязан тоже.
        h = ha.audit_text("print('a'); import torch; print('b')", ".py")
        self.assertIn("BACKPROP / gradient", h)

    def test_poc2_docstring_closing_line_keeps_code(self):
        h = ha.audit_text(fx("poc2_docstring.py.txt"), ".py")
        self.assertIn("BACKPROP / gradient", h)

    def test_poc3_fake_c_comment_in_strings(self):
        h = ha.audit_text(fx("poc3_fake_block_comment.py.txt"), ".py")
        self.assertIn("BACKPROP / gradient", h)

    def test_poc4_hash_inside_c_string(self):
        h = ha.audit_text(fx("poc4_hash_in_c_string.c.txt"), ".c")
        self.assertIn("BACKPROP / gradient", h)

    def test_strings_still_not_scanned_in_python(self):
        h = ha.audit_text('s = "import torch inside a string"\n', ".py")
        self.assertNotIn("BACKPROP / gradient", h)

    def test_comments_not_scanned_in_python(self):
        h = ha.audit_text("# import torch — только комментарий\n", ".py")
        self.assertNotIn("BACKPROP / gradient", h)

    def test_c_comments_stripped_strings_kept(self):
        h = ha.audit_text('// learning_rate in comment\nconst char* k = "learning_rate";\n', ".c")
        self.assertEqual(h.get("BACKPROP / gradient"), 1)  # строка — да, комментарий — нет

    def test_c_escaped_quote_in_string(self):
        h = ha.audit_text('const char* k = "a \\" b learning_rate";\n', ".c")
        self.assertIn("BACKPROP / gradient", h)

    def test_unparseable_py_warns_not_clean(self):
        h = ha.audit_text("def broken(:\n    import torch\n", ".py")
        self.assertIn("BACKPROP / gradient", h)  # сырой текст сканируется
        self.assertTrue(any("UNPARSEABLE" in c for c in h))
        self.assertEqual(ha.severity(h)[0], "warn")

    def test_fstring_expression_scanned(self):
        # 3.12+: выражения внутри f-string — код. На 3.8-3.11 — documented limitation.
        import tokenize
        if hasattr(tokenize, "FSTRING_START"):
            h = ha.audit_text('f"{x.grad}"\n', ".py")
            self.assertIn("BACKPROP / gradient", h)


class TestSelfExclusion(unittest.TestCase):
    """T4: только точные имена инструментов пропускаются."""

    def test_prefix_helpers_not_skipped(self):
        self.assertFalse(ha.skip_file("honest_audit_helpers.py"))
        self.assertFalse(ha.skip_file("honest_audit_evil.c"))

    def test_tools_themselves_skipped(self):
        self.assertTrue(ha.skip_file("honest_audit.py"))
        self.assertTrue(ha.skip_file("honest_audit_watch.py"))


class TestConfig(unittest.TestCase):
    """T8/T9: валидация конфига, exit 2, единый резолвер."""

    def test_severity_uppercase_normalized(self):
        cfg = dict(ha.DEFAULT_CONFIG)
        cfg["categories"] = {"X": {"severity": "BLOCK", "patterns": ["torch"]}}
        cfg = ha.validate_config(cfg)
        self.assertEqual(ha.severity({"X": 1}, cfg)[0], "block")

    def test_unknown_severity_exit2(self):
        cfg = dict(ha.DEFAULT_CONFIG)
        cfg["categories"] = {"X": {"severity": "maybe", "patterns": ["torch"]}}
        with self.assertRaises(SystemExit) as cm:
            ha.load_config_from_dict(cfg)
        self.assertEqual(cm.exception.code, 2)

    def test_bad_regex_exit2(self):
        cfg = dict(ha.DEFAULT_CONFIG)
        cfg["categories"] = {"X": {"severity": "warn", "patterns": ["([unclosed"]}}
        with self.assertRaises(SystemExit) as cm:
            ha.load_config_from_dict(cfg)
        self.assertEqual(cm.exception.code, 2)

    def test_resolver_finds_repo_config_from_subdir(self):
        cfg, src = ha.resolve_config(start_dir=os.path.join(ROOT, "tests"))
        self.assertIsNotNone(src)
        self.assertIn("honesty_patterns.json", src)

    def test_dynamic_exec_category_exists(self):
        # T12: exec/eval/__import__/importlib/compile — минимум WARN
        h = ha.audit_text("exec(\"__import__('torch')\")\n", ".py")
        self.assertTrue(any("DYNAMIC" in c for c in h))
        self.assertEqual(ha.severity(h)[0], "warn")


class TestExamplesControl(unittest.TestCase):
    """Позитивный контроль: examples/ воспроизводит expected_output.txt."""

    def test_examples_output_matches(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            try:
                ha.main(["honest_audit.py", "examples/"])
            except SystemExit:
                pass
        out = buf.getvalue()
        out = out.replace(ROOT + os.sep, "")
        exp_path = os.path.join(ROOT, "examples", "expected_output.txt")
        with open(exp_path, encoding="utf-8") as f:
            expected = f.read()
        # сравниваем смысловые строки (пути к правилам могут отличаться)
        self.assertIn("FRAUD: BACKPROP / gradient", out)
        self.assertIn("FRAUD: SOFTMAX", out)
        for line in expected.splitlines():
            if line.startswith(("FRAUD", "clean files", "rules:")):
                self.assertIn(line.strip(), out)

    def test_plain_torch_import_blocks(self):
        h = ha.audit_text("import torch\n", ".py")
        self.assertEqual(ha.severity(h)[0], "block")


if __name__ == "__main__":
    unittest.main()
