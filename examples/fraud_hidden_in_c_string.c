/* fraud_hidden_in_c_string.c — the real case of 2026-11-18:
 * a "renderer" that hides a full GPU backprop training pass inside a C string
 * (shader/kernel source). Scanning C string literals is what catches this. */
#include <stdio.h>

const char *kernel_source =
    "__kernel void pass2_head_and_grad(__global float *w, __global const float *err) {"
    "  int i = get_global_id(0);"
    "  float learning_rate = 0.001f;"
    "  w[i] -= learning_rate * err[i];   /* gradient descent step */"
    "}";

int main(void) {
    puts(kernel_source);
    return 0;
}
