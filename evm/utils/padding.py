def pad_left(value, to_size, pad_with):
    """
    Should be called to pad value to expected length
    """
    pad_amount = to_size - len(value)
    if pad_amount > 0:
        return b"".join((
            pad_with * pad_amount,
            value,
        ))
    else:
        return value


def pad_right(value, to_size, pad_with):
    """
    Should be called to pad value to expected length
    """
    pad_amount = to_size - len(value)
    if pad_amount > 0:
        return b"".join((
            value,
            pad_with * pad_amount,
        ))
    else:
        return value
