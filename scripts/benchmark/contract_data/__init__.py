import pathlib
from typing import Iterable

CONTRACTS_ROOT = "./scripts/benchmark/contract_data/"

CONTRACTS = ["erc20.sol", "DOSContract.sol"]


def get_contracts() -> Iterable[pathlib.Path]:
    for val in CONTRACTS:
        yield pathlib.Path(CONTRACTS_ROOT) / pathlib.Path(val)
