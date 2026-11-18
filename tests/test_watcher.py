# T0: watcher tests — T13 (argparse, значения не теряются) и T3 (паритет конфига с CLI).
import json, os, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import honest_audit as ha
import honest_audit_watch as hw


class TestWatcherArgs(unittest.TestCase):
    def test_interval_last_without_value_clean_error(self):
        with self.assertRaises(SystemExit) as cm:
            hw.parse_args(["somepath", "--interval"])
        self.assertEqual(cm.exception.code, 2)  # argparse: внятная ошибка, не IndexError

    def test_paths_not_eaten_by_option_values(self):
        a = hw.parse_args(["proj/src", "--interval", "5", "--log", "w.log"])
        self.assertEqual(a.paths, ["proj/src"])
        self.assertEqual(a.interval, 5.0)
        self.assertEqual(a.log, "w.log")

    def test_path_looking_like_number_kept(self):
        a = hw.parse_args(["3.0"])
        self.assertEqual(a.paths, ["3.0"])

    def test_once_flag(self):
        self.assertTrue(hw.parse_args(["--once"]).once)


class TestCliWatcherConfigParity(unittest.TestCase):
    """T3: одинаковый конфиг -> одинаковые вердикты у CLI и watcher."""

    def test_custom_config_applied_identically(self):
        custom = {
            "skip_dirs": [], "skip_dir_suffixes": [],
            "file_extensions": [".py"],
            "categories": {
                "NETWORK IN LIB": {"severity": "block",
                                   "why": "library must not do network",
                                   "patterns": ["\\brequests\\.", "\\bhttpx\\b"]}
            },
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(custom, f)
            cfg_path = f.name
        try:
            cfg, src = ha.resolve_config(cli_path=cfg_path)      # путь CLI
            self.assertEqual(src, cfg_path)
            cfg2, _ = ha.resolve_config(cli_path=cfg_path)       # путь watcher — тот же резолвер
            net = ha.audit_text("import httpx\nhttpx.get('http://x')\n", ".py", cfg)
            tor = ha.audit_text("import torch\n", ".py", cfg)    # torch УБРАН из правил
            self.assertEqual(ha.severity(net, cfg)[0], "block")
            self.assertEqual(ha.severity(tor, cfg)[0], "ok")
            self.assertEqual(ha.severity(net, cfg2)[0], "block")
        finally:
            os.unlink(cfg_path)


if __name__ == "__main__":
    unittest.main()
