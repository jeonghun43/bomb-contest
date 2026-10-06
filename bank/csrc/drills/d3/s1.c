/* d3/s1.c - drill D3 phase 1: six numbers, each twice the one before.
 * Macros: D3_S1_FIRST */

void phase_1(char *input)
{
    int i;
    int numbers[6];

    read_six_numbers(input, numbers);
    if (numbers[0] != D3_S1_FIRST)
        explode_bomb();
    for (i = 1; i < 6; i++) {
        if (numbers[i] != numbers[i - 1] * 2)
            explode_bomb();
    }
}
