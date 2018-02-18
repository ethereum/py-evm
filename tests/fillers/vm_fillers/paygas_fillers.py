from cytoolz import (
    pipe,
)

from evm.utils.test_builder.test_builder import (
    setup_filler,
    pre_state,
    execution,
    expect,
)

from evm.utils.test_builder.builder_utils import (
    generate_random_address,
)


address = generate_random_address()
caller = generate_random_address()
normal_contract_address = generate_random_address()
paygas_contract_address = generate_random_address()


expect_success = expect(post_state=[(address, "storage", {
    0: 1,
    1: 1,
})])
expect_failure = expect(post_state=[(address, "storage", {
    0: 0,
    1: 0,
})])

broke_caller = (caller, "balance", 0)
solvent_caller = (caller, "balance", 1000000)
normal_contract = (normal_contract_address, {
    # "vyperLLLCode": ["seq", ["MSTORE", 0, 1], ["RETURN", 0, 32]],
    "code": b"",
})
paygas_contract = (normal_contract_address, {
    # "vyperLLLCode": ["PAYGAS", 0],
    "code": b"",
})


paygas_omitted_filler = pipe(
    setup_filler("PaygasOmitted"),
    pre_state([broke_caller]),
    execution({
        # "vyperLLLCode": ["SSTORE", 0, 1],
        "code": b"`\x01`\x00U",
    }),
    expect_success,
)


paygas_normal_filler = pipe(
    setup_filler("PaygasNormal"),
    pre_state([solvent_caller]),
    execution({
        # "vyperLLLCode": ["seq", ["SSTORE", 0, 1], ["PAYGAS", 1], ["SSTORE", 1, 1]],
        "code": b"",
    }),
    expect_success,
)


paygas_repeated_filler = pipe(
    setup_filler("PaygasRepeated"),
    pre_state([solvent_caller]),
    execution({
        # "vyperLLLCode": [
        #     "seq",
        #     ["SSTORE", 0, 1],
        #     ["PAYGAS", 0],
        #     ["PAYGAS", 1],
        #     ["SSTORE", 1, 1]
        # ],
        "code": b"",
    }),
    expect_failure,
)


paygas_repeated_same_gasprice_filler = pipe(
    setup_filler("PaygasRepeatedSameGasprice"),
    pre_state([solvent_caller]),
    execution({
        # "vyperLLLCode": [
        #     "seq",
        #     ["SSTORE", 0, 1],
        #     ["PAYGAS", 0],
        #     ["PAYGAS", 0],
        #     ["SSTORE", 1, 1]
        # ],
        "code": b"",
    }),
    expect_failure,
)


paygas_zero_gasprice_filler = pipe(
    setup_filler("PaygasZeroGasprice"),
    pre_state([broke_caller]),
    execution({
        # "vyperLLLCode": ["seq", ["SSTORE", 0, 1], ["PAYGAS", 0], ["SSTORE", 1, 1]],
        "code": b"",
    }),
    expect_success,
)


paygas_insufficient_balance_filler = pipe(
    setup_filler("PaygasNormal"),
    pre_state([broke_caller]),
    execution({
        # "vyperLLLCode": ["seq", ["SSTORE", 0, 1], ["PAYGAS", 1], ["SSTORE", 1, 1]],
        "code": b"`",
    }),
    expect_failure,
)


paygas_after_call = pipe(
    setup_filler("PaygasAfterCall"),
    pre_state([
        solvent_caller,
        normal_contract,
    ]),
    execution({
        # "vyperLLLCode": [
        #     "seq",
        #     ["SSTORE", 0, 1],
        #     ["CALL", 1000, normal_contract_address, 0, 0, 0, 0, 0],
        #     ["PAYGAS", 0],
        #     ["SSTORE", 1, 1],
        # ],
        "code": b"",
    }),
    expect_success,
)


paygas_in_call_filler = pipe(
    setup_filler("PaygasInCallFiller"),
    pre_state([
        solvent_caller,
        paygas_contract,
    ]),
    execution({
        # "vyperLLLCode": [
        #     "seq",
        #     ["SSTORE", 0, 1],
        #     ["CALL", 1000, paygas_contract_address, 0, 0, 0, 0, 0],
        #     ["SSTORE", 1, 1],
        # ],
        "code": b"",
    }),
    expect_failure,
)
