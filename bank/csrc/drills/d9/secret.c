/* d9/secret.c - drill D9 secret phase: reached only through phase_defused().
 * Macros: D9_SEC_KEY (3 ints) */

int d9_key[3] = D9_SEC_KEY;

void secret_phase()
{
    char *input = read_line();
    int target = strtol(input, NULL, 10);

    if (target != d9_key[0] + d9_key[1] * d9_key[2])
        explode_bomb();
    printf("Wow! You've defused the secret stage!\n");
    phase_defused();
}
