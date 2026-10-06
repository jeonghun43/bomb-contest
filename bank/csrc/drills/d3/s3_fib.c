/* d3/s3_fib.c - drill D3 phase 3: the first value is fixed, the second is
 * free, and from then on each is the sum of the two before it.
 * Macros: D3_S3_A */

void phase_3(char *input)
{
    int i;
    int numbers[6];

    read_six_numbers(input, numbers);
    if (numbers[0] != D3_S3_A)
        explode_bomb();
    for (i = 2; i < 6; i++) {
        if (numbers[i] != numbers[i - 1] + numbers[i - 2])
            explode_bomb();
    }
}
