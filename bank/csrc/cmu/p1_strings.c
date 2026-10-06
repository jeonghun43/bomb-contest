/* p1_strings.c - phase 1: compare the line with a fixed sentence.
 * Macros: P1_STRING */

void phase_1(char *input)
{
    if (strings_not_equal(input, P1_STRING))
        explode_bomb();
}
