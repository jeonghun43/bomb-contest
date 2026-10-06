/***************************************************************************
 * bomb.c - main routine of your binary bomb
 *
 * You get this file together with the compiled bomb. It shows how the bomb
 * runs - one input line per phase, in order - and nothing more. The code
 * that decides whether a line defuses a phase is not in here; you will have
 * to find it in the binary.
 *
 * Usage:
 *     ./bomb                  read every answer from standard input
 *     ./bomb answers.txt      read answers from the file; when the file runs
 *                             out, continue from standard input
 *
 * Keep each solved answer on its own line in answers.txt, and you never have
 * to type it again.
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

    printf("Welcome to my fiendish little bomb. You have 6 phases with\n");
    printf("which to blow yourself up. Have a nice day!\n");

    /* Each phase: read a line, check it, record the defusal. */
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
    printf("Halfway there!\n");

    input = read_line();
    phase_4(input);
    phase_defused();
    printf("So you got that one.  Try this one.\n");

    input = read_line();
    phase_5(input);
    phase_defused();
    printf("Good work!  On to the next...\n");

    input = read_line();
    phase_6(input);
    phase_defused();

    /* Six phases down. Is that really everything? */

    return 0;
}
