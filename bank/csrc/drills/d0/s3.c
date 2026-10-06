/* d0/s3.c - drill D0 phase 3: the answer is decoded at run time into a
 * global buffer; `strings bomb` will not show it. (A global, not a stack
 * array, so no canary code gets in the way.)
 * Macros: D0_S3_ENC (bytes), D0_S3_LEN, D0_S3_KEY */

static char d0_enc[] = D0_S3_ENC;
char d0_buf[16];

void phase_3(char *input)
{
    int i;

    for (i = 0; i < D0_S3_LEN; i++)
        d0_buf[i] = d0_enc[i] ^ D0_S3_KEY;
    d0_buf[D0_S3_LEN] = '\0';
    if (strings_not_equal(input, d0_buf))
        explode_bomb();
}
