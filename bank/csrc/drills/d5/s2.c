/* d5/s2.c - drill D5 phase 2: recursive binary search; the number must make
 * func4 return 0. (The assignment's phase 4 also checks a second number.)
 * Macros: D5_S2_HI */

int func4(int val, int low, int high)
{
    int mid;

    mid = low + (high - low) / 2;
    if (mid > val)
        return func4(val, low, mid - 1) * 2;
    else if (mid < val)
        return func4(val, mid + 1, high) * 2 + 1;
    else
        return 0;
}

void phase_2(char *input)
{
    int x;

    if (sscanf(input, "%d", &x) != 1 || x < 0 || x > D5_S2_HI)
        explode_bomb();
    if (func4(x, 0, D5_S2_HI) != 0)
        explode_bomb();
}
