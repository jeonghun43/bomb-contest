/* d8/s1.c - drill D8 phase 1: walk a 7-node binary search tree looking for
 * the value; the depth where it is found must equal D8_S1_DEPTH.
 * Macros: D8_B1, D8_B21, D8_B22, D8_B31..D8_B34, D8_S1_DEPTH */

typedef struct bstStruct {
    int value;
    struct bstStruct *left, *right;
} bst;

bst b34 = {D8_B34, NULL, NULL};
bst b33 = {D8_B33, NULL, NULL};
bst b32 = {D8_B32, NULL, NULL};
bst b31 = {D8_B31, NULL, NULL};
bst b22 = {D8_B22, &b33, &b34};
bst b21 = {D8_B21, &b31, &b32};
bst b1 = {D8_B1, &b21, &b22};

void phase_1(char *input)
{
    int x, d = 0;
    bst *t = &b1;

    if (sscanf(input, "%d", &x) != 1)
        explode_bomb();
    while (t != NULL && t->value != x) {
        t = x < t->value ? t->left : t->right;
        d++;
    }
    if (t == NULL || d != D8_S1_DEPTH)
        explode_bomb();
}
