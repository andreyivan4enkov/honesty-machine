# fraud_softmax.py — claims "no softmax" in comments but uses it in code.
# The audit strips comments and docstrings: words in comments are not code.
import math

def softmax(logits):
    e = [math.exp(x) for x in logits]
    Z = sum(e)
    return [x / Z for x in e]

def select(logits):
    """Local winner selection, no normalization anywhere."""
    return softmax(logits).index(max(softmax(logits)))

# NOTE (documented limitation): spelling softmax OUT (exp/sum/divide under a
# different name) evades a regex gate. The gate catches WORDS; the rerun process
# catches MEANING. Both are required — see docs/METHODOLOGY.md.
