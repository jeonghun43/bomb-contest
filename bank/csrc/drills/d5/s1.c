/* d5/s1.c - drill D5 phase 1: a helper taking three arguments; the input is
 * passed as the second one.
 * Macros: D5_S1_M, D5_S1_S, D5_S1_A, D5_S1_C, D5_S1_T
 *
 * noinline: GCC 4.8 -O1 otherwise inlines mix3 and, with two constant
 * arguments, folds the whole call into one compare - and the point of the
 * phase (reading %edi/%esi/%edx at a call) disappears. */

__attribute__((noinline))
int mix3(int a, int b, int c)
{
    return a * D5_S1_M - b + (c << D5_S1_S);
}

void phase_1(char *input)
{
    int x;

    if (sscanf(input, "%d", &x) != 1)
        explode_bomb();
    if (mix3(D5_S1_A, x, D5_S1_C) != D5_S1_T)
        explode_bomb();
}
