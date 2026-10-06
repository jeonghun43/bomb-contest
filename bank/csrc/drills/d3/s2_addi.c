/* d3/s2_addi.c - drill D3 phase 2: a[i] = a[i-1] + i.
 * Macros: D3_S2_FIRST */

void phase_2(char *input)
{
    int i;
    int numbers[6];

    read_six_numbers(input, numbers);
    if (numbers[0] != D3_S2_FIRST)
        explode_bomb();
    for (i = 1; i < 6; i++) {
        if (numbers[i] != numbers[i - 1] + i)
            explode_bomb();
    }
}
