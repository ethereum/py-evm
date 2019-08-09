import pytest

from eth_utils import (
    encode_hex,
    ValidationError,
)

from trinity.plugins.builtin.syncer.cli import (
    parse_checkpoint_uri
)


@pytest.mark.parametrize(
    'uri, expected',
    (
        (
            'eth://block/byhash/0x113f05289c685eb5b87d433c3e09ec2bfa51d6472cc37108d03b0113b11e3080?score=11',  # noqa: E501
            ('0x113f05289c685eb5b87d433c3e09ec2bfa51d6472cc37108d03b0113b11e3080', 78, 11),
        ),
        (
            'eth://block/byhash/0x113f05289c685eb5b87d433c3e09ec2bfa51d6472cc37108d03b0113b11e3080?score=1,1',  # noqa: E501
            ('0x113f05289c685eb5b87d433c3e09ec2bfa51d6472cc37108d03b0113b11e3080', 78, 11),
        ),
        (
            'eth://block/byhash/0x113f05289c685eb5b87d433c3e09ec2bfa51d6472cc37108d03b0113b11e3080?score=1 1',  # noqa: E501
            ('0x113f05289c685eb5b87d433c3e09ec2bfa51d6472cc37108d03b0113b11e3080', 78, 11),
        ),
    )
)
def test_parse_checkpoint(uri, expected):
    block_hash, block_number, block_score = expected
    checkpoint = parse_checkpoint_uri(uri)
    assert encode_hex(checkpoint.block_hash) == block_hash
    assert checkpoint.score == block_score


@pytest.mark.parametrize(
    'uri',
    (
        'meh://block/byhash/0x113f05289c685eb5b87d433c3e09ec2bfa51d6472cc37108d03b0113b11e3080?score=11',  # noqa: E501
        'eth://meh/byhash/0x113f05289c685eb5b87d433c3e09ec2bfa51d6472cc37108d03b0113b11e3080?score=11',  # noqa: E501
        'eth://block/meh/0x113f05289c685eb5b87d433c3e09ec2bfa51d6472cc37108d03b0113b11e3080?score=11',  # noqa: E501
        'eth://block/byhash/meh?score=78',
        'eth://block/meh/0x113f05289c685eb5b87d433c3e09ec2bfa51d6472cc37108d03b0113b11e3080?score=11',  # noqa: E501
        'eth://block/meh/0x113f05289c685eb5b87d433c3e09ec2bfa51d6472cc37108d03b0113b11e3080?score=meh',  # noqa: E501
        'eth://block/byhash/0x113f05289c685eb5b87d433c3e09ec2bfa51d6472cc37108d03b0113b11e3080',
    )
)
def test_throws_validation_error(uri):
    with pytest.raises(ValidationError):
        parse_checkpoint_uri(uri)
