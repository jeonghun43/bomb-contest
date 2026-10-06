/* d6/s3.c - drill D6 phase 3: follow "next index" links through a 16-entry
 * array until index 15; the number of steps must equal D6_S3_STEPS. The
 * array is a single 16-cycle, so every start reaches 15.
 * Macros: D6_S3_NEXT (16 ints), D6_S3_STEPS */

void phase_3(char *input)
{
    static int d6_next[] = D6_S3_NEXT;
    int a, count = 0;

    if (sscanf(input, "%d", &a) != 1)
        explode_bomb();
    a = a & 0xf;
    while (a != 15) {
        a = d6_next[a];
        count++;
    }
    if (count != D6_S3_STEPS)
        explode_bomb();
}
