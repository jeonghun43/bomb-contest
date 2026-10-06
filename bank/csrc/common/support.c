/*
 * support.c - Bomb runtime: input, explosion, defusal bookkeeping.
 *
 * NOT distributed to students.
 *
 * Offline builds of this file match the original CMU bomb's support code
 * instruction for instruction (specs/003-practice-bank AC-05). Keep it that
 * way: before changing any statement here, run `make calib` and
 * tools/runtime_check.sh. Several shapes are load-bearing even though they
 * look arbitrary, for example `isspace(*input++)` in blank_line() and the
 * missing parameter list on skip().
 *
 * Server builds (-DNOTIFY) add reporting the way the original's course
 * version does: initialize_bomb() asks the daemon whether the bomb may run,
 * explode_bomb() and phase_defused() report through send_msg(). Phase
 * numbers are num_input_strings, i.e. real (non-blank) input lines read.
 *
 * Per-bomb settings come from the generated bombdata.h:
 *   NUM_PHASES   phases before the bomb counts as defused (CMU 6, drills 3)
 *   HAS_SECRET   1 if phase_defused() can open the secret phase
 *   SECRET_LINE  0-based input line re-read for the secret token (CMU 3)
 *   SECRET_WORD  the token that opens it
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <signal.h>
#include <unistd.h>

#include "bombdata.h"
#include "support.h"
#include "phases.h"
#ifdef NOTIFY
#include "driverlib.h"
#endif

#ifndef NUM_PHASES
#define NUM_PHASES 6
#endif
#ifndef HAS_SECRET
#define HAS_SECRET 0
#endif
#ifndef SECRET_LINE
#define SECRET_LINE 3
#endif

char input_strings[MAX_STRINGS][MAX_LINE];
int num_input_strings = 0;

static void sig_handler(int sig)
{
    printf("So you think you can stop the bomb with ctrl-c, do you?\n");
    sleep(3);
    printf("Well...");
    fflush(stdout);
    sleep(1);
    printf("OK. :-)\n");
    exit(16);
}

void invalid_phase(char *s)
{
    printf("Invalid phase%s\n", s);
    exit(8);
}

int string_length(char *aString)
{
    int length;
    char *ptr;

    ptr = aString;
    length = 0;
    while (*ptr != 0) {
        ptr++;
        length++;
    }
    return length;
}

int strings_not_equal(char *string1, char *string2)
{
    char *p, *q;

    if (string_length(string1) != string_length(string2))
        return 1;
    p = string1;
    q = string2;
    while (*p != 0) {
        if (*p != *q)
            return 1;
        p++;
        q++;
    }
    return 0;
}

#ifdef NOTIFY
/*
 * Report the line just read. A defusal that cannot be delivered must not be
 * lost silently, so the bomb stops and asks for a re-run; an explosion that
 * cannot be delivered only warns, since the bomb is ending anyway.
 */
static void send_msg(int defused)
{
    char hex[2 * MAX_LINE + 1];
    char result[2 * MAX_LINE + 64];
    char status_msg[SUBMITR_MAXBUF];
    char *in;
    int i;

    in = input_strings[num_input_strings - 1];
    for (i = 0; i < MAX_LINE && in[i] != '\0'; i++)
        sprintf(hex + 2 * i, "%02x", (unsigned char) in[i]);
    hex[2 * i] = '\0';

    sprintf(result, "%s %d %s", defused ? "defused" : "exploded",
            num_input_strings, hex);

    if (driver_post(BOMB_ID, result, 0, status_msg) < 0) {
        if (defused) {
            printf("\nCould not reach the record server. "
                   "Nothing was lost - please run the bomb again.\n");
            exit(9);
        }
        printf("(warning: this explosion could not be recorded)\n");
    }
}
#endif

void initialize_bomb(void)
{
#ifdef NOTIFY
    char status_msg[SUBMITR_MAXBUF];
#endif

    signal(SIGINT, sig_handler);

#ifdef NOTIFY
    if (init_driver(status_msg) < 0) {
        printf("%s\n", status_msg);
        exit(9);
    }
#endif
}

void initialize_bomb_solve(void)
{
}

int blank_line(char *input)
{
    while (*input != 0) {
        if (!isspace(*input++))
            return 0;
    }
    return 1;
}

/* No parameter list on purpose: the original's call site loads %eax = 0. */
char *skip()
{
    char *p;

    while (1) {
        p = fgets(input_strings[num_input_strings], MAX_LINE, infile);
        if ((p == NULL) || (!blank_line(p)))
            return p;
    }
}

void explode_bomb(void)
{
    printf("\nBOOM!!!\n");
    printf("The bomb has blown up.\n");
#ifdef NOTIFY
    send_msg(0);
#endif
    exit(8);
}

void read_six_numbers(char *input, int *numbers)
{
    int numScanned = sscanf(input, "%d %d %d %d %d %d",
                            &numbers[0], &numbers[1], &numbers[2],
                            &numbers[3], &numbers[4], &numbers[5]);
    if (numScanned < 6)
        explode_bomb();
}

/*
 * Read the next non-blank line. When an input file runs out, carry on from
 * stdin, so students can keep solved answers in a file and type the rest.
 * The last character is dropped unconditionally (it is normally '\n'), as in
 * the original.
 */
char *read_line(void)
{
    int len;
    char *str;

    str = skip();
    if (str == NULL) {
        if (infile == stdin) {
            printf("Error: Premature EOF on stdin\n");
            exit(8);
        }
        if (getenv("GRADE_BOMB"))
            exit(0);
        infile = stdin;
        str = skip();
        if (str == NULL) {
            printf("Error: Premature EOF on stdin\n");
            exit(0);
        }
    }

    len = strlen(input_strings[num_input_strings]);
    if (len >= MAX_LINE - 1) {
        printf("Error: Input line too long\n");
        strcpy(input_strings[num_input_strings++], "***truncated***");
        explode_bomb();
    }

    input_strings[num_input_strings][len - 1] = '\0';
    return input_strings[num_input_strings++];
}

void phase_defused(void)
{
#if HAS_SECRET
    char string[80];
    int a, b;
#endif

#ifdef NOTIFY
    send_msg(1);
#endif

    if (num_input_strings == NUM_PHASES) {
#if HAS_SECRET
        if (sscanf(input_strings[SECRET_LINE], "%d %d %s", &a, &b, string) == 3) {
            if (strings_not_equal(string, SECRET_WORD) == 0) {
                printf("Curses, you've found the secret phase!\n");
                printf("But finding it and solving it are quite different...\n");
                secret_phase();
            }
        }
#endif
        printf("Congratulations! You've defused the bomb!\n");
    }
}
