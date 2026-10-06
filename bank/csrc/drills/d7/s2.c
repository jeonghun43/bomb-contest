/* d7/s2.c - drill D7 phase 2: six numbers 1..6 each pick a node (walk k-1
 * steps from elem1); the picked values must strictly increase.
 * Macros: D7_S2_V1..V6 */

typedef struct elemStruct {
    int value;
    int index;
    struct elemStruct *next;
} elem;

elem elem6 = {D7_S2_V6, 6, NULL};
elem elem5 = {D7_S2_V5, 5, &elem6};
elem elem4 = {D7_S2_V4, 4, &elem5};
elem elem3 = {D7_S2_V3, 3, &elem4};
elem elem2 = {D7_S2_V2, 2, &elem3};
elem elem1 = {D7_S2_V1, 1, &elem2};

void phase_2(char *input)
{
    int a[6];
    int i, j, prev = 0;
    elem *p;

    read_six_numbers(input, a);
    for (i = 0; i < 6; i++) {
        if (a[i] < 1 || a[i] > 6)
            explode_bomb();
        p = &elem1;
        for (j = 1; j < a[i]; j++)
            p = p->next;
        if (p->value <= prev)
            explode_bomb();
        prev = p->value;
    }
}
