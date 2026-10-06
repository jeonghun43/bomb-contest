/* p2_double.c - phase 2: six numbers, each twice the one before.
 * Macros: P2_FIRST */

void phase_2(char *input)
{
    int i;
    int numbers[6];

    read_six_numbers(input, numbers);
    if (numbers[0] != P2_FIRST)
        explode_bomb();
    for (i = 1; i < 6; i++) {
        if (numbers[i] != numbers[i - 1] * 2)
            explode_bomb();
    }
}
