/*
 * bomb.h - Shared declarations for the defusing bomb.
 *
 * NOTE: This header is NOT distributed to contestants.
 */
#ifndef BOMB_H
#define BOMB_H

#include <stdio.h>

#define MAX_LINE_TOKEN 64

/* Input source: stdin, or the answer file given on the command line. */
extern FILE *infile;

/* ---- util.c ---- */
char       *read_line(void);
void        read_six_numbers(char *s, int *a);
const char *get_phase_input(int phase); /* 1-based; "" if not read yet */

unsigned    rotl32(unsigned v, int n);
unsigned    rotr32(unsigned v, int n);
unsigned    bit_reverse(unsigned v, int bits);
int         popcount32(unsigned v);

/* ---- notify.c (server mode, compiled only with -DNOTIFY) ---- */
#ifdef NOTIFY
/*
 * Send one request line to the record daemon and read one reply line.
 * Returns 0 on success (reply written to `reply`, NUL-terminated), -1 on any
 * connection, write, or read-timeout failure.
 */
int notify_request(const char *line, char *reply, size_t n);
#endif

/* ---- support.c ---- */
void initialize_bomb(void);
void explode_bomb(void);
void phase_defused(void);
void bomb_log(int phase, const char *result);

/* ---- phases.c ---- */
void phase_1(char *input);
void phase_2(char *input);
void phase_3(char *input);
void phase_4(char *input);
void phase_5(char *input);
void phase_6(char *input);
void secret_phase(void);

#endif /* BOMB_H */
