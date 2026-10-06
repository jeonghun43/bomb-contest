/* d2/s2.c - drill D2 phase 2: one number, compared once as unsigned and
 * once as signed.
 * Macros: D2_S2_UMIN (an unsigned bound near 2^32), D2_S2_HIGH (negative) */

void phase_2(char *input)
{
    int x;

    if (sscanf(input, "%d", &x) != 1)
        explode_bomb();
    if ((unsigned) x < D2_S2_UMIN)
        explode_bomb();
    if (x > D2_S2_HIGH)
        explode_bomb();
}
