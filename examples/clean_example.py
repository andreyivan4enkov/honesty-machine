# clean_example.py — honest local-dynamics memory: superposition storage,
# Hebbian reinforcement, no gradients, no softmax, no randomness in forward.
# Should pass the audit as CLEAN.

def store(W, f, d):
    return W + [[f[i] * f[j] / d for j in range(d)] for i in range(d)]

def reinforce(W, rec, d):
    # Local Hebb rule: what was retrieved gets stronger. No loss function.
    return store(W, rec, d)
