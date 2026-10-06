/* d8/s3.c - drill D8 phase 3: walk a 15-node tree toward the value, adding
 * up every node visited; the sum must equal D8_S3_T.
 * Macros: D8_M1, D8_M21, D8_M22, D8_M31..M34, D8_M41..M48, D8_S3_T */

typedef struct mStruct {
    int value;
    struct mStruct *left, *right;
} mnode;

mnode m48 = {D8_M48, NULL, NULL};
mnode m47 = {D8_M47, NULL, NULL};
mnode m46 = {D8_M46, NULL, NULL};
mnode m45 = {D8_M45, NULL, NULL};
mnode m44 = {D8_M44, NULL, NULL};
mnode m43 = {D8_M43, NULL, NULL};
mnode m42 = {D8_M42, NULL, NULL};
mnode m41 = {D8_M41, NULL, NULL};
mnode m34 = {D8_M34, &m47, &m48};
mnode m33 = {D8_M33, &m45, &m46};
mnode m32 = {D8_M32, &m43, &m44};
mnode m31 = {D8_M31, &m41, &m42};
mnode m22 = {D8_M22, &m33, &m34};
mnode m21 = {D8_M21, &m31, &m32};
mnode m1 = {D8_M1, &m21, &m22};

void phase_3(char *input)
{
    int x, sum = 0;
    mnode *t = &m1;

    if (sscanf(input, "%d", &x) != 1)
        explode_bomb();
    while (t != NULL) {
        sum += t->value;
        if (x == t->value)
            break;
        t = x < t->value ? t->left : t->right;
    }
    if (sum != D8_S3_T)
        explode_bomb();
}
