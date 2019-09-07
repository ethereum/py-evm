from pathlib import Path

from eth2._utils.bls import bls
from eth2._utils.hash import hash_eth2
from eth2._utils.merkle.common import get_merkle_proof
from eth2._utils.merkle.sparse import calc_merkle_tree_from_leaves
from eth2.beacon.genesis import initialize_beacon_state_from_eth1
from eth2.beacon.helpers import compute_domain
from eth2.beacon.signature_domain import SignatureDomain
from eth2.beacon.tools.fixtures.config_types import Minimal
from eth2.beacon.tools.fixtures.loading import load_config_at_path, load_yaml_at
from eth2.beacon.tools.misc.ssz_vector import override_lengths
from eth2.beacon.types.deposit_data import DepositData
from eth2.beacon.types.deposits import Deposit

ROOT_DIR = Path("eth2/beacon/scripts")
KEY_SET_FILE = Path("keygen_16_validators.yaml")


def _load_config(config):
    config_file_name = ROOT_DIR / Path(f"config_{config.name}.yaml")
    return load_config_at_path(config_file_name)


def _mk_deposit_data(key_pair, bls_withdrawal_prefix, balance):
    privkey = int.from_bytes(bytes.fromhex(key_pair["privkey"][2:]), byteorder="big")
    pubkey = bytes.fromhex(key_pair["pubkey"][2:])
    withdrawal_credentials = (
        bls_withdrawal_prefix.to_bytes(1, byteorder="big") + hash_eth2(pubkey)[1:]
    )
    amount = balance

    deposit_data = DepositData(
        pubkey=pubkey, withdrawal_credentials=withdrawal_credentials, amount=amount
    )
    deposit_data_signing_root = deposit_data.signing_root
    signature = bls.sign(
        deposit_data_signing_root,
        privkey,
        compute_domain(SignatureDomain.DOMAIN_DEPOSIT),
    )

    return deposit_data.copy(signature=signature)


def _main():
    config_type = Minimal
    config = _load_config(config_type)
    override_lengths(config)

    key_set = load_yaml_at(ROOT_DIR / KEY_SET_FILE)

    deposit_datas = tuple(
        _mk_deposit_data(
            key_pair, config.BLS_WITHDRAWAL_PREFIX, config.MAX_EFFECTIVE_BALANCE
        )
        for key_pair in key_set
    )

    deposit_data_leaves = tuple(data.hash_tree_root for data in deposit_datas)

    deposits = tuple()
    for index, data in enumerate(deposit_datas):
        length_mix_in = (index + 1).to_bytes(32, byteorder="little")
        tree = calc_merkle_tree_from_leaves(deposit_data_leaves[: index + 1])

        deposit = Deposit(
            proof=(get_merkle_proof(tree, item_index=index) + (length_mix_in,)),
            data=data,
        )
        deposits += (deposit,)

    eth1_block_hash = b"\x42" * 32
    eth1_timestamp = 10000
    state = initialize_beacon_state_from_eth1(
        eth1_block_hash=eth1_block_hash,
        eth1_timestamp=eth1_timestamp,
        deposits=deposits,
        config=config,
    )

    # TODO make genesis_time configurable, ideally via some delay from now
    the_state_we_want = state.copy(genesis_time=1567777777)


if __name__ == "__main__":
    _main()
