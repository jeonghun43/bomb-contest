/* d2/s1.c - drill D2 phase 1: shifts and multiplies (lea / imul / shl).
 * Macros: D2_S1_SHIFT, D2_S1_MUL, D2_S1_SUB, D2_S1_TARGET */

void phase_1(char *input)
{
    int x, y;

    if (sscanf(input, "%d", &x) != 1)
        explode_bomb();
    y = (x << D2_S1_SHIFT) + x * D2_S1_MUL - D2_S1_SUB;
    if (y != D2_S1_TARGET)
        explode_bomb();
}
