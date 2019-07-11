# from eth_utils import (
#     ValidationError,
# )

# from eth2._utils.bitfield import (
#     get_bitfield_length,
#     has_voted,
# )


# NOTE: this has moved to ssz layer of validation in spec/v0.8
# def validate_bitfield(bitfield: bytes, committee_size: int) -> None:
#     """
#     Verify ``bitfield`` against the ``committee_size``.
#     """
#     if len(bitfield) != get_bitfield_length(committee_size):
#         raise ValidationError(
#             f"len(bitfield) ({len(bitfield)}) != "
#             f"get_bitfield_length(committee_size) ({get_bitfield_length(committee_size)}), "
#             f"where committee_size={committee_size}"
#         )

#     for i in range(committee_size, len(bitfield) * 8):
#         if has_voted(bitfield, i):
#             raise ValidationError(f"bit ({i}) should be zero")
