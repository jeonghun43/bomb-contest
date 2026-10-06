/* d2/s3.c - drill D2 phase 3: unsigned division and remainder by a constant,
 * which the compiler turns into a multiply by a "magic number" and shifts.
 * Unsigned, so no sign-correction code.
 * Macros: D2_S3_DIV, D2_S3_Q, D2_S3_R */

void phase_3(char *input)
{
    int x;

    if (sscanf(input, "%d", &x) != 1)
        explode_bomb();
    if ((unsigned) x / D2_S3_DIV != D2_S3_Q)
        explode_bomb();
    if ((unsigned) x % D2_S3_DIV != D2_S3_R)
        explode_bomb();
}
