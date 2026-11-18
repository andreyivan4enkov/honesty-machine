# T0: E2E tests of the pre-commit hook (T2 staged-vs-worktree, T6 renames/spaces,
# T7 fail-closed + chaining). Each test builds a temp repo and installs the hook.
import os, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sh(cmd, cwd, check=True):
    r = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise AssertionError(f"cmd failed: {cmd}\n{r.stdout}\n{r.stderr}")
    return r


class HookRepo:
    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix="hm_hook_test_")
        sh("git init -q", self.dir)
        sh('git config user.email t@t.t && git config user.name t', self.dir)
        for f in ("honest_audit.py", "honesty_patterns.json", "install_precommit.sh"):
            shutil.copy(os.path.join(ROOT, f), self.dir)
        sh("bash install_precommit.sh", self.dir)

    def write(self, name, content):
        with open(os.path.join(self.dir, name), "w", encoding="utf-8") as f:
            f.write(content)

    def commit(self, msg="x"):
        return sh("git add -A && git commit -m commitmsg", self.dir, check=False)

    def cleanup(self):
        shutil.rmtree(self.dir, ignore_errors=True)


class TestHookE2E(unittest.TestCase):
    def setUp(self):
        self.r = HookRepo()

    def tearDown(self):
        self.r.cleanup()

    def test_t2_staged_fraud_blocked_even_if_worktree_clean(self):
        self.r.write("evil.py", "import torch\n")
        sh("git add evil.py", self.r.dir)
        self.r.write("evil.py", "# clean now\n")          # worktree чист, staged — подлог
        res = self.r.commit()
        self.assertNotEqual(res.returncode, 0, "staged-подлог обязан блокироваться")

    def test_t2_clean_staged_passes_even_if_worktree_dirty(self):
        self.r.write("ok.py", "x = 1\n")
        sh("git add ok.py", self.r.dir)
        self.r.write("ok.py", "import torch\n")           # подлог только в worktree
        res = self.r.commit()
        self.assertEqual(res.returncode, 0, f"чистый staged обязан проходить:\n{res.stdout}{res.stderr}")

    def test_t7_missing_auditor_blocks(self):
        os.remove(os.path.join(self.r.dir, "honest_audit.py"))
        self.r.write("ok.py", "x = 1\n")
        res = self.r.commit()
        self.assertNotEqual(res.returncode, 0, "нет аудитора -> fail-closed")

    def test_t7_existing_hook_chained(self):
        hook = os.path.join(self.r.dir, ".git", "hooks", "pre-commit")
        with open(hook, "w") as f:
            f.write('#!/bin/bash\necho witness >> witness.log\n')
        os.chmod(hook, 0o755)
        sh("bash install_precommit.sh", self.r.dir)       # переустановка поверх
        self.r.write("ok.py", "x = 1\n")
        res = self.r.commit()
        self.assertEqual(res.returncode, 0)
        self.assertTrue(os.path.exists(os.path.join(self.r.dir, "witness.log")),
                        "прежний хук обязан исполняться (чейнинг)")

    def test_t6_filename_with_spaces_audited(self):
        self.r.write("my file.py", "import torch\n")
        res = self.r.commit()
        self.assertNotEqual(res.returncode, 0, "имя с пробелом обязано аудироваться")

    def test_t6_rename_with_edit_audited(self):
        self.r.write("old.py", "x = 1\n")
        self.r.commit("base")
        sh("git mv old.py new.py", self.r.dir)
        self.r.write("new.py", "import torch\n")
        sh("git add new.py", self.r.dir)
        res = sh("git commit -m rename", self.r.dir, check=False)
        self.assertNotEqual(res.returncode, 0, "rename+правка с подлогом обязана блокироваться")

    def test_t8_broken_config_blocks_commit(self):
        self.r.write("honesty_patterns.json", "{ not json !!!")
        self.r.write("ok.py", "x = 1\n")
        res = self.r.commit()
        self.assertNotEqual(res.returncode, 0, "битый конфиг -> fail-closed")


if __name__ == "__main__":
    unittest.main()
