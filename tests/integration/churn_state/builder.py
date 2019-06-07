import itertools

from eth._utils.address import generate_contract_address
from eth_utils import decode_hex

from tests.core.integration_test_helpers import FUNDED_ACCT


def deploy_storage_churn_contract(chain):
    nonce = 0
    deploy_tx = chain.create_unsigned_transaction(
        nonce=nonce,
        gas_price=1234,
        gas=3000000,
        to=b'',
        value=0,
        data=decode_hex("608060405234801561001057600080fd5b50600160008080815260200190815260200160002081905550610336806100386000396000f3fe608060405234801561001057600080fd5b506004361061004c5760003560e01c80634903b0d114610051578063622ff59a14610093578063adbd8315146100c1578063ef6537b5146100ef575b600080fd5b61007d6004803603602081101561006757600080fd5b810190808035906020019092919050505061011d565b6040518082815260200191505060405180910390f35b6100bf600480360360208110156100a957600080fd5b8101908080359060200190929190505050610135565b005b6100ed600480360360208110156100d757600080fd5b810190808035906020019092919050505061020e565b005b61011b6004803603602081101561010557600080fd5b8101908080359060200190929190505050610265565b005b60006020528060005260406000206000915090505481565b3073ffffffffffffffffffffffffffffffffffffffff1663adbd8315826040518263ffffffff1660e01b815260040180828152602001915050600060405180830381600087803b15801561018857600080fd5b505af115801561019c573d6000803e3d6000fd5b505050503073ffffffffffffffffffffffffffffffffffffffff1663adbd8315826040518263ffffffff1660e01b815260040180828152602001915050600060405180830381600087803b1580156101f357600080fd5b505af1158015610207573d6000803e3d6000fd5b5050505050565b60008090505b81811015610260576000806000838152602001908152602001600020541115610253576000808281526020019081526020016000206000905550610262565b8080600101915050610214565b505b50565b60008090505b818110156102e457600160008083815260200190815260200160002054036000806001840181526020019081526020016000205414156102d757600080828152602001908152602001600020546000806001840181526020019081526020016000208190555050610307565b808060010191505061026b565b506001600080808152602001908152602001600020600082825401925050819055505b5056fea165627a7a72305820dba28f294357644493dce42aff2ea2bf5f72e20dcb00a6ed4094dd313bf8f5220029"),  # noqa: E501
    )
    chain.apply_transaction(deploy_tx.as_signed_transaction(FUNDED_ACCT))
    chain.mine_block()

    return generate_contract_address(FUNDED_ACCT.public_key.to_canonical_address(), nonce)


def update_churn(chain, contract_addr, start_nonce=1, num_blocks=20):
    nymph_addrs = []
    nonces = itertools.count(start_nonce)
    for _ in range(num_blocks):
        _churn_storage_once(chain, contract_addr, next(nonces))
        _churn_storage_once(chain, contract_addr, next(nonces))
        nymph_addrs.extend([
            _add_nymph_contract(chain, next(nonces)),
            _add_nymph_contract(chain, next(nonces)),
        ])
        chain.mine_block()
    return nymph_addrs, next(nonces)


def delete_churn(chain, nymph_addresses, contract_addr, start_nonce=1, num_blocks=20):
    # do two deletes per block to try to catch some funky scenarios like:
    # account (or storage) delete success then rollback due to follow-up delete failure
    nonces = itertools.count(start_nonce)
    for _ in range(num_blocks):
        _delete_storage_twice(chain, contract_addr, next(nonces))
        if len(nymph_addresses) >= 2:
            nymph_to_delete = nymph_addresses.pop()
            _delete_nymph(chain, nymph_to_delete, next(nonces))
            nymph_to_delete = nymph_addresses.pop()
            _delete_nymph(chain, nymph_to_delete, next(nonces))
        chain.mine_block()
    return nymph_addresses


def _churn_storage_once(chain, contract_addr, nonce):
    # invoke function shuffle the storage, with a width of 64
    # shuffle(uint256)
    func_id = decode_hex("0xef6537b5")
    # width is how many different storage slots to fill before wrapping
    width = b'\x40'
    # join call with parameters and pad:
    method_invocation = func_id + width.rjust(32, b'\0')

    tx = chain.create_unsigned_transaction(
        nonce=nonce,
        gas_price=1234,
        gas=123456,
        to=contract_addr,
        value=0,
        data=method_invocation,
    )
    _, _, computation = chain.apply_transaction(tx.as_signed_transaction(FUNDED_ACCT))
    assert computation.is_success


def _add_nymph_contract(chain, nonce):
    deploy_tx = chain.create_unsigned_transaction(
        nonce=nonce,
        gas_price=1234,
        gas=123457,
        to=b'',
        value=0,
        data=decode_hex("6080604052348015600f57600080fd5b50607a8061001e6000396000f3fe6080604052348015600f57600080fd5b506004361060285760003560e01c80635969aa8414602d575b600080fd5b60336035565b005b3373ffffffffffffffffffffffffffffffffffffffff16fffea165627a7a72305820cc81a4355ab2bb255e1233528ced5013be67280d530689ba007ed9f206230c740029"),  # noqa: E501
    )
    _, _, computation = chain.apply_transaction(deploy_tx.as_signed_transaction(FUNDED_ACCT))
    assert computation.is_success

    return generate_contract_address(FUNDED_ACCT.public_key.to_canonical_address(), nonce)


def _delete_storage_twice(chain, contract_addr, nonce):
    # invoke function shuffle the storage, with a width of 64
    # delete_twice(uint256)
    func_id = decode_hex("0x622ff59a")
    # width is how many different storage slots might be deletable
    width = b'\x40'
    # join call with parameters and pad:
    method_invocation = func_id + width.rjust(32, b'\0')

    tx = chain.create_unsigned_transaction(
        nonce=nonce,
        gas_price=1235,
        gas=123458,
        to=contract_addr,
        value=0,
        data=method_invocation,
    )
    _, _, computation = chain.apply_transaction(tx.as_signed_transaction(FUNDED_ACCT))
    assert computation.is_success


def _delete_nymph(chain, contract_addr, nonce):
    # invoke function shuffle the storage, with a width of 64
    # poof()
    func_id = decode_hex("0x5969aa84")

    tx = chain.create_unsigned_transaction(
        nonce=nonce,
        gas_price=1235,
        gas=123459,
        to=contract_addr,
        value=0,
        data=func_id,
    )
    _, _, computation = chain.apply_transaction(tx.as_signed_transaction(FUNDED_ACCT))
    assert computation.is_success
