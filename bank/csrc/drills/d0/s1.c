/* d0/s1.c - drill D0 phase 1: the answer sits in .rodata.
 * Macros: D0_S1_WORD */

void phase_1(char *input)
{
    if (strings_not_equal(input, D0_S1_WORD))
        explode_bomb();
}
