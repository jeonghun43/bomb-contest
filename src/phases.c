/*
 * phases.c - The defusing conditions.
 *
 * NOT distributed to contestants. This is the bomb.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "bomb.h"
#include "bombdata.h"

/*==========================================================================
 * Phase 1 - rotate and xor
 *
 * One integer. Both operations are bijections, so exactly one input works.
 *========================================================================*/
void phase_1(char *input)
{
    int x;
    unsigned v;

    if (sscanf(input, "%d", &x) != 1)
        explode_bomb();

    v = (unsigned) x ^ P1_KEY;
    v = rotl32(v, P1_ROT);

    if (v != P1_TARGET)
        explode_bomb();
}

/*==========================================================================
 * Phase 2 - 16-bit linear feedback shift register
 *
 * Six integers. The first is fixed; each later value is produced from the
 * previous one by a shift and a conditional xor.
 *========================================================================*/
void phase_2(char *input)
{
    int a[6];
    int i;
    unsigned t, n;

    read_six_numbers(input, a);

    if (a[0] != P2_SEED)
        explode_bomb();

    for (i = 1; i < 6; i++) {
        t = (unsigned) a[i - 1];
        n = (t << 1) & 0xFFFFu;
        if ((t & 0x8000u) != 0)
            n ^= P2_POLY;
        if ((unsigned) a[i] != n)
            explode_bomb();
    }
}

/*==========================================================================
 * Phase 3 - walk on a 4x4 torus
 *
 * Two integers: the starting row and column. Each cell encodes a direction,
 * a stride and a weight. Exactly one start reaches the goal with the right
 * accumulated weight (the generator checks all sixteen).
 *========================================================================*/
static const int p3_dr[4] = { -1, 0, 1, 0 }; /* up, right, down, left */
static const int p3_dc[4] = { 0, 1, 0, -1 };

void phase_3(char *input)
{
    int r, c, i, sum;
    unsigned v, dir, step;

    if (sscanf(input, "%d %d", &r, &c) != 2)
        explode_bomb();

    if (r < 0 || r > 3 || c < 0 || c > 3)
        explode_bomb();

    sum = 0;
    for (i = 0; i < P3_STEPS; i++) {
        v = p3_grid[r][c];
        dir = v & 3u;
        step = ((v >> 2) & 3u) + 1u;
        sum += (int) ((v >> 4) & 0xFu);
        r = (r + p3_dr[dir] * (int) step) & 3;
        c = (c + p3_dc[dir] * (int) step) & 3;
    }

    if (r * 4 + c != P3_GOAL)
        explode_bomb();
    if (sum != P3_SUM)
        explode_bomb();
}

/*==========================================================================
 * Phase 4 - modular inverse
 *
 * Two integers. The modulus is prime and the multiplier is coprime to it,
 * so the congruence has exactly one solution in range. The second number is
 * derived from the first by reversing its low eleven bits.
 *========================================================================*/
void phase_4(char *input)
{
    int x, y;

    if (sscanf(input, "%d %d", &x, &y) != 2)
        explode_bomb();

    if (x < 1 || x >= P4_MOD)
        explode_bomb();

    if ((x * P4_MUL) % P4_MOD != P4_RES)
        explode_bomb();

    if ((unsigned) y != bit_reverse((unsigned) x, 11))
        explode_bomb();
}

/*==========================================================================
 * Phase 5 - path through a binary tree
 *
 * A six character string of 'L' and 'R'. The direction of each step is
 * decided by the accumulator, so the path is determined, not searched.
 *========================================================================*/
void phase_5(char *input)
{
    char buf[MAX_LINE_TOKEN];
    int i, idx, want, got;
    unsigned acc, v;

    if (sscanf(input, "%63s", buf) != 1)
        explode_bomb();

    if (strlen(buf) != 6)
        explode_bomb();

    acc = P5_INIT;
    idx = 0;

    for (i = 0; i < 6; i++) {
        v = p5_tree[idx];
        want = (int) ((acc ^ v) & 1u);

        if (buf[i] != 'L' && buf[i] != 'R')
            explode_bomb();
        got = (buf[i] == 'R');

        if (got != want)
            explode_bomb();

        idx = 2 * idx + 1 + want;
        acc = rotl32(acc, 5) + v;
    }

    if (acc != P5_TARGET)
        explode_bomb();
}

/*==========================================================================
 * Phase 6 - chain of bit masks
 *
 * A permutation of 1..6. Each node carries a mask; the masks form a strictly
 * increasing chain under set inclusion, so exactly one order works.
 *========================================================================*/
struct p6_node {
    unsigned mask;
    int id;
    struct p6_node *next;
};

static struct p6_node p6_nodes[6];
static struct p6_node *p6_head;

static void p6_build(void)
{
    int i;

    for (i = 0; i < 6; i++) {
        p6_nodes[i].mask = p6_masks[i];
        p6_nodes[i].id = p6_ids[i];
        p6_nodes[i].next = NULL;
    }

    for (i = 0; i < 5; i++)
        p6_nodes[p6_chain[i]].next = &p6_nodes[p6_chain[i + 1]];

    p6_head = &p6_nodes[p6_chain[0]];
}

static struct p6_node *p6_lookup(int id)
{
    struct p6_node *n;

    for (n = p6_head; n != NULL; n = n->next) {
        if (n->id == id)
            return n;
    }

    return NULL;
}

void phase_6(char *input)
{
    int a[6];
    int i, j;
    unsigned prev;
    struct p6_node *n;

    read_six_numbers(input, a);

    for (i = 0; i < 6; i++) {
        if (a[i] < 1 || a[i] > 6)
            explode_bomb();
        for (j = 0; j < i; j++) {
            if (a[i] == a[j])
                explode_bomb();
        }
    }

    p6_build();

    prev = 0;
    for (i = 0; i < 6; i++) {
        n = p6_lookup(a[i]);
        if (n == NULL)
            explode_bomb();
        if ((prev & n->mask) != prev)
            explode_bomb();
        prev = n->mask;
    }

    if (prev != P6_FULL)
        explode_bomb();
}

/*==========================================================================
 * Secret phase - reverse the bits, then invert modulo a prime
 *
 * One integer. 65537 is prime, so the congruence pins down the reversed
 * value uniquely; the population count is a consistency check.
 *========================================================================*/
void secret_phase(void)
{
    char *input;
    int x;
    unsigned r;

    printf("Enter the final code: ");
    fflush(stdout);

    input = read_line();

    if (sscanf(input, "%d", &x) != 1)
        explode_bomb();

    if (x < 1 || x > 0xFFFF)
        explode_bomb();

    r = bit_reverse((unsigned) x, 16);

    if ((r * PS_MUL) % PS_MOD != PS_RES)
        explode_bomb();

    if (popcount32((unsigned) x) != PS_POP)
        explode_bomb();

    printf("Wow! You've defused the hidden stage!\n");
    bomb_log(7, "DEFUSED");
}
