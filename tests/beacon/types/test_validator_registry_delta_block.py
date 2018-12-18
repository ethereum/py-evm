from eth.beacon.types.validator_registry_delta_block import (
    ValidatorRegistryDeltaBlock,
)


def test_defaults(sample_validator_registry_delta_block_params):
    validator_registry_delta_block = ValidatorRegistryDeltaBlock(
        **sample_validator_registry_delta_block_params
    )
    assert validator_registry_delta_block.latest_registry_delta_root == sample_validator_registry_delta_block_params['latest_registry_delta_root']  # noqa: E501
    assert validator_registry_delta_block.validator_index == sample_validator_registry_delta_block_params['validator_index']  # noqa: E501
    assert validator_registry_delta_block.pubkey == sample_validator_registry_delta_block_params['pubkey']  # noqa: E501
    assert validator_registry_delta_block.flag == sample_validator_registry_delta_block_params['flag']  # noqa: E501
