/*
 * driverlib.c - Report to the record daemon over a local Unix socket.
 *
 * NOT distributed to students. Linked into every bomb, as the original links
 * its driverlib into the self-study bomb too; only server builds (-DNOTIFY)
 * call it.
 *
 * Protocol (one line each way, see specs/002-contest-server):
 *     HELLO <bomb_id>                          -> OK | CLOSED <why> | ERR <why>
 *     EVENT <bomb_id> <defused|exploded> <phase> <hexinput>   -> OK | ERR <why>
 *
 * Identity is NOT carried in the message: the daemon reads the connecting
 * process's uid from the kernel (SO_PEERCRED), so a student cannot report
 * under someone else's name. The daemon answers OK whether or not a claimed
 * defusal is valid, so a reply never reveals an answer.
 */
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/time.h>

#include "driverlib.h"

#ifndef NOTIFY_SOCKET
#define NOTIFY_SOCKET "/run/bomblab/report.sock"
#endif
#ifndef BOMB_ID
#define BOMB_ID "offline"
#endif

/* Send one request line, read one reply line. 0 on success, -1 otherwise. */
static int notify_request(const char *line, char *reply, size_t n)
{
    int fd;
    struct sockaddr_un addr;
    struct timeval tv;
    size_t len, off;
    ssize_t r;

    fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd < 0)
        return -1;

    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, NOTIFY_SOCKET, sizeof(addr.sun_path) - 1);

    /* Bound the whole exchange so a stalled daemon cannot hang the bomb. */
    tv.tv_sec = 3;
    tv.tv_usec = 0;
    setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));

    if (connect(fd, (struct sockaddr *) &addr, sizeof(addr)) < 0) {
        close(fd);
        return -1;
    }

    len = strlen(line);
    off = 0;
    while (off < len) {
        r = write(fd, line + off, len - off);
        if (r <= 0) {
            close(fd);
            return -1;
        }
        off += (size_t) r;
    }

    off = 0;
    while (off < n - 1) {
        r = read(fd, reply + off, n - 1 - off);
        if (r <= 0)
            break;
        off += (size_t) r;
        if (memchr(reply, '\n', off) != NULL)
            break;
    }
    reply[off] = '\0';
    close(fd);

    return off > 0 ? 0 : -1;
}

static void chomp(char *s)
{
    char *nl = strchr(s, '\n');

    if (nl != NULL)
        *nl = '\0';
}

int init_driver(char *status_msg)
{
    char line[128];
    char reply[SUBMITR_MAXBUF];

    snprintf(line, sizeof(line), "HELLO %s\n", BOMB_ID);

    if (notify_request(line, reply, sizeof(reply)) != 0) {
        strcpy(status_msg, "Could not reach the record server. "
               "Ask a proctor for help.");
        return -1;
    }
    chomp(reply);
    if (strncmp(reply, "OK", 2) != 0) {
        /* CLOSED (outside the operating window) or ERR (unknown bomb). */
        snprintf(status_msg, SUBMITR_MAXBUF,
                 "This bomb is not active right now: %s", reply);
        return -1;
    }
    strcpy(status_msg, "OK");
    return 0;
}

int driver_post(char *userid, char *result, int autograde, char *status_msg)
{
    char line[SUBMITR_MAXBUF];
    char reply[SUBMITR_MAXBUF];

    (void) autograde;
    snprintf(line, sizeof(line), "EVENT %s %s\n", userid, result);

    if (notify_request(line, reply, sizeof(reply)) != 0) {
        strcpy(status_msg, "Could not reach the record server.");
        return -1;
    }
    chomp(reply);
    snprintf(status_msg, SUBMITR_MAXBUF, "%s", reply);
    return 0;
}
