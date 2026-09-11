/*
 * support.c - Bomb bookkeeping: explosion, defusal, logging, secret trigger.
 *
 * NOT distributed to contestants.
 *
 * Two build modes share this file:
 *   offline (default)  - append events to a local bomb.log
 *   server  (-DNOTIFY) - report events to the record daemon; identity is the
 *                        connecting uid, established by the daemon, so nothing
 *                        here proves who we are.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "bomb.h"
#include "bombdata.h"

#define SECRET_TRIGGER_PHASE 4
#define NUM_PUBLIC_PHASES 6

static int num_defused = 0;
static int secret_armed = 0;

#ifdef NOTIFY

/* ---- server mode ------------------------------------------------------- */

#define REPLY_MAX 128

static void hex_encode(const char *in, char *out, size_t out_sz)
{
    static const char digits[] = "0123456789abcdef";
    size_t i = 0;

    /* out must hold 2*strlen(in)+1; the caller sizes it for an 80-char line. */
    for (; in[i] != '\0' && (2 * i + 2) < out_sz; i++) {
        unsigned char c = (unsigned char) in[i];
        out[2 * i] = digits[c >> 4];
        out[2 * i + 1] = digits[c & 0xF];
    }
    out[2 * i] = '\0';
}

/* Report one event. `result` is "DEFUSED" or "EXPLODED"; phase is 1..7. */
void bomb_log(int phase, const char *result)
{
    char hexin[2 * MAX_LINE_TOKEN + 2 * 80 + 4];
    char line[512];
    char reply[REPLY_MAX];
    const char *kind;

    kind = (strcmp(result, "DEFUSED") == 0) ? "defused" : "exploded";
    hex_encode(get_phase_input(phase), hexin, sizeof(hexin));

    snprintf(line, sizeof(line), "EVENT %s %s %d %s\n",
             BOMB_ID, kind, phase, hexin);

    if (notify_request(line, reply, sizeof(reply)) != 0) {
        /*
         * A defusal we cannot record must not be silently lost: stop and let
         * the contestant re-run. An explosion that we cannot record is only a
         * warning - the bomb is ending anyway.
         */
        if (strcmp(kind, "defused") == 0) {
            printf("\nCould not reach the record server. "
                   "Nothing was lost - please run the bomb again.\n");
            fflush(stdout);
            exit(9);
        }
        printf("(warning: this explosion could not be recorded)\n");
    }
}

void initialize_bomb(void)
{
    char line[128];
    char reply[REPLY_MAX];

    snprintf(line, sizeof(line), "HELLO %s\n", BOMB_ID);

    if (notify_request(line, reply, sizeof(reply)) != 0) {
        printf("Could not reach the record server. "
               "Ask a proctor for help.\n");
        exit(9);
    }

    if (strncmp(reply, "OK", 2) != 0) {
        /* CLOSED (before start / after end) or ERR (unknown bomb). */
        char *nl = strchr(reply, '\n');
        if (nl)
            *nl = '\0';
        printf("This bomb is not active right now: %s\n", reply);
        exit(9);
    }
}

#else /* offline mode */

#define LOG_FILE "bomb.log"

void bomb_log(int phase, const char *result)
{
    FILE *f;
    time_t now;
    struct tm *lt;
    char stamp[32];

    f = fopen(LOG_FILE, "a");
    if (f == NULL)
        return;

    now = time(NULL);
    lt = localtime(&now);
    if (lt != NULL)
        strftime(stamp, sizeof(stamp), "%Y-%m-%d %H:%M:%S", lt);
    else
        strcpy(stamp, "unknown-time");

    fprintf(f, "%s | seed=%d | phase=%d | %s\n", stamp, BOMB_SEED, phase, result);
    fclose(f);
}

void initialize_bomb(void)
{
    bomb_log(0, "START");
}

#endif /* NOTIFY */

/* ---- shared across both modes ----------------------------------------- */

void explode_bomb(void)
{
    printf("\nBOOM!!!\n");
    printf("The bomb has blown up.\n");
    fflush(stdout);

    bomb_log(num_defused + 1, "EXPLODED");
    exit(8);
}

/*
 * Called after each phase survives. Also decides whether the hidden stage
 * becomes reachable: the trigger phase's answer line may carry one extra
 * token beyond what that phase itself parses.
 */
void phase_defused(void)
{
    int a, b;
    char token[MAX_LINE_TOKEN];

    num_defused++;
    bomb_log(num_defused, "DEFUSED");

    if (num_defused == SECRET_TRIGGER_PHASE) {
        if (sscanf(get_phase_input(SECRET_TRIGGER_PHASE), "%d %d %63s",
                   &a, &b, token) == 3) {
            if (strcmp(token, PS_WORD) == 0)
                secret_armed = 1;
        }
    }

    if (num_defused == NUM_PUBLIC_PHASES && secret_armed) {
        printf("Curses, you've found the hidden stage!\n");
        printf("But finding it and solving it are quite different...\n");
        secret_phase();
    }
}
