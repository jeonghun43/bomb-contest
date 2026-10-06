/*
 * support.h - Bomb runtime shared by every bomb in the practice bank.
 *
 * NOT distributed to students. The functions here reproduce the original CMU
 * bomb's support code instruction for instruction when built with the
 * original toolchain (specs/003-practice-bank/research.md section 6).
 */
#ifndef SUPPORT_H
#define SUPPORT_H

#include <stdio.h>

#define MAX_STRINGS 20  /* input lines the bomb keeps */
#define MAX_LINE    80  /* fgets buffer per line */

extern FILE *infile;    /* defined in bomb.c */
extern char input_strings[MAX_STRINGS][MAX_LINE];
extern int num_input_strings;

void initialize_bomb(void);
void initialize_bomb_solve(void);
char *read_line(void);
void phase_defused(void);
void explode_bomb(void);
void invalid_phase(char *s);
void read_six_numbers(char *input, int *numbers);
int string_length(char *aString);
int strings_not_equal(char *string1, char *string2);

#endif /* SUPPORT_H */
