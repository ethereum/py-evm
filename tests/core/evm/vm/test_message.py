from __future__ import unicode_literals
import pytest
import evm.vm.message as m


def _create_message(gas=1, gas_price=1, to=b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff", sender=b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff", value=1, data=b"", code=b"", origin="\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff"):
    return m.Message(gas=gas, gas_price=gas_price, to=to, sender=sender, value=value, data=data, code=code, origin=origin)

# def test_initializes_properly():
#     """
#     # all __init__ parameters are properly validated.
#     """
#     assert 

# def test_is_origin():
#     #correctly returns True/False for whether this message is the origin message
#     assert _create_message().is_origin == True

# def test_origin():
#     #property returns correct value.
#     assert _create_message().origin == "\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff"
