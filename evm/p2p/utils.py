def sxor(s1, s2):
    if len(s1) != len(s2):
        raise ValueError("Cannot sxor strings of different length")
    return bytes(x ^ y for x, y in zip(s1, s2))


def roundup_16(x):
    """Rounds up the given value to the next multiple of 16."""
    remainder = x % 16
    if remainder != 0:
        x += 16 - remainder
    return x
