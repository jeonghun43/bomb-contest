/* d9/s1.c - drill D9 phase 1: a plain string compare (warm-up).
 * Macros: D9_S1_WORD */

void phase_1(char *input)
{
    if (strings_not_equal(input, D9_S1_WORD))
        explode_bomb();
}
