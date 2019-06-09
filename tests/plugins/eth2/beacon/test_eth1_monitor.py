import pytest
import ssz
import eth_utils
from trio.testing import wait_all_tasks_blocked

from eth2.beacon.types.deposit_data import DepositData

from trinity.plugins.eth2.beacon.eth1_monitor import Eth1Monitor

from p2p.trio_service import background_service

from .constants import MIN_DEPOSIT_AMOUNT


SAMPLE_PUBKEY = b"\x11" * 48
SAMPLE_WITHDRAWAL_CREDENTIALS = b"\x22" * 32
SAMPLE_VALID_SIGNATURE = b"\x33" * 96


def deposit(w3, registration_contract, amount):
    deposit_input = (
        SAMPLE_PUBKEY,
        SAMPLE_WITHDRAWAL_CREDENTIALS,
        SAMPLE_VALID_SIGNATURE,
        ssz.get_hash_tree_root(
            DepositData(
                pubkey=SAMPLE_PUBKEY,
                withdrawal_credentials=SAMPLE_WITHDRAWAL_CREDENTIALS,
                amount=amount,
                signature=SAMPLE_VALID_SIGNATURE,
            )
        ),
    )
    tx_hash = registration_contract.functions.deposit(*deposit_input).transact(
        {"value": amount * eth_utils.denoms.gwei}
    )
    tx_receipt = w3.eth.waitForTransactionReceipt(tx_hash)
    assert tx_receipt["status"]


def test_deploy(w3, registration_contract):
    pass


@pytest.mark.trio
async def test_eth1_monitor_filter(w3, registration_contract, logs_lookback_period):
    deposit(w3, registration_contract, MIN_DEPOSIT_AMOUNT)
    print("!@# deposit #0")
    deposit(w3, registration_contract, MIN_DEPOSIT_AMOUNT)
    m = Eth1Monitor(
        w3,
        registration_contract.address,
        registration_contract.abi,
        0,
        logs_lookback_period,
    )
    async with background_service(m):
        deposit(w3, registration_contract, MIN_DEPOSIT_AMOUNT)
        await wait_all_tasks_blocked()
        print("!@# deposit #1")
