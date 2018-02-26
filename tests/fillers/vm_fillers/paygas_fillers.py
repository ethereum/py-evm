from collections import namedtuple

from cytoolz import (
    pipe,
)

from evm.utils.test_builder.test_builder import (
    setup_sharding_filler,
    pre_state,
    expect,
)

from evm.utils.test_builder.builder_utils import (
    generate_random_address,
)


Test = namedtuple("Test", ["filler", "fill_kwargs"])
Test.__new__.__defaults__ = (None,)  # make `None` default for fill_kwargs


address = generate_random_address()
coinbase = generate_random_address()
caller = generate_random_address()
normal_contract_address = b"`\xa8\xdc~\xba\xd7\x03\x8c\x9a\x83}\x84\xd8\x13\xa8R\x92\xe5d\xbd"
paygas_contract_address = b"[p\xb7s\x88\xb4e\xf7R@w\xd2e\xfa\x1c{j\x9acy"
assert address != normal_contract_address


storage_updated = (address, "storage", {
    0: 1,
    1: 1,
})

broke_caller = (caller, "balance", 0)
solvent_caller = (caller, "balance", 1000000)
normal_contract = (normal_contract_address, {
    # "vyperLLLCode": ["seq", ["MSTORE", 0, 1], ["RETURN", 0, 32]],
    "code": b"`\x01`\x00R` `\x00\xf3",
})
paygas_contract = (normal_contract_address, {
    # "vyperLLLCode": ["PAYGAS", 0],
    "code": b"`\x00\xf5",
})


paygas_omitted_test = Test(pipe(
    setup_sharding_filler("PaygasOmitted"),
    pre_state({
        address: {
            "balance": 0,
            # "vyperLLLCode": [
            #     "seq",
            #     ["SSTORE", 0, 1],
            #     ["SSTORE", 1, 1],
            # ],
            "code": b"`\x01`\x00U`\x01`\x01U",
        }
    }),
    expect(
        networks=["Sharding"],
        transaction={
            "to": address,
            "accessList": [
                [address, b""],
            ]
        },
        post_state=[
            storage_updated,
        ]
    )
))


paygas_normal_test = Test(pipe(
    setup_sharding_filler("PaygasNormal"),
    pre_state({
        address: {
            "balance": 100000,
            # "vyperLLLCode": [
            #     "seq",
            #     ["SSTORE", 0, 1],
            #     ["PAYGAS", 1],
            #     ["SSTORE", 1, 1],
            # ],
            "code": b"`\x01`\x00U`\x01\xf5P`\x01`\x01U",
        }
    }),
    expect(
        networks=["Sharding"],
        transaction={
            "to": address,
            "accessList": [
                [address, b""],
            ],
        },
        post_state=[
            storage_updated,
            (address, "balance", 38980),
        ]
    )
))


paygas_zero_gas_price_test = Test(pipe(
    setup_sharding_filler("PaygasZeroGasprice"),
    pre_state({
        address: {
            "balance": 100000,
            # "vyperLLLCode": [
            #     "seq",
            #     ["SSTORE", 0, 1],
            #     ["PAYGAS", 0],
            #     ["SSTORE", 1, 1],
            # ],
            "code": b"`\x01`\x00U`\x00\xf5P`\x01`\x01U",
        }
    }),
    expect(
        networks=["Sharding"],
        transaction={
            "to": address,
            "accessList": [
                [address, b""],
            ],
        },
        post_state=[
            storage_updated,
        ]
    )
))


paygas_repeated_test = Test(pipe(
    setup_sharding_filler("PaygasRepeated"),
    pre_state({
        address: {
            "balance": 100000,
            # "vyperLLLCode": [
            #     "seq",
            #     ["SSTORE", 0, 1],
            #     ["PAYGAS", 1],
            #     ["PAYGAS", 2],
            #     ["SSTORE", 1, 1]
            # ],
            "code": b"`\x01`\x00U`\x01\xf5P`\x02\xf5P`\x01`\x01U",
        }
    }),
    expect(
        networks=["Sharding"],
        transaction={
            "to": address,
            "accessList": [
                [address, b""],
            ],
        },
        post_state=[
            (address, "balance", 38972),
            storage_updated,
        ],
    )
))


paygas_repeated_same_gasprice_test = Test(pipe(
    setup_sharding_filler("PaygasRepeatedSameGasprice"),
    pre_state({
        address: {
            "balance": 100000,
            # "vyperLLLCode": [
            #     "seq",
            #     ["SSTORE", 0, 1],
            #     ["PAYGAS", 1],
            #     ["PAYGAS", 1],
            #     ["SSTORE", 1, 1]
            # ],
            "code": b"`\x01`\x00U`\x01\xf5P`\x01\xf5P`\x01`\x01U",
        }
    }),
    expect(
        networks=["Sharding"],
        transaction={
            "to": address,
            "accessList": [
                [address, b""],
            ],
        },
        post_state=[
            (address, "balance", 38972),
            storage_updated,
        ],
    )
))


paygas_insufficient_balance_test = Test(pipe(
    setup_sharding_filler("PaygasInsufficientBalance"),
    pre_state({
        address: {
            "balance": 0,
            # "vyperLLLCode": [
            #     "seq",
            #     ["SSTORE", 0, 1],
            #     ["PAYGAS", 1],
            #     ["SSTORE", 1, 1]
            # ],
            "code": b"`\x01`\x00U`\x01\xf5P`\x01`\x01U",
        }
    }),
    expect(
        networks=["Sharding"],
        transaction={
            "to": address,
            "accessList": [
                [address, b""],
            ],
        },
        post_state=None,
    )
))


paygas_after_call_test = Test(pipe(
    setup_sharding_filler("PaygasAfterCall"),
    pre_state([
        (address, {
            "balance": 0,
            # "vyperLLLCode": [
            #     "seq",
            #     ["SSTORE", 0, 1],
            #     ["CALL", 1000, normal_contract_address, 0, 0, 0, 0, 0],
            #     ["PAYGAS", 0],
            #     ["SSTORE", 1, 1],
            # ],
            "code": (
                b"`\x01`\x00U`\x00`\x00`\x00`\x00`\x00s`\xa8\xdc~\xba\xd7\x03\x8c\x9a\x83}\x84"
                b"\xd8\x13\xa8R\x92\xe5d\xbda\x03\xe8\xf1P`\x00\xf5P`\x01`\x01U"
            )
        }),
        normal_contract,
    ]),
    expect(
        networks=["Sharding"],
        transaction={
            "to": address,
            "accessList": [
                [address, b""],
                [normal_contract_address],
            ],
        },
        post_state=[
            storage_updated,
        ]
    )
))


paygas_in_call_test = Test(pipe(
    setup_sharding_filler("PaygasInCall"),
    pre_state([
        (address, {
            "balance": 0,
            # "vyperLLLCode": [
            #     "seq",
            #     ["SSTORE", 0, 1],
            #     ["CALL", 1000, paygas_contract_address, 0, 0, 0, 0, 0],
            #     ["SSTORE", 1, 1],
            # ],
            "code": (
                b"`\x01`\x00U`\x00`\x00`\x00`\x00`\x00s[p\xb7s\x88\xb4e\xf7R@w\xd2e\xfa\x1c{j\x9a"
                b"cya\x03\xe8\xf1P`\x01`\x01U"
            )
        }),
        paygas_contract,
    ]),
    expect(
        networks=["Sharding"],
        transaction={
            "to": address,
            "accessList": [
                [address, b""],
                [paygas_contract_address],
            ],
        },
        post_state=[
            storage_updated,
        ],
    )
))


paygas_fail_before_test = Test(pipe(
    setup_sharding_filler("PaygasFailBefore", environment={"currentCoinbase": coinbase}),
    pre_state({
        address: {
            "balance": 0,
            # "vyperLLLCode": [
            #     "seq",
            #     ["SSTORE", 0, 1],
            #     ["assert", 0],
            #     ["PAYGAS", 1],
            #     ["SSTORE", 1, 1],
            # ],
            "code": b"`\x01`\x00U`\x00a\x00\x0fW`\x00\x80\xfd[`\x01\xf5P`\x01`\x01U",
        }
    }),
    expect(
        networks=["Sharding"],
        transaction={
            "to": address,
            "accessList": [
                [address, b""],
            ],
        },
        post_state=None,
    )
))


paygas_fail_thereafter_test = Test(pipe(
    setup_sharding_filler("PaygasFailThereafter", environment={"currentCoinbase": coinbase}),
    pre_state({
        address: {
            "balance": 0,
            # "vyperLLLCode": [
            #     "seq",
            #     ["SSTORE", 0, 1],
            #     ["PAYGAS", 1],
            #     ["SSTORE", 1, 1],
            #     ["assert", 0],
            # ],
            "code": b"`\x01`\x00U`\x01\xf5P`\x01`\x01U`\x00a\x00\x18W`\x00\x80\xfd[",
        }
    }),
    expect(
        networks=["Sharding"],
        transaction={
            "to": address,
            "accessList": [
                [address, b""],
            ],
        },
        post_state=[
            (address, "balance", 0),
        ],
    )
))
