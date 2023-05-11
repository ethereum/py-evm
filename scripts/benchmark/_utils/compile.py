import json
import pathlib
import subprocess
from typing import (
    Dict,
    Iterable,
)


def derive_compile_path(contract_path: pathlib.Path) -> pathlib.Path:
    return contract_path.with_name(f"{contract_path.name}-compiled")


def compile_contract(contract_path: pathlib.Path) -> None:
    out_path = derive_compile_path(contract_path)
    subprocess.run(
        [
            "solc",
            contract_path,
            "--pretty-json",
            "--combined-json",
            "bin,abi",
            "--overwrite",
            "-o",
            out_path,
        ],
        stdout=subprocess.PIPE,
    )


def compile_contracts(contract_paths: Iterable[pathlib.Path]) -> None:
    for path in contract_paths:
        compile_contract(path)


def get_compiled_contract(
    contract_path: pathlib.Path, contract_name: str
) -> Dict[str, str]:
    compiled_path = derive_compile_path(contract_path) / "combined.json"

    with open(compiled_path) as file:
        data = json.load(file)
    return data["contracts"][f"{contract_path}:{contract_name}"]
