/* p4_func4_bsearch.c - phase 4: "%d %d", the first is searched for by a
 * recursive binary search over [0, P4_HI] whose return value must be 0, the
 * second must equal P4_SECOND.
 * Macros: P4_HI, P4_SECOND
 *
 * The target return value stays 0, as in the original: any other value turns
 * "test %eax,%eax" into "cmp $n,%eax" and the code no longer matches. */

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

void phase_4(char *input)
{
    int user_val, user_val2, result, numScanned;

    numScanned = sscanf(input, "%d %d", &user_val, &user_val2);
    if ((numScanned != 2) || user_val < 0 || user_val > P4_HI)
        explode_bomb();

    result = func4(user_val, 0, P4_HI);
    if (result != 0 || user_val2 != P4_SECOND)
        explode_bomb();
}
