/* d4/s2.c - drill D4 phase 2: "%d %c"; the cases start at an offset, so
 * the compiler subtracts it before the bounds check and the table jump, and
 * each case names the character that must follow. Five cases, so a table.
 * Macros: D4_S2_BASE, D4_S2_C0..C4 (char codes) */

void phase_2(char *input)
{
    int index;
    char c, want = 0;

    if (sscanf(input, "%d %c", &index, &c) < 2)
        explode_bomb();

    switch (index) {
    case D4_S2_BASE + 0: want = D4_S2_C0; break;
    case D4_S2_BASE + 1: want = D4_S2_C1; break;
    case D4_S2_BASE + 2: want = D4_S2_C2; break;
    case D4_S2_BASE + 3: want = D4_S2_C3; break;
    case D4_S2_BASE + 4: want = D4_S2_C4; break;
    default:
        explode_bomb();
        break;
    }
    if (c != want)
        explode_bomb();
}
