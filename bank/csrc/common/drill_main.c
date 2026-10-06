/***************************************************************************
 * bomb.c - main routine of drill @DRILL_ID@: @DRILL_TITLE@
 *
 * A drill is a small bomb that practises one idea from the real Bomb Lab.
 * It runs exactly like the full bomb - same input handling, same explode
 * and defuse routines, same habits in gdb (break phase_2, break
 * explode_bomb, ...) - but it has three phases instead of six:
 *
 *     phase 1   the idea in its plainest form
 *     phase 2   the same idea in a different shape
 *     phase 3   the idea combined with something you have already seen
 *
 * Usage:
 *     ./bomb                  read every answer from standard input
 *     ./bomb answers.txt      read answers from the file; when the file runs
 *                             out, continue from standard input
 *
 * Defuse a phase and its write-up opens: run `bomblab notes` on the server.
 ***************************************************************************/

#include <stdio.h>
#include <stdlib.h>
#include "support.h"
#include "phases.h"

/* Where the input lines come from: standard input or the answer file. */
FILE *infile;

int main(int argc, char *argv[])
{
    char *input;

    /* No arguments: read the answers from standard input. */
    if (argc == 1) {
        infile = stdin;
    }

    /* One argument: read from that file until it ends, then from stdin. */
    else if (argc == 2) {
        if (!(infile = fopen(argv[1], "r"))) {
            printf("%s: Error: Couldn't open %s\n", argv[0], argv[1]);
            exit(8);
        }
    }

    /* Anything else is a usage error. */
    else {
        printf("Usage: %s [<input_file>]\n", argv[0]);
        exit(8);
    }

    initialize_bomb();

    printf("Welcome to drill @DRILL_ID@: @DRILL_TITLE@.\n");
    printf("It has 3 phases. Each one practises the same idea.\n");

    input = read_line();
    phase_1(input);
    phase_defused();
    printf("Phase 1 defused. How about the next one?\n");

    input = read_line();
    phase_2(input);
    phase_defused();
    printf("That's number 2.  Keep going!\n");

    input = read_line();
    phase_3(input);
    phase_defused();

    return 0;
}
