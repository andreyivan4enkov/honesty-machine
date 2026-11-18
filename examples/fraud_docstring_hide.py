# fraud_docstring_hide.py — bypass caught 2026-11-18 (Qwen audit, PoC2):
# the closing line of a triple-quoted string carried real code, and the old
# post-line stripper dropped the whole line. Tokenizer stripping keeps it.
x = """
looks like a harmless docstring
"""; import torch
