/* d1/s3.c - drill D1 phase 3: the input's length picks the string it must
 * equal from a table of pointers.
 * Macros: D1_S3_WORDS (8 strings) */

static char *d1_words[] = D1_S3_WORDS;

void phase_3(char *input)
{
    int n = string_length(input);

    if (n < 2 || n > 9)
        explode_bomb();
    if (strings_not_equal(input, d1_words[n - 2]))
        explode_bomb();
}
