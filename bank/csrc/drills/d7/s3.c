/* d7/s3.c - drill D7 phase 3: the deciding logic of the assignment's
 * phase 6 - each number x picks node 7-x, and the picked values must
 * strictly decrease. (The assignment also checks for duplicates and
 * relinks the list; neither changes the answer.)
 * Macros: D7_S3_V1..V6 */

typedef struct nodeStruct {
    int value;
    int index;
    struct nodeStruct *next;
} listNode;

listNode node6 = {D7_S3_V6, 6, NULL};
listNode node5 = {D7_S3_V5, 5, &node6};
listNode node4 = {D7_S3_V4, 4, &node5};
listNode node3 = {D7_S3_V3, 3, &node4};
listNode node2 = {D7_S3_V2, 2, &node3};
listNode node1 = {D7_S3_V1, 1, &node2};

void phase_3(char *input)
{
    int a[6];
    int i, j, prev = 0x7fffffff;
    listNode *p;

    read_six_numbers(input, a);
    for (i = 0; i < 6; i++) {
        if (a[i] < 1 || a[i] > 6)
            explode_bomb();
        p = &node1;
        for (j = 1; j < 7 - a[i]; j++)
            p = p->next;
        if (p->value >= prev)
            explode_bomb();
        prev = p->value;
    }
}
