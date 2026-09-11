/*
 * util.c - Input handling and bit helpers.
 *
 * NOT distributed to contestants.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "bomb.h"

#define MAX_LINE 80
#define MAX_PHASES 7 /* 6 public phases + secret phase */

static char input_strings[MAX_PHASES][MAX_LINE];
static int num_input_strings = 0;

/*
 * Read one line from the input source, strip the trailing newline, and keep a
 * copy so that phase_defused() can re-examine it later.
 */
char *read_line(void)
{
    char *p;
    size_t len;

    if (num_input_strings >= MAX_PHASES) {
        printf("Error: Too many input lines\n");
        exit(8);
    }

    p = fgets(input_strings[num_input_strings], MAX_LINE, infile);
    if (p == NULL) {
        if (infile == stdin)
            printf("Error: Premature EOF on stdin\n");
        else
            printf("Error: Premature EOF on input file\n");
        exit(8);
    }

    len = strlen(p);
    while (len > 0 && (p[len - 1] == '\n' || p[len - 1] == '\r'))
        p[--len] = '\0';

    if (len == MAX_LINE - 1) {
        printf("Error: Input line too long\n");
        explode_bomb();
    }

    num_input_strings++;
    return p;
}

/* 1-based accessor used by the defusal bookkeeping. */
const char *get_phase_input(int phase)
{
    if (phase < 1 || phase > num_input_strings)
        return "";
    return input_strings[phase - 1];
}

void read_six_numbers(char *s, int *a)
{
    int n;

    n = sscanf(s, "%d %d %d %d %d %d",
               &a[0], &a[1], &a[2], &a[3], &a[4], &a[5]);
    if (n != 6)
        explode_bomb();
}

unsigned rotl32(unsigned v, int n)
{
    n &= 31;
    return (v << n) | (v >> ((32 - n) & 31));
}

unsigned rotr32(unsigned v, int n)
{
    n &= 31;
    return (v >> n) | (v << ((32 - n) & 31));
}

/* Reverse the low `bits` bits of v. */
unsigned bit_reverse(unsigned v, int bits)
{
    unsigned r = 0;
    int i;

    for (i = 0; i < bits; i++)
        r = (r << 1) | ((v >> i) & 1u);

    return r;
}

int popcount32(unsigned v)
{
    int c = 0;

    while (v != 0) {
        c += (int) (v & 1u);
        v >>= 1;
    }

    return c;
}
