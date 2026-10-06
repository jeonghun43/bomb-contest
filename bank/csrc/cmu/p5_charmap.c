/* p5_charmap.c - phase 5: six characters; the low four bits of each pick a
 * letter from a 16-entry table, and the letters must spell P5_TARGET.
 * Macros: P5_ARRAY (16 chars), P5_TARGET (6 chars)
 *
 * The table is a static local, as in the original, so its symbol reads
 * array.NNNN in the binary. */

void phase_5(char *input)
{
    static char array[] = P5_ARRAY;
    int i;
    char buf[7];

    if (string_length(input) != 6)
        explode_bomb();
    for (i = 0; i < 6; i++)
        buf[i] = array[input[i] & 0xf];
    buf[6] = '\0';
    if (strings_not_equal(buf, P5_TARGET) != 0)
        explode_bomb();
}
