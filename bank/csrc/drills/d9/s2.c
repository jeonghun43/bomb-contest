/* d9/s2.c - drill D9 phase 2: two numbers. This line is the one
 * phase_defused() re-reads with "%d %d %s" for the secret token.
 * Macros: D9_S2_A, D9_S2_K */

void phase_2(char *input)
{
    int a, b;

    if (sscanf(input, "%d %d", &a, &b) != 2)
        explode_bomb();
    if (a != D9_S2_A || b != a * D9_S2_K)
        explode_bomb();
}
