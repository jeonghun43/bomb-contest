/* d4/s1.c - drill D4 phase 1: a dense switch over 0..4 (a jump table).
 * Five cases: GCC 4.8 emits a table from five cases up; with four it
 * compares instead.
 * Macros: D4_S1_V0 .. D4_S1_V4 */

void phase_1(char *input)
{
    int index, val, x = 0;

    if (sscanf(input, "%d %d", &index, &val) < 2)
        explode_bomb();

    switch (index) {
    case 0: x = D4_S1_V0; break;
    case 1: x = D4_S1_V1; break;
    case 2: x = D4_S1_V2; break;
    case 3: x = D4_S1_V3; break;
    case 4: x = D4_S1_V4; break;
    default:
        explode_bomb();
        break;
    }
    if (x != val)
        explode_bomb();
}
