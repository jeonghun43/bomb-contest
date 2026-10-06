"""
words.py - Word and phrase pools for drill answers.

Plain lowercase words, so a student types them without thinking about
encoding. None is an answer from the original bomb.
"""

WORDS = [
    "breakpoint", "register", "segment", "pointer", "compiler", "assembly",
    "debugger", "syscall", "linker", "loader", "pipeline", "overflow",
    "bitmask", "operand", "mnemonic", "address", "offset", "stride",
    "lattice", "quartz", "harbor", "lantern", "compass", "glacier", "meadow",
    "orchard", "pebble", "ripple", "thistle", "willow", "ember", "falcon",
    "garnet", "hollow", "juniper", "kettle", "marble", "nimbus", "pumice",
    "saffron", "tundra", "velvet", "walnut", "zenith", "anchor", "beacon",
    "cobalt", "dynamo", "fjord", "gondola", "hazel", "iris", "jasper",
]

PHRASES = [
    "strings end at the first zero byte",
    "the length check comes first",
    "every character must match",
    "read the comparison twice",
    "examine memory as a string",
    "the answer was in rodata all along",
    "registers hold the arguments",
    "two strings walk side by side",
    "a null terminator ends the loop",
    "one byte at a time",
]
