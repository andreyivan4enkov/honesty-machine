# fraud_fake_block_comment.py — bypass caught 2026-11-18 (Qwen audit, PoC3):
# fake C-style comment markers inside Python strings made the old stripper
# erase everything between them (re.S across the whole file).
A = "/*"
import torch
B = "*/"
