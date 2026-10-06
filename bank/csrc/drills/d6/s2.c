/* d6/s2.c - drill D6 phase 2: the low four bits of each character index a
 * table of ints; the sum must equal D6_S2_SUM.
 * Macros: D6_S2_VALS (16 ints), D6_S2_LEN, D6_S2_SUM */

void phase_2(char *input)
{
    static int d6_vals[] = D6_S2_VALS;
    int i, sum = 0;

    if (string_length(input) != D6_S2_LEN)
        explode_bomb();
    for (i = 0; i < D6_S2_LEN; i++)
        sum += d6_vals[input[i] & 0xf];
    if (sum != D6_S2_SUM)
        explode_bomb();
}
