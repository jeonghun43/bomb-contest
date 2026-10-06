/* d8/s2.c - drill D8 phase 2: fun7 path encoding on a 15-node tree (the
 * CMU secret phase shape, here as an ordinary phase).
 * Macros: D8_N1, D8_N21, D8_N22, D8_N31..N34, D8_N41..N48, D8_S2_TARGET */

typedef struct treeNodeStruct {
    int value;
    struct treeNodeStruct *left, *right;
} treeNode;

treeNode n48 = {D8_N48, NULL, NULL};
treeNode n46 = {D8_N46, NULL, NULL};
treeNode n43 = {D8_N43, NULL, NULL};
treeNode n42 = {D8_N42, NULL, NULL};
treeNode n44 = {D8_N44, NULL, NULL};
treeNode n47 = {D8_N47, NULL, NULL};
treeNode n41 = {D8_N41, NULL, NULL};
treeNode n45 = {D8_N45, NULL, NULL};
treeNode n34 = {D8_N34, &n47, &n48};
treeNode n31 = {D8_N31, &n41, &n42};
treeNode n33 = {D8_N33, &n45, &n46};
treeNode n32 = {D8_N32, &n43, &n44};
treeNode n22 = {D8_N22, &n33, &n34};
treeNode n21 = {D8_N21, &n31, &n32};
treeNode n1 = {D8_N1, &n21, &n22};

int fun7(treeNode *node, int val)
{
    if (node == NULL)
        return -1;
    if (val < node->value)
        return fun7(node->left, val) * 2;
    else if (val == node->value)
        return 0;
    else
        return fun7(node->right, val) * 2 + 1;
}

void phase_2(char *input)
{
    int target = strtol(input, NULL, 10);

    if (fun7(&n1, target) != D8_S2_TARGET)
        explode_bomb();
}
