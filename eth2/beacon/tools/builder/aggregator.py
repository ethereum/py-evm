from eth_typing import BLSSignature
from ssz import get_hash_tree_root, uint64

from eth2._utils.bls import bls
from eth2._utils.hash import hash_eth2
from eth2.beacon.committee_helpers import get_beacon_committee
from eth2.beacon.helpers import compute_epoch_at_slot, get_domain
from eth2.beacon.signature_domain import SignatureDomain
from eth2.beacon.types.states import BeaconState
from eth2.beacon.typing import CommitteeIndex, Slot
from eth2.configs import CommitteeConfig

# TODO: TARGET_AGGREGATORS_PER_COMMITTEE is not in Eth2Config now.
TARGET_AGGREGATORS_PER_COMMITTEE = 16


def slot_signature(
    state: BeaconState, slot: Slot, privkey: int, config: CommitteeConfig
) -> BLSSignature:
    """
    Sign on ``slot`` and return the signature.
    """
    domain = get_domain(
        state,
        SignatureDomain.DOMAIN_BEACON_ATTESTER,
        config.SLOTS_PER_EPOCH,
        message_epoch=compute_epoch_at_slot(slot, config.SLOTS_PER_EPOCH),
    )
    return bls.sign(get_hash_tree_root(slot, sedes=uint64), privkey, domain)


def is_aggregator(
    state: BeaconState,
    slot: Slot,
    index: CommitteeIndex,
    signature: BLSSignature,
    config: CommitteeConfig,
) -> bool:
    """
    Check if the validator is one of the aggregators of the given ``slot``.

      .. note::
        - Probabilistically, with enought validators, the aggregator count should
        approach ``TARGET_AGGREGATORS_PER_COMMITTEE``.

        - With ``len(committee)`` is 128 and ``TARGET_AGGREGATORS_PER_COMMITTEE`` is 16,
        the expected length of selected validators is 16.

        - It's possible that this algorithm selects *no one* as the aggregator, but with the
        above parameters, the chance of having no aggregator has a probability of 3.78E-08.

        - Chart analysis: https://docs.google.com/spreadsheets/d/1C7pBqEWJgzk3_jesLkqJoDTnjZOODnGTOJUrxUMdxMA  # noqa: E501
    """
    committee = get_beacon_committee(state, slot, index, config)
    modulo = max(1, len(committee) // TARGET_AGGREGATORS_PER_COMMITTEE)
    return int.from_bytes(hash_eth2(signature)[0:8], byteorder="little") % modulo == 0
