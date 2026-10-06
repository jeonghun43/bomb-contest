/* d7/s1.c - drill D7 phase 1: walk a linked list a fixed number of steps
 * from item1; the list is not linked in memory order.
 * Macros: D7_S1_V1..V6 (values), D7_S1_N1..N6 (next pointers), D7_S1_STEPS */

typedef struct itemStruct {
    int value;
    int index;
    struct itemStruct *next;
} item;

extern item item1, item2, item3, item4, item5, item6;

item item1 = {D7_S1_V1, 1, D7_S1_N1};
item item2 = {D7_S1_V2, 2, D7_S1_N2};
item item3 = {D7_S1_V3, 3, D7_S1_N3};
item item4 = {D7_S1_V4, 4, D7_S1_N4};
item item5 = {D7_S1_V5, 5, D7_S1_N5};
item item6 = {D7_S1_V6, 6, D7_S1_N6};

void phase_1(char *input)
{
    item *p = &item1;
    int i, x;

    if (sscanf(input, "%d", &x) != 1)
        explode_bomb();
    for (i = 0; i < D7_S1_STEPS; i++)
        p = p->next;
    if (x != p->value)
        explode_bomb();
}
