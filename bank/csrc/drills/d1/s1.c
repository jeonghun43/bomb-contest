/* d1/s1.c - drill D1 phase 1: compare with a global string.
 * Macros: D1_S1_TEXT */

void phase_1(char *input)
{
    if (strings_not_equal(input, D1_S1_TEXT))
        explode_bomb();
}
