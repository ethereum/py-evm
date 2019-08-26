from eth2.beacon.types.attestations import Attestation

from .pool import OperationPool


class AttestationPool(OperationPool[Attestation]):
    pass
