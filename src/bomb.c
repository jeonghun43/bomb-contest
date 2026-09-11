/***************************************************************************
 * bomb.c - The main driver of the binary bomb.
 *
 * This file is handed to contestants together with the compiled binary.
 * It shows the order in which the phases run and nothing else: every
 * defusing condition lives in code you do not get to read.
 *
 * Usage:
 *     ./bomb                  read answers from stdin, one line per phase
 *     ./bomb answers.txt      read answers from a file, one line per phase
 ***************************************************************************/
#include <stdio.h>
#include <stdlib.h>

#include "bomb.h"

FILE *infile;

int main(int argc, char *argv[])
{
    char *input;

    if (argc == 1) {
        infile = stdin;
    } else if (argc == 2) {
        infile = fopen(argv[1], "r");
        if (infile == NULL) {
            printf("%s: Error: Couldn't open %s\n", argv[0], argv[1]);
            exit(8);
        }
    } else {
        printf("Usage: %s [<answer_file>]\n", argv[0]);
        exit(8);
    }

    initialize_bomb();

    printf("Welcome to this little bomb. It has six phases.\n");
    printf("Give me a line of input for each one, or I will blow up.\n");

    input = read_line();
    phase_1(input);
    phase_defused();
    printf("Phase 1 defused. Five to go.\n");

    input = read_line();
    phase_2(input);
    phase_defused();
    printf("That's number 2. Keep going.\n");

    input = read_line();
    phase_3(input);
    phase_defused();
    printf("Halfway there!\n");

    input = read_line();
    phase_4(input);
    phase_defused();
    printf("So you got that one. Try this one.\n");

    input = read_line();
    phase_5(input);
    phase_defused();
    printf("Good work! On to the last one.\n");

    input = read_line();
    phase_6(input);
    phase_defused();

    printf("Congratulations! You've defused the bomb!\n");
    return 0;
}
