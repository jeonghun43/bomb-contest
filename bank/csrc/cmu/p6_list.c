/* p6_list.c - phase 6: a permutation of 1..6; each number becomes 7-x and
 * picks a node of a linked list; the nodes are relinked in that order and
 * must then be in descending order of value.
 * Macros: P6_V1 .. P6_V6 (node values)
 *
 * Nodes are defined last-to-first so GCC 4.8 lays them out node1..node6, as
 * in the original. */

typedef struct nodeStruct {
    int value;
    int index;
    struct nodeStruct *next;
} listNode;

listNode node6 = {P6_V6, 6, NULL};
listNode node5 = {P6_V5, 5, &node6};
listNode node4 = {P6_V4, 4, &node5};
listNode node3 = {P6_V3, 3, &node4};
listNode node2 = {P6_V2, 2, &node3};
listNode node1 = {P6_V1, 1, &node2};

void phase_6(char *input)
{
    listNode *start = &node1;
    listNode *p;
    int indices[6];
    listNode *pointers[6];
    int i, j;

    read_six_numbers(input, indices);

    for (i = 0; i < 6; i++) {
        if (indices[i] < 1 || indices[i] > 6)
            explode_bomb();
        for (j = i + 1; j < 6; j++) {
            if (indices[i] == indices[j])
                explode_bomb();
        }
    }

    for (i = 0; i < 6; i++)
        indices[i] = 7 - indices[i];

    for (i = 0; i < 6; i++) {
        p = start;
        for (j = 1; j < indices[i]; j++)
            p = p->next;
        pointers[i] = p;
    }

    start = pointers[0];
    p = start;
    for (i = 1; i < 6; i++) {
        p->next = pointers[i];
        p = p->next;
    }
    p->next = NULL;

    p = start;
    for (i = 0; i < 5; i++) {
        if (p->value < p->next->value)
            explode_bomb();
        p = p->next;
    }
}
