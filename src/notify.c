/*
 * notify.c - Report to the record daemon over a local Unix socket.
 *
 * Compiled only in server mode (-DNOTIFY). NOT distributed to contestants.
 *
 * Identity is NOT carried in the message: the daemon reads the connecting
 * process's uid from the kernel (SO_PEERCRED), so a contestant cannot report
 * under another contestant's name. We therefore send no token here.
 */
#include <stddef.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/time.h>

#include "bomb.h"

#ifndef NOTIFY_SOCKET
#define NOTIFY_SOCKET "/run/bomblab/report.sock"
#endif

int notify_request(const char *line, char *reply, size_t n)
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

    /* Read one reply line (or as much as arrives before the timeout). */
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
