from cytoolz import (
    pipe,
)

from evm.tools.test_builder.test_builder import (
    Test,
    setup_sharding_filler,
    pre_state,
    expect,
)

from evm.tools.test_builder.builder_utils import (
    generate_random_address,
)


address = generate_random_address()
normal_contract_address = b"`\xa8\xdc~\xba\xd7\x03\x8c\x9a\x83}\x84\xd8\x13\xa8R\x92\xe5d\xbd"
paygas_contract_address = b"[p\xb7s\x88\xb4e\xf7R@w\xd2e\xfa\x1c{j\x9acy"
assert address != normal_contract_address


storage_updated = (address, "storage", {
    0: 1,
    1: 1,
})

paygas_successful = (address, "storage", 2, 2)  # return code + 1
paygas_failed = (address, "storage", 2, 1)  # return code + 1
second_paygas_failed = (address, "storage", 3, 1)

normal_contract = (normal_contract_address, {
    # "vyperLLLCode": ["seq", ["MSTORE", 0, 1], ["RETURN", 0, 32]],
    "code": b"`\x01`\x00R` `\x00\xf3",
})
paygas_contract = (normal_contract_address, {
    # "vyperLLLCode": ["seq", ["MSTORE", 0, ["ADD", 1, ["PAYGAS", 1]]], ["RETURN", 0, 32]],
    "code": b"`\x01\xf5`\x01\x01`\x00R` `\x00\xf3",
    "balance": 1000000,
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
            #     ["SSTORE", 2, ["ADD", 1, ["PAYGAS", 1]]],
            #     ["SSTORE", 1, 1],
            # ],
            "code": b"`\x01`\x00U`\x01\xf5`\x01\x01`\x02U`\x01`\x01U",
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
            paygas_successful,
            (address, "balance", 18973),
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
            #     ["SSTORE", 2, ["ADD", 1, ["PAYGAS", 0]]],
            #     ["SSTORE", 1, 1],
            # ],
            "code": b"`\x01`\x00U`\x00\xf5`\x01\x01`\x02U`\x01`\x01U",
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
            paygas_successful,
        ]
    )
))


paygas_repeated_test = Test(pipe(
    setup_sharding_filler("PaygasRepeated"),
    pre_state({
        address: {
            "balance": 200000,
            # "vyperLLLCode": [
            #     "seq",
            #     ["SSTORE", 0, 1],
            #     ["SSTORE", 2, ["ADD", 1, ["PAYGAS", 1]]],
            #     ["SSTORE", 3, ["ADD", 1, ["PAYGAS", 2]]],
            #     ["SSTORE", 1, 1],
            # ],
            "code": b"`\x01`\x00U`\x01\xf5`\x01\x01`\x02U`\x02\xf5`\x01\x01`\x03U`\x01`\x01U",
        }
    }),
    expect(
        networks=["Sharding"],
        transaction={
            "to": address,
            "accessList": [
                [address, b""],
            ],
            "gasLimit": 200000,
        },
        post_state=[
            storage_updated,
            paygas_successful,
            second_paygas_failed,
            (address, "balance", 98958),
        ],
    )
))


paygas_repeated_same_gasprice_test = Test(pipe(
    setup_sharding_filler("PaygasRepeatedSameGasprice"),
    pre_state({
        address: {
            "balance": 200000,
            # "vyperLLLCode": [
            #     "seq",
            #     ["SSTORE", 0, 1],
            #     ["SSTORE", 2, ["ADD", 1, ["PAYGAS", 1]]],
            #     ["SSTORE", 3, ["ADD", 1, ["PAYGAS", 1]]],
            #     ["SSTORE", 1, 1],
            # ],
            "code": b"`\x01`\x00U`\x01\xf5`\x01\x01`\x02U`\x01\xf5`\x01\x01`\x03U`\x01`\x01U",
        }
    }),
    expect(
        networks=["Sharding"],
        transaction={
            "to": address,
            "accessList": [
                [address, b""],
            ],
            "gasLimit": 200000,
        },
        post_state=[
            storage_updated,
            paygas_successful,
            second_paygas_failed,
            (address, "balance", 98958),
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
            #     ["SSTORE", 2, ["ADD", 1, ["PAYGAS", 1]]],
            #     ["SSTORE", 1, 1],
            # ],
            "code": b"`\x01`\x00U`\x01\xf5`\x01\x01`\x02U`\x01`\x01U",
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
            "balance": 100000,
            # "vyperLLLCode": [
            #     "seq",
            #     ["SSTORE", 0, 1],
            #     ["CALL", 1000, normal_contract_address, 0, 0, 0, 0, 0],
            #     ["SSTORE", 2, ["ADD", 1, ["PAYGAS", 1]]],
            #     ["SSTORE", 1, 1],
            #     ["RETURN", 0, 32]
            # ],
            "code": (
                b"`\x01`\x00U`\x00`\x00`\x00`\x00`\x00s`\xa8\xdc~\xba\xd7\x03\x8c\x9a\x83}\x84\xd8"
                b"\x13\xa8R\x92\xe5d\xbda\x03\xe8\xf1P`\x01\xf5`\x01\x01`\x02U`\x01`\x01U` `\x00"
                b"\xf3"
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
            paygas_successful,
            (address, "balance", 18223),
        ]
    )
))


paygas_in_call_test = Test(pipe(
    setup_sharding_filler("PaygasInCall"),
    pre_state([
        (address, {
            "balance": 200000,
            # "vyperLLLCode": [
            #     "seq",
            #     ["SSTORE", 0, 1],
            #     ["SSTORE", 2, ["CALL", 1000, paygas_contract_address, 0, 0, 0, 0, 32]],
            #     ["SSTORE", 1, 1],
            #     ["RETURN", 0, 32],
            # ],
            "code": (
                b"`\x01`\x00U` `\x00`\x00`\x00`\x00s[p\xb7s\x88\xb4e\xf7R@w\xd2e\xfa\x1c{j\x9acya"
                b"\x03\xe8\xf1`\x02U`\x01`\x01U` `\x00\xf3"
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
            "gasLimit": 200000,
        },
        post_state=[
            storage_updated,
            paygas_failed,
            (address, "balance", 200000),
        ],
    )
))


paygas_fail_before_test = Test(pipe(
    setup_sharding_filler("PaygasFailBefore"),
    pre_state({
        address: {
            "balance": 100000,
            # "vyperLLLCode": [
            #     "seq",
            #     ["SSTORE", 0, 1],
            #     ["assert", 0],
            #     ["SSTORE", 2, ["ADD", 1, ["PAYGAS", 1]]],
            #     ["SSTORE", 1, 1],
            # ],
            "code": b"`\x01`\x00U`\x00a\x00\x0fW`\x00\x80\xfd[`\x01\xf5`\x01\x01`\x02U`\x01`\x01U",
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
    setup_sharding_filler("PaygasFailThereafter"),
    pre_state({
        address: {
            "balance": 100000,
            # "vyperLLLCode": [
            #     "seq",
            #     ["SSTORE", 0, 1],
            #     ["SSTORE", 2, ["ADD", 1, ["PAYGAS", 1]]],
            #     ["SSTORE", 1, 1],
            #     ["assert", 0],
            # ],
            "code": b"`\x01`\x00U`\x01\xf5`\x01\x01`\x02U`\x01`\x01U`\x00a\x00\x1dW`\x00\x80\xfd[",
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
            (address, "balance", 18951),
        ],
    )
))


paygas_survives_revert_test = Test(pipe(
    setup_sharding_filler("PaygasFailThereafter"),
    pre_state({
        address: {
            "balance": 100000,
            # "vyperLLLCode": [
            #     "seq",
            #     ["SSTORE", 0, 1],
            #     ["SSTORE", 2, ["ADD", 1, ["PAYGAS", 1]]],
            #     ["SSTORE", 1, 1],
            #     ["revert", 0, 0],
            # ],
            "code": b"`\x01`\x00U`\x01\xf5`\x01\x01`\x02U`\x01`\x01U`\x00`\x00\xfd",
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
            (address, "balance", 38958),
        ],
    )
))
