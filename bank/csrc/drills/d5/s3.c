/* d5/s3.c - drill D5 phase 3: a function that calls itself twice.
 * Macros: D5_S3_BASE, D5_S3_T */

int func5(int n)
{
    if (n < 2)
        return n + D5_S3_BASE;
    return func5(n - 1) + func5(n - 2);
}

void phase_3(char *input)
{
    int n;

    if (sscanf(input, "%d", &n) != 1)
        explode_bomb();
    if (n < 0 || n > 20)
        explode_bomb();
    if (func5(n) != D5_S3_T)
        explode_bomb();
}
