/* d9/s3.c - drill D9 phase 3: the expected number depends on a global the
 * runtime keeps, num_input_strings (lines read so far, blank lines not
 * counted).
 * Macros: D9_S3_K, D9_S3_C */

void phase_3(char *input)
{
    int x;

    if (sscanf(input, "%d", &x) != 1)
        explode_bomb();
    if (x != num_input_strings * D9_S3_K + D9_S3_C)
        explode_bomb();
}
