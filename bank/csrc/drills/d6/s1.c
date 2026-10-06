/* d6/s1.c - drill D6 phase 1: the low four bits of each character index a
 * 16-letter table; each looked-up letter must match the target, one by one.
 * (The assignment's phase 5 builds the letters into a stack buffer and
 * compares with strings_not_equal; the indexing is the same.)
 * Macros: D6_S1_ARRAY (16 chars), D6_S1_TARGET (6 chars) */

void phase_1(char *input)
{
    static char d6_letters[] = D6_S1_ARRAY;
    int i;

    if (string_length(input) != 6)
        explode_bomb();
    for (i = 0; i < 6; i++) {
        if (d6_letters[input[i] & 0xf] != D6_S1_TARGET[i])
            explode_bomb();
    }
}
