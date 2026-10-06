/* d3/s3_collatz.c - drill D3 phase 3: the next value depends on whether the
 * previous one is odd (3n+1) or even (n/2).
 * Macros: D3_S3_FIRST */

void phase_3(char *input)
{
    int i, prev, want;
    int numbers[6];

    read_six_numbers(input, numbers);
    if (numbers[0] != D3_S3_FIRST)
        explode_bomb();
    for (i = 1; i < 6; i++) {
        prev = numbers[i - 1];
        if (prev & 1)
            want = 3 * prev + 1;
        else
            want = prev / 2;
        if (numbers[i] != want)
            explode_bomb();
    }
}
