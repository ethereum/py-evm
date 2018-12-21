import pytest

from eth.vm.forks import (
    TangerineWhistleVM,
    FrontierVM,
    HomesteadVM,
    SpuriousDragonVM,
    ByzantiumVM,
    ConstantinopleVM,
)

from trinity._utils.eip1085 import extract_vm_configuration


def wrap_config(v):
    return {'params': v}


CONSTANTINOPLE_AT_0 = wrap_config({
    "homesteadForkBlock": "0x00",
    "EIP150ForkBlock": "0x00",
    "EIP158ForkBlock": "0x00",
    "byzantiumForkBlock": "0x00",
    "constantinopleForkBlock": "0x00",
})
CONSTANTINOPLE_AT_0_CONFIG = (
    (0, ConstantinopleVM),
)

CONSTANTINOPLE_AT_5 = wrap_config({
    "homesteadForkBlock": "0x00",
    "EIP150ForkBlock": "0x00",
    "EIP158ForkBlock": "0x00",
    "byzantiumForkBlock": "0x00",
    "constantinopleForkBlock": "0x05",
})
CONSTANTINOPLE_AT_5_CONFIG = (
    (0, ByzantiumVM),
    (5, ConstantinopleVM),
)

BYZANTIUM_AT_0 = wrap_config({
    "homesteadForkBlock": "0x00",
    "EIP150ForkBlock": "0x00",
    "EIP158ForkBlock": "0x00",
    "byzantiumForkBlock": "0x00",
})
BYZANTIUM_AT_0_CONFIG = (
    (0, ByzantiumVM),
)

BYZANTIUM_AT_5 = wrap_config({
    "homesteadForkBlock": "0x00",
    "EIP150ForkBlock": "0x00",
    "EIP158ForkBlock": "0x00",
    "byzantiumForkBlock": "0x05",
})
BYZANTIUM_AT_5_CONFIG = (
    (0, SpuriousDragonVM),
    (5, ByzantiumVM),
)

SPURIOUS_AT_0 = wrap_config({
    "homesteadForkBlock": "0x00",
    "EIP150ForkBlock": "0x00",
    "EIP158ForkBlock": "0x00",
})
SPURIOUS_AT_0_CONFIG = (
    (0, SpuriousDragonVM),
)

SPURIOUS_AT_5 = wrap_config({
    "homesteadForkBlock": "0x00",
    "EIP150ForkBlock": "0x00",
    "EIP158ForkBlock": "0x05",
})
SPURIOUS_AT_5_CONFIG = (
    (0, TangerineWhistleVM),
    (5, SpuriousDragonVM),
)

TANGERINE_AT_0 = wrap_config({
    "homesteadForkBlock": "0x00",
    "EIP150ForkBlock": "0x00",
})
TANGERINE_AT_0_CONFIG = (
    (0, TangerineWhistleVM),
)

TANGERINE_AT_5 = wrap_config({
    "homesteadForkBlock": "0x00",
    "EIP150ForkBlock": "0x05",
})
TANGERINE_AT_5_CONFIG = (
    (0, HomesteadVM),
    (5, TangerineWhistleVM),
)

HOMESTEAD_AT_0 = wrap_config({
    "homesteadForkBlock": "0x00",
})
HOMESTEAD_AT_0_CONFIG = (
    (0, HomesteadVM),
)

HOMESTEAD_AT_5 = wrap_config({
    "homesteadForkBlock": "0x05",
})
HOMESTEAD_AT_5_CONFIG = (
    (0, FrontierVM),
    (5, HomesteadVM),
)

FRONTIER_AT_0 = wrap_config({
    "frontierForkBlock": "0x00",
})
FRONTIER_AT_0_CONFIG = (
    (0, FrontierVM),
)


@pytest.mark.parametrize(
    'genesis_config,expected',
    (
        (CONSTANTINOPLE_AT_0, CONSTANTINOPLE_AT_0_CONFIG),
        (CONSTANTINOPLE_AT_5, CONSTANTINOPLE_AT_5_CONFIG),
        (BYZANTIUM_AT_0, BYZANTIUM_AT_0_CONFIG),
        (BYZANTIUM_AT_5, BYZANTIUM_AT_5_CONFIG),
        (SPURIOUS_AT_0, SPURIOUS_AT_0_CONFIG),
        (SPURIOUS_AT_5, SPURIOUS_AT_5_CONFIG),
        (TANGERINE_AT_0, TANGERINE_AT_0_CONFIG),
        (TANGERINE_AT_5, TANGERINE_AT_5_CONFIG),
        (HOMESTEAD_AT_0, HOMESTEAD_AT_0_CONFIG),
        (HOMESTEAD_AT_5, HOMESTEAD_AT_5_CONFIG),
        (FRONTIER_AT_0, FRONTIER_AT_0_CONFIG),
    ),
)
def test_eip1085_extract_vm_configuration(genesis_config, expected):
    actual = extract_vm_configuration(genesis_config)
    assert actual == expected
