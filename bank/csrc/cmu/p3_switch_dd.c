/* p3_switch_dd.c - phase 3: "%d %d", the first picks a case of a dense
 * switch (a jump table), the second must equal that case's value.
 * Macros: P3_V0 .. P3_V7 */

void phase_3(char *input)
{
    int index, val, x = 0;
    int numScanned;

    numScanned = sscanf(input, "%d %d", &index, &val);
    if (numScanned < 2)
        explode_bomb();

    switch (index) {
    case 0: x = P3_V0; break;
    case 1: x = P3_V1; break;
    case 2: x = P3_V2; break;
    case 3: x = P3_V3; break;
    case 4: x = P3_V4; break;
    case 5: x = P3_V5; break;
    case 6: x = P3_V6; break;
    case 7: x = P3_V7; break;
    default:
        explode_bomb();
        x = 0;
        break;
    }
    if (x != val)
        explode_bomb();
}
