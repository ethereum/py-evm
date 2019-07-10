from .pool import OperationPool

from eth2.beacon.types.attestations import Attestation


class AttestationPool(OperationPool[Attestation]):
    pass
