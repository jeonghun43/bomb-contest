/* d1/s2.c - drill D1 phase 2: a length check, then a compare with a string
 * the compiler assembles on the stack from 8-byte immediates (movabs).
 * Macros: D1_S2_WORD, D1_S2_LEN */

void phase_2(char *input)
{
    char key[] = D1_S2_WORD;

    if (string_length(input) != D1_S2_LEN)
        explode_bomb();
    if (strings_not_equal(input, key))
        explode_bomb();
}
