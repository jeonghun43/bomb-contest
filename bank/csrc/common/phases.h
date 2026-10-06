/*
 * phases.h - Phase entry points.
 *
 * NOT distributed to students. A CMU-structure bomb defines phase_1..phase_6
 * and secret_phase; a drill defines phase_1..phase_3 (and secret_phase for
 * D9). Declaring the unused ones is harmless.
 */
#ifndef PHASES_H
#define PHASES_H

void phase_1(char *input);
void phase_2(char *input);
void phase_3(char *input);
void phase_4(char *input);
void phase_5(char *input);
void phase_6(char *input);

/*
 * Deliberately declared without a parameter list, as in the original: the
 * call in phase_defused() then carries "mov $0x0,%eax" exactly like the
 * original binary does.
 */
void secret_phase();

#endif /* PHASES_H */
