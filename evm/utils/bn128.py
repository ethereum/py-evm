from py_ecc import (
    optimized_bn128 as bn128,
)

from evm.exceptions import (
    ValidationError,
)


def validate_point(x, y):
    FQ = bn128.FQ

    if x >= bn128.field_modulus:
        raise ValidationError("Point x value is greater than field modulus")
    elif y >= bn128.field_modulus:
        raise ValidationError("Point y value is greater than field modulus")

    if (x, y) != (0, 0):
        p1 = (FQ(x), FQ(y), FQ(1))
        if not bn128.is_on_curve(p1, bn128.b):
            raise ValidationError("Point is not on the curve")
    else:
        p1 = (FQ(1), FQ(1), FQ(0))

    return p1
