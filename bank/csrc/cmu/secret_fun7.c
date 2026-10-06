/* secret_fun7.c - secret phase: a number 1..1001 is looked up in a 15-node
 * binary search tree; fun7 encodes the path (left: 2*f, right: 2*f+1, found:
 * 0, missing: -1) and the result must equal SECRET_TARGET.
 * Macros: T_N1, T_N21, T_N22, T_N31..T_N34, T_N41..T_N48, SECRET_TARGET
 *
 * Node definition order makes GCC 4.8 lay the tree out as the original does
 * (n1, n21, n22, n32, n33, n31, n34, n45, ...). SECRET_TARGET is never 0:
 * 0 would turn "cmp $n,%eax" into "test %eax,%eax". */

typedef struct treeNodeStruct {
    int value;
    struct treeNodeStruct *left, *right;
} treeNode;

treeNode n48 = {T_N48, NULL, NULL};
treeNode n46 = {T_N46, NULL, NULL};
treeNode n43 = {T_N43, NULL, NULL};
treeNode n42 = {T_N42, NULL, NULL};
treeNode n44 = {T_N44, NULL, NULL};
treeNode n47 = {T_N47, NULL, NULL};
treeNode n41 = {T_N41, NULL, NULL};
treeNode n45 = {T_N45, NULL, NULL};
treeNode n34 = {T_N34, &n47, &n48};
treeNode n31 = {T_N31, &n41, &n42};
treeNode n33 = {T_N33, &n45, &n46};
treeNode n32 = {T_N32, &n43, &n44};
treeNode n22 = {T_N22, &n33, &n34};
treeNode n21 = {T_N21, &n31, &n32};
treeNode n1 = {T_N1, &n21, &n22};

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

void secret_phase()
{
    char *input = read_line();
    int target = strtol(input, NULL, 10);
    int result;

    if (target < 1 || target > 1001)
        explode_bomb();
    result = fun7(&n1, target);
    if (result != SECRET_TARGET)
        explode_bomb();
    printf("Wow! You've defused the secret stage!\n");
    phase_defused();
}
