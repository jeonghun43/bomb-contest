/*
 * phases_rt.c - Trivial phases for testing the runtime (tools/runtime_check.sh).
 *
 * Not a puzzle and never shipped. The answers are "one", "two", "three",
 * "4 4", "five", "six" and, for the secret phase, "seven"; with RT_DRILL only
 * the first three phases exist. Phase 4 parses "%d %d" so its line can carry
 * the secret token the way the CMU bomb's phase 4 line does.
 */
#include <stdio.h>
#include <stdlib.h>
#include "bombdata.h"
#include "support.h"
#include "phases.h"

void phase_1(char *input)
{
    if (strings_not_equal(input, "one"))
        explode_bomb();
}

void phase_2(char *input)
{
    if (strings_not_equal(input, "two"))
        explode_bomb();
}

void phase_3(char *input)
{
    if (strings_not_equal(input, "three"))
        explode_bomb();
}

#ifndef RT_DRILL
void phase_4(char *input)
{
    int a, b;

    if (sscanf(input, "%d %d", &a, &b) != 2 || a != 4 || b != 4)
        explode_bomb();
}

void phase_5(char *input)
{
    if (strings_not_equal(input, "five"))
        explode_bomb();
}

void phase_6(char *input)
{
    if (strings_not_equal(input, "six"))
        explode_bomb();
}

void secret_phase()
{
    char *input = read_line();

    if (strings_not_equal(input, "seven"))
        explode_bomb();
    printf("Wow! You've defused the secret stage!\n");
    phase_defused();
}
#endif
