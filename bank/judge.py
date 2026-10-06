"""
judge.py - C library semantics in Python, for the server's re-scoring.

The server never trusts a bomb's "defused" report: it re-runs the phase's
check on the reported input line. That check must agree with the compiled
bomb on every input, including odd spacing, signs, overflow and trailing
junk, or a student is recorded as exploding when they did not. This module
reproduces the glibc behaviour the bombs rely on; tools/fuzz_bank.py holds it
to the real binaries.

Lines are str decoded as latin-1, one character per byte, exactly the bytes
the bomb stored (after read_line dropped the last character).
"""

INT_MIN, INT_MAX = -(1 << 31), (1 << 31) - 1
LONG_MIN, LONG_MAX = -(1 << 63), (1 << 63) - 1
WS = " \t\n\v\f\r"            # isspace() in the C locale


def to_int32(v):
    """Truncate to a C int, as assigning a long to an int does."""
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v & 0x80000000 else v


def to_uint32(v):
    return v & 0xFFFFFFFF


def signed_char(ch):
    """A plain C char is signed on x86-64."""
    b = ord(ch) & 0xFF
    return b - 256 if b & 0x80 else b


def _skip_ws(s, i):
    while i < len(s) and s[i] in WS:
        i += 1
    return i


def _scan_long(s, i):
    """
    Optional sign then decimal digits at s[i:]. Returns (value, next) with
    glibc's clamp to long on overflow, or (None, i) if there are no digits.
    """
    j = i
    if j < len(s) and s[j] in "+-":
        j += 1
    k = j
    while k < len(s) and "0" <= s[k] <= "9":
        k += 1
    if k == j:
        return None, i
    v = int(s[j:k])
    if s[i] == "-":
        v = -v
    v = max(LONG_MIN, min(LONG_MAX, v))
    return v, k


def sscanf(s, fmt):
    """
    Emulate glibc sscanf for the directives the bombs use: %d, %s, %c,
    whitespace, and literal characters.

    Returns (ret, values) where ret is what sscanf returns: the number of
    conversions assigned, or -1 (EOF) when the input ran out before the first
    conversion and before any matching failure.
    """
    vals = []
    i = 0
    f = 0
    while f < len(fmt):
        c = fmt[f]
        if c in WS:
            i = _skip_ws(s, i)
            f += 1
            continue
        if c != "%":
            if i >= len(s):
                return (-1 if not vals else len(vals)), vals
            if s[i] != c:
                return len(vals), vals
            i += 1
            f += 1
            continue

        conv = fmt[f + 1]
        f += 2
        if conv == "d":
            i = _skip_ws(s, i)
            if i >= len(s):
                return (-1 if not vals else len(vals)), vals
            v, i2 = _scan_long(s, i)
            if v is None:
                return len(vals), vals
            vals.append(to_int32(v))
            i = i2
        elif conv == "s":
            i = _skip_ws(s, i)
            if i >= len(s):
                return (-1 if not vals else len(vals)), vals
            j = i
            while j < len(s) and s[j] not in WS:
                j += 1
            vals.append(s[i:j])
            i = j
        elif conv == "c":
            if i >= len(s):
                return (-1 if not vals else len(vals)), vals
            vals.append(s[i])
            i += 1
        else:
            raise ValueError("unsupported conversion %%%s" % conv)
    return len(vals), vals


def strtol(s):
    """strtol(s, NULL, 10): whitespace, sign, digits; 0 if none; long clamp."""
    i = _skip_ws(s, 0)
    v, _ = _scan_long(s, i)
    return 0 if v is None else v


def atoi_int(s):
    """`int x = strtol(s, NULL, 10);`"""
    return to_int32(strtol(s))


def read_six_numbers(s):
    """The bomb's read_six_numbers: six ints, or None where it explodes."""
    ret, vals = sscanf(s, "%d %d %d %d %d %d")
    return vals if ret >= 6 else None


def strings_not_equal(a, b):
    """The bomb's own comparison: length first, then character by character."""
    return a != b


def string_length(s):
    return len(s)


def check(bomb, phase, line):
    """True iff `line` defuses phase `phase` (1-based, secret = N+1)."""
    p = bomb.phase(phase)
    if p is None:
        return False
    return bool(p.check(line))
