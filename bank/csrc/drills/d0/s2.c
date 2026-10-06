/* d0/s2.c - drill D0 phase 2: the expected number is computed at run time
 * from a global table, so it only exists in a register at the compare.
 * Macros: D0_S2_TAB (4 ints) */

int d0_tab[4] = D0_S2_TAB;

void phase_2(char *input)
{
    int x;

    if (sscanf(input, "%d", &x) != 1)
        explode_bomb();
    if (x != d0_tab[0] * d0_tab[1] + d0_tab[2] - d0_tab[3])
        explode_bomb();
}
