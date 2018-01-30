import functools
import logging

from cytoolz import (
    pipe,
)

import pytest

import rlp

from eth_tester.exceptions import (
    TransactionFailed,
    ValidationError,
)

from eth_tester.backends.pyevm.main import (
    get_default_account_keys,
)

from eth_utils import (
    to_checksum_address,
    to_tuple,
)

from eth_keys import (
    keys,
)

from evm.utils.address import (
    generate_contract_address,
)
from evm.utils.hexadecimal import (
    decode_hex,
    encode_hex,
)
from evm.utils.keccak import (
    keccak,
)

from evm.vm.forks.spurious_dragon.transactions import (
    SpuriousDragonTransaction,
)

from evm.vm.forks.sharding.vmc_utils import (
    create_vmc_tx,
)
from evm.vm.forks.sharding.vmc_handler import (
    NextLogUnavailable,
    parse_collation_added_data,
)

from tests.sharding.fixtures import (  # noqa: F401
    vmc,
)


PASSPHRASE = '123'
ZERO_ADDR = b'\x00' * 20
# for testing we set it to 5, 25 or 2500 originally
SHUFFLING_CYCLE_LENGTH = 25
WITHDRAW_HASH = keccak(b"withdraw")

test_keys = get_default_account_keys()

logger = logging.getLogger('evm.chain.sharding.mainchain_handler.VMCHandler')


def get_code(vmc_handler, address):
    return vmc_handler.web3.eth.getCode(to_checksum_address(address))


def get_nonce(vmc_handler, address):
    return vmc_handler.web3.eth.getTransactionCount(to_checksum_address(address))


def mine(vmc_handler, num_blocks):
    vmc_handler.web3.testing.mine(num_blocks)


def send_raw_transaction(vmc_handler, raw_transaction):
    w3 = vmc_handler.web3
    raw_transaction_bytes = rlp.encode(raw_transaction)
    raw_transaction_hex = w3.toHex(raw_transaction_bytes)
    transaction_hash = w3.eth.sendRawTransaction(raw_transaction_hex)
    return transaction_hash


def deploy_contract(vmc_handler,
                    bytecode,
                    privkey,
                    value,
                    gas,
                    gas_price):
    w3 = vmc_handler.web3
    contract_transaction_dict = {
        'nonce': get_nonce(vmc_handler, privkey.public_key.to_canonical_address()),
        'to': b'',  # CREATE_CONTRACT_ADDRESS
        'data': encode_hex(bytecode),
        'value': value,
        'gas': gas,
        'gasPrice': gas_price,
        'chainId': None,
    }
    signed_transaction_dict = w3.eth.account.signTransaction(
        contract_transaction_dict,
        privkey.to_hex(),
    )
    tx_hash = w3.eth.sendRawTransaction(signed_transaction_dict['rawTransaction'])
    return tx_hash


# vmc related

def is_vmc_deployed(vmc_handler):
    return (
        get_code(vmc_handler, vmc_handler.address) != b'' and
        get_nonce(vmc_handler, vmc_handler.vmc_tx_sender_address) != 0
    )


def mk_validation_code(address):
    """
    validation_code = '''
~calldatacopy(0, 0, 128)
~call(3000, 1, 0, 0, 128, 0, 32)
return(~mload(0) == {})
    '''.format(utils.checksum_encode(address))
    return serpent.compile(validation_code)
    """
    # The precompiled bytecode of the validation code which
    # verifies EC signatures
    validation_code_bytecode = b"a\x009\x80a\x00\x0e`\x009a\x00GV`\x80`\x00`\x007` "
    validation_code_bytecode += b"`\x00`\x80`\x00`\x00`\x01a\x0b\xb8\xf1Ps"
    validation_code_bytecode += address
    validation_code_bytecode += b"`\x00Q\x14` R` ` \xf3[`\x00\xf3"
    return validation_code_bytecode


def sign(message, privkey):
    """@privkey: Key type
    """
    signature = keys.ecdsa_sign(message, privkey)
    v, r, s = signature.vrs
    v += 27
    signature_bytes = b''.join([item.to_bytes(32, 'big') for item in (v, r, s)])
    return signature_bytes


def create_transaction_from_hex(raw_transaction_hex, TransactionClass):
    return pipe(
        raw_transaction_hex,
        decode_hex,
        functools.partial(rlp.decode, sedes=TransactionClass),
    )


def create_sighasher_tx(TransactionClass):
    sighasher_tx_hex = "0xf9016d808506fc23ac0083026a508080b9015a6101488061000e6000396101565660007f01000000000000000000000000000000000000000000000000000000000000006000350460f8811215610038576001915061003f565b60f6810391505b508060005b368312156100c8577f01000000000000000000000000000000000000000000000000000000000000008335048391506080811215610087576001840193506100c2565b60b881121561009d57607f8103840193506100c1565b60c08112156100c05760b68103600185013560b783036020035260005101840193505b5b5b50610044565b81810360388112156100f4578060c00160005380836001378060010160002060e052602060e0f3610143565b61010081121561010557600161011b565b6201000081121561011757600261011a565b60035b5b8160005280601f038160f701815382856020378282600101018120610140526020610140f350505b505050505b6000f31b2d4f"  # noqa: E501
    return create_transaction_from_hex(sighasher_tx_hex, TransactionClass)


def create_viper_rlp_decoder_tx(TransactionClass):
    # TODO: the RLPList in the new `rlp_decoder_tx_hex` doesn't work fine, so for now use the old
    # one. address=0xCb969cAAad21A78a24083164ffa81604317Ab603
    viper_rlp_decoder_tx_hex = "0xf90237808506fc23ac00830330888080b902246102128061000e60003961022056600060007f010000000000000000000000000000000000000000000000000000000000000060003504600060c082121515585760f882121561004d5760bf820336141558576001905061006e565b600181013560f783036020035260005160f6830301361415585760f6820390505b5b368112156101c2577f010000000000000000000000000000000000000000000000000000000000000081350483602086026040015260018501945060808112156100d55760018461044001526001828561046001376001820191506021840193506101bc565b60b881121561014357608081038461044001526080810360018301856104600137608181141561012e5760807f010000000000000000000000000000000000000000000000000000000000000060018401350412151558575b607f81038201915060608103840193506101bb565b60c08112156101b857600182013560b782036020035260005160388112157f010000000000000000000000000000000000000000000000000000000000000060018501350402155857808561044001528060b6838501038661046001378060b6830301830192506020810185019450506101ba565bfe5b5b5b5061006f565b601f841315155857602060208502016020810391505b6000821215156101fc578082604001510182826104400301526020820391506101d8565b808401610420528381018161044003f350505050505b6000f31b2d4f"  # noqa: E501
    # new one but for now not working fine. address=0x6b2A423C7915e984ebCD3aD2B86ba815A7D4ae6d
    # viper_rlp_decoder_tx_hex = 0xf9035b808506fc23ac0083045ef88080b903486103305660006109ac5260006109cc527f0100000000000000000000000000000000000000000000000000000000000000600035046109ec526000610a0c5260006109005260c06109ec51101515585760f86109ec51101561006e5760bf6109ec510336141558576001610a0c52610098565b60013560f76109ec51036020035260005160f66109ec510301361415585760f66109ec5103610a0c525b61010060016064818352015b36610a0c511015156100b557610291565b7f0100000000000000000000000000000000000000000000000000000000000000610a0c5135046109ec526109cc5160206109ac51026040015260016109ac51016109ac5260806109ec51101561013b5760016109cc5161044001526001610a0c516109cc5161046001376001610a0c5101610a0c5260216109cc51016109cc52610281565b60b86109ec5110156101d15760806109ec51036109cc51610440015260806109ec51036001610a0c51016109cc51610460013760816109ec5114156101ac5760807f01000000000000000000000000000000000000000000000000000000000000006001610a0c5101350410151558575b607f6109ec5103610a0c5101610a0c5260606109ec51036109cc51016109cc52610280565b60c06109ec51101561027d576001610a0c51013560b76109ec510360200352600051610a2c526038610a2c5110157f01000000000000000000000000000000000000000000000000000000000000006001610a0c5101350402155857610a2c516109cc516104400152610a2c5160b66109ec5103610a0c51016109cc516104600137610a2c5160b66109ec5103610a0c510101610a0c526020610a2c51016109cc51016109cc5261027f565bfe5b5b5b81516001018083528114156100a4575b5050601f6109ac511115155857602060206109ac5102016109005260206109005103610a0c5261010060016064818352015b6000610a0c5112156102d45761030a565b61090051610a0c516040015101610a0c51610900516104400301526020610a0c5103610a0c5281516001018083528114156102c3575b50506109cc516109005101610420526109cc5161090051016109005161044003f35b61000461033003610004600039610004610330036000f31b2d4f   # noqa: E501
    return create_transaction_from_hex(viper_rlp_decoder_tx_hex, TransactionClass)


@to_tuple
def mk_initiating_contracts(sender_privkey,
                            sender_starting_nonce,
                            TransactionClass,
                            gas_price):
    """Make transactions of createing initial contracts
    Including rlp_decoder, sighasher and validator_manager
    """
    nonce = sender_starting_nonce

    viper_rlp_decoder_tx = create_viper_rlp_decoder_tx(TransactionClass)
    sighasher_tx = create_sighasher_tx(TransactionClass)
    vmc_tx = create_vmc_tx(TransactionClass, gas_price=gas_price)

    # the sender gives all senders of the txs money, and append the
    # money-giving tx with the original tx to the return list
    for tx in (viper_rlp_decoder_tx, sighasher_tx, vmc_tx):
        funding_tx_for_tx_sender = TransactionClass.create_unsigned_transaction(
            nonce,
            gas_price,
            500000,
            tx.sender,
            tx.gas * tx.gas_price + tx.value,
            b'',
        ).as_signed_transaction(sender_privkey)
        nonce += 1
        yield funding_tx_for_tx_sender
    for tx in (viper_rlp_decoder_tx, sighasher_tx, vmc_tx):
        yield tx


def do_withdraw(vmc_handler, validator_index):
    assert validator_index < len(test_keys)
    privkey = test_keys[validator_index]
    signature = sign(WITHDRAW_HASH, privkey)
    vmc_handler.withdraw(validator_index, signature)
    mine(vmc_handler, 1)


def deploy_valcode_and_deposit(vmc_handler, privkey):
    """
    Deploy validation code of and with the privkey, and do deposit

    :param privkey: PrivateKey object
    :return: returns nothing
    """
    address = privkey.public_key.to_canonical_address()
    valcode = mk_validation_code(
        privkey.public_key.to_canonical_address()
    )
    nonce = get_nonce(vmc_handler, address)
    valcode_addr = generate_contract_address(address, nonce)
    deploy_contract(
        vmc_handler,
        valcode,
        privkey,
        value=0,
        gas=vmc_handler.config['DEFAULT_GAS'],
        gas_price=vmc_handler.config['GAS_PRICE'],
    )
    mine(vmc_handler, 1)
    vmc_handler.deposit(valcode_addr, address)
    return valcode_addr


def deploy_initiating_contracts(vmc_handler, privkey):
    w3 = vmc_handler.web3
    nonce = get_nonce(vmc_handler, privkey.public_key.to_canonical_address())
    txs = mk_initiating_contracts(
        privkey,
        nonce,
        SpuriousDragonTransaction,
        vmc_handler.config['GAS_PRICE'],
    )
    for tx in txs[:3]:
        send_raw_transaction(vmc_handler, tx)
    mine(vmc_handler, 1)
    for tx in txs[3:]:
        send_raw_transaction(vmc_handler, tx)
        mine(vmc_handler, 1)
    logger.debug(
        'deploy_initiating_contracts: vmc_tx_hash=%s',
        w3.eth.getTransactionReceipt(encode_hex(txs[-1].hash)),
    )


def import_key(vmc_handler, privkey):
    """
    :param vmc_handler: VMCHandler
    :param privkey: PrivateKey object from eth_keys
    """
    try:
        vmc_handler.web3.personal.importRawKey(privkey.to_hex(), PASSPHRASE)
    # Exceptions happen when the key is already imported.
    #   - ValueError: `web3.py`
    #   - ValidationError: `eth_tester`
    except (ValueError, ValidationError):
        pass


def mk_testing_colhdr(vmc_handler,
                      shard_id,
                      parent_collation_hash,
                      number,
                      collation_coinbase=test_keys[0].public_key.to_canonical_address(),
                      privkey=test_keys[0]):
    period_length = vmc_handler.config['PERIOD_LENGTH']
    current_block_number = vmc_handler.web3.eth.blockNumber
    expected_period_number = (current_block_number + 1) // period_length
    logger.debug("mk_testing_colhdr: expected_period_number=%s", expected_period_number)
    sender_addr = privkey.public_key.to_canonical_address()
    period_start_prevhash = vmc_handler.call(
        vmc_handler.mk_contract_tx_detail(
            sender_address=sender_addr,
            gas=vmc_handler.config['DEFAULT_GAS'],
        )
    ).get_period_start_prevhash(expected_period_number)
    logger.debug("mk_testing_colhdr: period_start_prevhash=%s", period_start_prevhash)
    tx_list_root = b"tx_list " * 4
    post_state_root = b"post_sta" * 4
    receipt_root = b"receipt " * 4
    sighash = keccak(
        rlp.encode([
            shard_id,
            expected_period_number,
            period_start_prevhash,
            parent_collation_hash,
            tx_list_root,
            collation_coinbase,
            post_state_root,
            receipt_root,
            number,
        ])
    )
    sig = sign(sighash, privkey)
    return rlp.encode([
        shard_id,
        expected_period_number,
        period_start_prevhash,
        parent_collation_hash,
        tx_list_root,
        collation_coinbase,
        post_state_root,
        receipt_root,
        number,
        sig,
    ])


@pytest.mark.parametrize(  # noqa: F811
    'mock_score,mock_is_new_head,expected_score,expected_is_new_head',
    (
        # test case in doc.md
        (
            (10, 11, 12, 11, 13, 14, 15, 11, 12, 13, 14, 12, 13, 14, 15, 16, 17, 18, 19, 16),
            (True, True, True, False, True, True, True, False, False, False, False, False, False, False, False, True, True, True, True, False),  # noqa: E501
            (19, 18, 17, 16, 16, 15, 15, 14, 14, 14, 13, 13, 13, 12, 12, 12, 11, 11, 11, 10),
            (True, True, True, True, False, True, False, True, False, False, True, False, False, True, False, False, True, False, False, True),  # noqa: E501
        ),
        (
            (1, 2, 3, 2, 2, 2),
            (True, True, True, False, False, False),
            (3, 2, 2, 2, 2, 1),
            (True, True, False, False, False, True),
        ),
    )
)
def test_vmc_fetch_candidate_head(vmc,
                                  mock_score,
                                  mock_is_new_head,
                                  expected_score,
                                  expected_is_new_head):
    shard_id = 0
    mock_collation_added_logs = [
        {
            'header': [None] * 10,
            'score': mock_score[i],
            'is_new_head': mock_is_new_head[i],
        } for i in range(len(mock_score))
    ]
    # mock collation_added_logs
    vmc.new_logs[shard_id] = mock_collation_added_logs
    for i in range(len(mock_score)):
        log = vmc.fetch_candidate_head(shard_id)
        assert log['score'] == expected_score[i]
        assert log['is_new_head'] == expected_is_new_head[i]
    with pytest.raises(NextLogUnavailable):
        log = vmc.fetch_candidate_head(shard_id)


def test_vmc_contract_calls(vmc):  # noqa: F811
    shard_id = 0
    validator_index = 0
    primary_key = test_keys[validator_index]
    primary_addr = test_keys[validator_index].public_key.to_canonical_address()
    default_gas = vmc.config['DEFAULT_GAS']

    # test `mk_build_transaction_detail` ######################################
    build_transaction_detail = vmc.mk_build_transaction_detail(
        nonce=0,
        gas=10000,
    )
    assert 'nonce' in build_transaction_detail
    assert 'gas' in build_transaction_detail
    assert 'chainId' in build_transaction_detail
    with pytest.raises(ValueError):
        build_transaction_detail = vmc.mk_build_transaction_detail(
            nonce=None,
            gas=10000,
        )
    with pytest.raises(ValueError):
        build_transaction_detail = vmc.mk_build_transaction_detail(
            nonce=0,
            gas=None,
        )

    # test `mk_contract_tx_detail` ######################################
    tx_detail = vmc.mk_contract_tx_detail(
        sender_address=ZERO_ADDR,
        gas=vmc.config['DEFAULT_GAS'],
    )
    assert 'from' in tx_detail
    assert 'gas' in tx_detail
    with pytest.raises(ValueError):
        tx_detail = vmc.mk_contract_tx_detail(
            sender_address=ZERO_ADDR,
            gas=None,
        )
    with pytest.raises(ValueError):
        tx_detail = vmc.mk_contract_tx_detail(
            sender_address=None,
            gas=vmc.config['DEFAULT_GAS'],
        )

    # test the deployment of vmc ######################################
    # deploy vmc if it is not deployed yet.
    if not is_vmc_deployed(vmc):
        logger.debug('is_vmc_deployed(vmc) == True')
        # import test_key
        import_key(vmc, primary_key)
        deploy_initiating_contracts(vmc, primary_key)
        mine(vmc, 1)

    assert is_vmc_deployed(vmc)

    lookahead_blocks = vmc.config['LOOKAHEAD_PERIODS'] * vmc.config['PERIOD_LENGTH']
    # test `deposit` and `get_eligible_proposer` ######################################
    # now we require 1 validator.
    # if there is currently no validator, we deposit one.
    # else, there should only be one validator, for easier testing.
    num_validators = vmc.call(
        vmc.mk_contract_tx_detail(sender_address=primary_addr, gas=default_gas)
    ).get_num_validators()
    if num_validators == 0:
        # deploy valcode for the validator, and deposit as the first validator
        valcode_addr = deploy_valcode_and_deposit(
            vmc,
            primary_key,
        )
        # TODO: error occurs when we don't mine so many blocks
        mine(vmc, lookahead_blocks)
        assert vmc.get_eligible_proposer(shard_id) == valcode_addr

    # assert the current_block_number >= LOOKAHEAD_PERIODS * PERIOD_LENGTH
    # to ensure that `get_eligible_proposer` works
    current_block_number = vmc.web3.eth.blockNumber
    if current_block_number < lookahead_blocks:
        mine(vmc, lookahead_blocks - current_block_number)
    assert vmc.web3.eth.blockNumber >= lookahead_blocks

    num_validators = vmc.call(
        vmc.mk_contract_tx_detail(sender_address=primary_addr, gas=default_gas)
    ).get_num_validators()
    assert num_validators == 1
    assert vmc.get_eligible_proposer(shard_id) != ZERO_ADDR
    logger.debug("vmc_handler.get_num_validators()=%s", num_validators)

    # test `add_header` ######################################
    genesis_colhdr_hash = b'\x00' * 32
    # create a testing collation header, whose parent is the genesis
    header0_1 = mk_testing_colhdr(vmc, shard_id, genesis_colhdr_hash, 1)
    header0_1_hash = keccak(header0_1)
    # if a header is added before its parent header is added, `add_header` should fail
    # TransactionFailed raised when assertions fail
    with pytest.raises(TransactionFailed):
        header_parent_not_added = mk_testing_colhdr(
            vmc,
            shard_id,
            header0_1_hash,
            1,
        )
        vmc.call(vmc.mk_contract_tx_detail(
            sender_address=primary_addr,
            gas=default_gas,
            gas_price=1,
        )).add_header(header_parent_not_added)
    # when a valid header is added, the `add_header` call should succeed
    vmc.add_header(header0_1)
    mine(vmc, vmc.config['PERIOD_LENGTH'])
    # if a header is added before, the second trial should fail
    with pytest.raises(TransactionFailed):
        vmc.call(vmc.mk_contract_tx_detail(
            sender_address=primary_addr,
            gas=default_gas,
            gas_price=1,
        )).add_header(header0_1)
    # when a valid header is added, the `add_header` call should succeed
    header0_2 = mk_testing_colhdr(vmc, shard_id, header0_1_hash, 2)
    header0_2_hash = keccak(header0_2)
    vmc.add_header(header0_2)

    mine(vmc, vmc.config['PERIOD_LENGTH'])
    # confirm the score of header1 and header2 are correct or not
    colhdr0_1_score = vmc.call(
        vmc.mk_contract_tx_detail(sender_address=primary_addr, gas=default_gas)
    ).get_collation_headers__score(shard_id, header0_1_hash)
    assert colhdr0_1_score == 1
    colhdr0_2_score = vmc.call(
        vmc.mk_contract_tx_detail(sender_address=primary_addr, gas=default_gas)
    ).get_collation_headers__score(shard_id, header0_2_hash)
    assert colhdr0_2_score == 2
    # confirm the logs are correct
    assert vmc.get_next_log(shard_id)['score'] == 2
    assert vmc.get_next_log(shard_id)['score'] == 1
    with pytest.raises(NextLogUnavailable):
        vmc.get_next_log(shard_id)
    # filter logs in multiple shards
    header1_1 = mk_testing_colhdr(vmc, 1, genesis_colhdr_hash, 1)
    vmc.add_header(header1_1)
    mine(vmc, 1)
    assert vmc.get_next_log(1)['score'] == 1
    logs = vmc.web3.eth.getLogs({
        "fromBlock": 0,
        "toBlock": vmc.web3.eth.blockNumber,
        "topics": [
            encode_hex(vmc.COLLATION_ADDED_TOPIC),
        ]
    })
    assert len(logs) == 3

    vmc.tx_to_shard(
        test_keys[1].public_key.to_canonical_address(),
        shard_id,
        100000,
        1,
        b'',
        value=1234567,
    )
    mine(vmc, 1)
    receipt_value = vmc.call(
        vmc.mk_contract_tx_detail(sender_address=primary_addr, gas=default_gas)
    ).get_receipts__value(0)
    # the receipt value should be equaled to the transaction value
    assert receipt_value == 1234567

    # test `withdraw` ######################################
    do_withdraw(vmc, validator_index)
    mine(vmc, 1)
    # if the only validator withdraws, because there is no validator anymore, the result of
    # `get_num_validators` must be 0.
    # print(vmc.get_eligible_proposer(shard_id))
    num_validators = vmc.call(
        vmc.mk_contract_tx_detail(sender_address=primary_addr, gas=default_gas)
    ).get_num_validators()
    assert num_validators == 0


@pytest.mark.parametrize(
    'data_hex,expected_header,expected_is_new_head,expected_score',
    (
        (
            "0xf9011f8005a0548cb741e565bc030f2b831d558cc197cddd1e7aab9549e77910ddbe65dde4b2a00000000000000000000000000000000000000000000000000000000000000000a074785f6c6973742074785f6c6973742074785f6c6973742074785f6c69737420947e5f4552091a69125d5dfcb7b8c2659029395bdfa0706f73745f737461706f73745f737461706f73745f737461706f73745f737461a0726563656970742072656365697074207265636569707420726563656970742001b860000000000000000000000000000000000000000000000000000000000000001b2c3dbf1b660db4c5eba798dbccd187105767247e6648cdd9c664a81af5fc217a194d54c0ba0a4b57c4eb70edc45367c6a1044b0e5f29b5a9339d214c9ea8016c00000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000001",  # noqa: E501
            (0, 5, b'T\x8c\xb7A\xe5e\xbc\x03\x0f+\x83\x1dU\x8c\xc1\x97\xcd\xdd\x1ez\xab\x95I\xe7y\x10\xdd\xbee\xdd\xe4\xb2', b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', b'tx_list tx_list tx_list tx_list ', b'~_ER\t\x1ai\x12]]\xfc\xb7\xb8\xc2e\x90)9[\xdf', b'post_stapost_stapost_stapost_sta', b'receipt receipt receipt receipt ', 1, b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x1b,=\xbf\x1bf\r\xb4\xc5\xeb\xa7\x98\xdb\xcc\xd1\x87\x10Wg$~fH\xcd\xd9\xc6d\xa8\x1a\xf5\xfc!z\x19MT\xc0\xba\nKW\xc4\xebp\xed\xc4Sg\xc6\xa1\x04K\x0e_)\xb5\xa93\x9d!L\x9e\xa8\x01l'),  # noqa: E501
            True,
            1,
        ),
        (
            "0xf9011f8006a0a149733c7160ada7d19fbec374c95c8a677303909c1d36f9a8bb994e3af96bbea0000e88d3cd262be90531edadf213219cf94a1fa296483307ba323a7c5519c7e9a074785f6c6973742074785f6c6973742074785f6c6973742074785f6c69737420947e5f4552091a69125d5dfcb7b8c2659029395bdfa0706f73745f737461706f73745f737461706f73745f737461706f73745f737461a0726563656970742072656365697074207265636569707420726563656970742002b860000000000000000000000000000000000000000000000000000000000000001b933e6e5627669b1b51d5b0759b311ad7c2bbff17fd44aec86dd66e8886b7d76b7bbdb064b4bea863a662113b5056dff996f589828cd973644c4dbbf739e261d500000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000002",  # noqa: E501
            (0, 6, b'\xa1Is<q`\xad\xa7\xd1\x9f\xbe\xc3t\xc9\\\x8ags\x03\x90\x9c\x1d6\xf9\xa8\xbb\x99N:\xf9k\xbe', b'\x00\x0e\x88\xd3\xcd&+\xe9\x051\xed\xad\xf2\x13!\x9c\xf9J\x1f\xa2\x96H3\x07\xba2:|U\x19\xc7\xe9', b'tx_list tx_list tx_list tx_list ', b'~_ER\t\x1ai\x12]]\xfc\xb7\xb8\xc2e\x90)9[\xdf', b'post_stapost_stapost_stapost_sta', b'receipt receipt receipt receipt ', 2, b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x1b\x93>nV'f\x9b\x1bQ\xd5\xb0u\x9b1\x1a\xd7\xc2\xbb\xff\x17\xfdD\xae\xc8m\xd6n\x88\x86\xb7\xd7k{\xbd\xb0d\xb4\xbe\xa8c\xa6b\x11;PV\xdf\xf9\x96\xf5\x89\x82\x8c\xd9sdLM\xbb\xf79\xe2a\xd5"),  # noqa: E501
            True,
            2,
        ),
    )
)
def test_parse_collation_added_data(data_hex,
                                    expected_header,
                                    expected_is_new_head,
                                    expected_score):
    parsed_data = parse_collation_added_data(data_hex)
    assert parsed_data['header'] == expected_header
    assert parsed_data['is_new_head'] == expected_is_new_head
    assert parsed_data['score'] == expected_score
