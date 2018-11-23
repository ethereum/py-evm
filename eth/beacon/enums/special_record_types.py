from enum import IntEnum


class SpecialRecordTypes(IntEnum):
    LOGOUT = 0
    CASPER_SLASHING = 1
    PROPOSER_SLASHING = 2
    DEPOSIT_PROOF = 3
