/*
 * driverlib.h - Reporting to the record daemon.
 *
 * NOT distributed to students. Same file name and entry points as the
 * original CMU bomb's reporting library, so the symbol table reads the same;
 * underneath it talks to our record daemon over a local Unix socket instead
 * of HTTP.
 */
#ifndef DRIVERLIB_H
#define DRIVERLIB_H

#define SUBMITR_MAXBUF 8192

/* Ask the daemon whether this bomb may run. 0 = go, -1 = status_msg says why. */
int init_driver(char *status_msg);

/*
 * Report one result line for bomb `userid`. Returns 0 when the daemon
 * received it, -1 (with status_msg set) when it could not be delivered.
 * `autograde` is unused and kept for the original's signature.
 */
int driver_post(char *userid, char *result, int autograde, char *status_msg);

#endif /* DRIVERLIB_H */
