import pytest
import evm.vm.message as m

message_object = m.Message(
    1,                      #gas
    1,                      #gas_price
    b'',                    #to
    '11111111111111111111', #sender
    1,                      #value
    '',                     #data
    'asdf',                 #code
    '22222222222222222222'  #origin
    )                    

def test_initilizes_properly():
    # all __init__ parameters are properly validated.
    assert message_object.gas == 1
    assert message_object.gas_price == 1
    assert message_object.to == b''
    assert message_object.sender == '11111111111111111111'
    assert message_object.value == 1
    assert message_object.data == ''
    assert message_object.code == 'asdf'
    assert message_object.origin == '22222222222222222222'

def test_is_origin():
    #correctly returns True/False for whether this message is the origin message
    assert message_object.is_origin == False

def origin():
    #property returns correct value.
    assert message_object.origin == '22222222222222222222'