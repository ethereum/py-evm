# ``max_iterations`` was added to prevent the exponential nature from running
# indefinitely. Some ``ethereum/tests`` would hang forever on this calculation. We
# should keep an eye on this function to see if this value is accurate enough for
# the use case.
def fake_exponential(
    factor: int, numerator: int, denominator: int, max_iterations: int = 10000
) -> int:
    i = 1
    output = 0
    numerator_accum = factor * denominator
    while numerator_accum > 0 and i < max_iterations:
        output += numerator_accum
        numerator_accum = (numerator_accum * numerator) // (denominator * i)
        i += 1
    return output // denominator
