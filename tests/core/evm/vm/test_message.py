from __future__ import unicode_literals
import pytest
import evm.vm.message as m
from evm.constants import (
    CREATE_CONTRACT_ADDRESS,
)

ADDRESS = b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff"
TEST_ADDRESS = b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xf9"

def _create_message(
    create_address=None,
    gas=1,
    gas_price=1,
    to=ADDRESS,
    sender=ADDRESS,
    value=1,
    data=b"",
    code=b"",
    origin=ADDRESS):
    return m.Message(
        gas=gas,
        gas_price=gas_price,
        to=to, sender=sender,
        value=value,
        data=data,
        code=code,
        origin=origin,
        create_address=create_address
        )

def test_initializes_properly():
    """
    # all __init__ parameters are properly validated.
    """
    #TODO: Needs proper tests here

def test_is_origin():
    #correctly returns True/False for whether this message is the origin message
    assert _create_message().is_origin == True

@pytest.mark.parametrize(
    "origin,sender,should_be_origin",
    (
        (ADDRESS, TEST_ADDRESS, False),  # tests that when they are diffrent, it isn't the origin message.
        (ADDRESS, ADDRESS, True),  # tests that when they are the same, it is the origin message.
    )
)
def test_computed_is_origin_property(origin, sender, should_be_origin):
    message = _create_message(sender=sender, origin=origin)
    assert message.is_origin is should_be_origin

def test_code_address():
    """
    returns correct value when to address is set to CREATE_CONTRACT_ADDRESS.
    """
    assert _create_message(to=CREATE_CONTRACT_ADDRESS).code_address == CREATE_CONTRACT_ADDRESS

def test_storage_address():
    """
    returns correct value when message is performing contract creation.
    """
    assert _create_message(create_address=TEST_ADDRESS).storage_address == TEST_ADDRESS

@pytest.mark.parametrize(
    "address,is_valid",
    (
        (ADDRESS, False),  # tests that is_create is False when 'to' != CREATE_CONTRACT_ADDRESS
        (CREATE_CONTRACT_ADDRESS, True),  # tests is_create is True when 'to'== CREATE_CONTRACT_ADDRESS.
    )
)
def test_is_create(address,is_valid):
    """
    returns True when message is for contract creation.
    """
    assert _create_message(to=address).is_create is is_valid
