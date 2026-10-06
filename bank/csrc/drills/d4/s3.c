/* d4/s3.c - drill D4 phase 3: a sparse switch (too spread out for a table,
 * so the compiler emits compares) where two cases fall through.
 * Macros: D4_S3_K0..K3 (case keys), D4_S3_A0..A3 */

void phase_3(char *input)
{
    int key, val, x = 0;

    if (sscanf(input, "%d %d", &key, &val) != 2)
        explode_bomb();

    switch (key) {
    case D4_S3_K0:
        x += D4_S3_A0;
        /* fall through */
    case D4_S3_K1:
        x += D4_S3_A1;
        break;
    case D4_S3_K2:
        x += D4_S3_A2;
        /* fall through */
    case D4_S3_K3:
        x += D4_S3_A3;
        break;
    default:
        explode_bomb();
    }
    if (x != val)
        explode_bomb();
}
