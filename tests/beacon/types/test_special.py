from eth.beacon.types.special_records import (
    SpecialRecord,
)


def test_defaults(sample_special_params):
    special = SpecialRecord(**sample_special_params)
    assert special.kind == sample_special_params['kind']
    assert special.data == sample_special_params['data']
