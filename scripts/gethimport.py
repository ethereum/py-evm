#!/usr/bin/env python

"""
Create a Trinity database by importing the current state of a Geth database
"""

import argparse
import logging
import os
import os.path
from pathlib import Path
import shutil
import snappy
import struct
import time

import plyvel

from eth_utils import humanize_hash
import rlp
from rlp.sedes import CountableList

from eth.chains.mainnet import MAINNET_GENESIS_HEADER, MainnetChain
from eth.constants import BLANK_ROOT_HASH, EMPTY_SHA3
from eth.db.backends.level import LevelDB
from eth.db.trie import make_trie_root_and_nodes
from eth.rlp.headers import BlockHeader
from eth.rlp.transactions import BaseTransactionFields
from eth.rlp.accounts import Account

from eth.db.trie_iteration import iterate_leaves

from trie.utils.nibbles import nibbles_to_bytes


logger = logging.getLogger('importer')


class GethKeys:
    # from https://github.com/ethereum/go-ethereum/blob/master/core/rawdb/schema.go
    DatabaseVersion = b'DatabaseVersion'
    HeadBlock = b'LastBlock'

    headerPrefix = b'h'
    headerNumberPrefix = b'H'
    headerHashSuffix = b'n'

    blockBodyPrefix = b'b'
    blockReceiptsPrefix = b'r'

    @classmethod
    def header_hash_for_block_number(cls, block_number: int) -> bytes:
        "The key to get the hash of the header with the given block number"
        packed_block_number = struct.pack('>Q', block_number)
        return cls.headerPrefix + packed_block_number + cls.headerHashSuffix

    @classmethod
    def block_number_for_header_hash(cls, header_hash: bytes) -> bytes:
        "The key to get the block number of the header with the given hash"
        return cls.headerNumberPrefix + header_hash

    @classmethod
    def block_header(cls, block_number: int, header_hash: bytes) -> bytes:
        packed_block_number = struct.pack('>Q', block_number)
        return cls.headerPrefix + packed_block_number + header_hash

    @classmethod
    def block_body(cls, block_number: int, header_hash: bytes) -> bytes:
        packed_block_number = struct.pack('>Q', block_number)
        return cls.blockBodyPrefix + packed_block_number + header_hash

    @classmethod
    def block_receipts(cls, block_number: int, header_hash: bytes) -> bytes:
        packed_block_number = struct.pack('>Q', block_number)
        return cls.blockReceiptsPrefix + packed_block_number + header_hash


class GethFreezerIndexEntry:
    def __init__(self, filenum: int, offset: int):
        self.filenum = filenum
        self.offset = offset

    @classmethod
    def from_bytes(cls, data: bytes) -> 'GethFreezerIndexEntry':
        assert len(data) == 6
        filenum, offset = struct.unpack('>HI', data)
        return cls(filenum, offset)

    def __repr__(self):
        return f'IndexEntry(filenum={self.filenum}, offset={self.offset})'


class GethFreezerTable:
    def __init__(self, ancient_path, name, uses_compression):
        self.ancient_path = ancient_path
        self.name = name
        self.uses_compression = uses_compression
        logger.debug(f'opening freezer table. name={self.name}')

        self.index_file = open(os.path.join(ancient_path, self.index_file_name), 'rb')
        stat_result = os.stat(self.index_file.fileno())
        index_file_size = stat_result.st_size
        assert index_file_size % 6 == 0, index_file_size
        logger.debug(f'index_size={index_file_size} ({index_file_size // 6} entries)')
        self.entries = index_file_size // 6

        first_index_bytes = self.index_file.read(6)
        first_index = GethFreezerIndexEntry.from_bytes(first_index_bytes)
        logger.debug(f'first_index={first_index}')

        self.index_file.seek(-6, 2)
        last_index_bytes = self.index_file.read(6)
        last_index = GethFreezerIndexEntry.from_bytes(last_index_bytes)
        logger.debug(f'last_index={last_index}')

        self._data_files = dict()

    @property
    def index_file_name(self):
        suffix = 'cidx' if self.uses_compression else 'ridx'
        return f'{self.name}.{suffix}'

    def data_file_name(self, number: int):
        suffix = 'cdat' if self.uses_compression else 'rdat'
        return f'{self.name}.{number:04d}.{suffix}'

    def _data_file(self, number: int):
        if number not in self._data_files:
            path = os.path.join(self.ancient_path, self.data_file_name(number))
            data_file = open(path, 'rb')
            self._data_files[number] = data_file

        return self._data_files[number]

    def get(self, number: int) -> bytes:
        assert number < self.entries

        self.index_file.seek(number * 6)
        entry_bytes = self.index_file.read(6)
        start_entry = GethFreezerIndexEntry.from_bytes(entry_bytes)

        # What happens if we're trying to read the last item? Won't this fail?
        # Is there always one extra entry in the index file?
        self.index_file.seek((number+1) * 6)
        entry_bytes = self.index_file.read(6)
        end_entry = GethFreezerIndexEntry.from_bytes(entry_bytes)

        if start_entry.filenum != end_entry.filenum:
            # Duplicates logic from freezer_table.go:getBounds
            start_entry = GethFreezerIndexEntry(end_entry.filenum, offset=0)

        data_file = self._data_file(start_entry.filenum)
        data_file.seek(start_entry.offset)
        data = data_file.read(end_entry.offset - start_entry.offset)

        if not self.uses_compression:
            return data

        return snappy.decompress(data)

    def __del__(self) -> None:
        for f in self._data_files.values():
            f.close()
        self.index_file.close()


class BlockBody(rlp.Serializable):
    "This is how geth stores block bodies"
    fields = [
        ('transactions', CountableList(BaseTransactionFields)),
        ('uncles', CountableList(BlockHeader)),
    ]

    def __repr__(self) -> str:
        return f'BlockBody(txns={self.transactions}, uncles={self.uncles})'


class GethDatabase:
    def __init__(self, path):
        self.db = plyvel.DB(
            path,
            create_if_missing=False,
            error_if_exists=False,
            max_open_files=16
        )

        ancient_path = os.path.join(path, 'ancient')
        self.ancient_hashes = GethFreezerTable(ancient_path, 'hashes', False)
        self.ancient_headers = GethFreezerTable(ancient_path, 'headers', True)
        self.ancient_bodies = GethFreezerTable(ancient_path, 'bodies', True)
        self.ancient_receipts = GethFreezerTable(ancient_path, 'receipts', True)

        if self.database_version != b'\x07':
            raise Exception(f'geth database version {self.database_version} is not supported')

    @property
    def database_version(self) -> bytes:
        raw_version = self.db.get(GethKeys.DatabaseVersion)
        return rlp.decode(raw_version)

    @property
    def last_block_hash(self) -> bytes:
        return self.db.get(GethKeys.HeadBlock)

    def block_num_for_hash(self, header_hash: bytes) -> int:
        raw_num = self.db.get(GethKeys.block_number_for_header_hash(header_hash))
        return struct.unpack('>Q', raw_num)[0]

    def block_header(self, block_number: int, header_hash: bytes = None) -> BlockHeader:
        if header_hash is None:
            header_hash = self.header_hash_for_block_number(block_number)

        raw_data = self.db.get(GethKeys.block_header(block_number, header_hash))
        if raw_data is not None:
            return rlp.decode(raw_data, sedes=BlockHeader)

        raw_data = self.ancient_headers.get(block_number)
        return rlp.decode(raw_data, sedes=BlockHeader)

    def header_hash_for_block_number(self, block_number: int) -> bytes:
        # This needs to check the ancient db (freezerHashTable)
        result = self.db.get(GethKeys.header_hash_for_block_number(block_number))

        if result is not None:
            return result

        return self.ancient_hashes.get(block_number)

    def block_body(self, block_number: int, header_hash: bytes = None):
        if header_hash is None:
            header_hash = self.header_hash_for_block_number(block_number)

        raw_data = self.db.get(GethKeys.block_body(block_number, header_hash))
        if raw_data is not None:
            return rlp.decode(raw_data, sedes=BlockBody)

        raw_data = self.ancient_bodies.get(block_number)
        return rlp.decode(raw_data, sedes=BlockBody)

    def block_receipts(self, block_number: int, header_hash: bytes = None):
        if header_hash is None:
            header_hash = self.header_hash_for_block_number(block_number)

        raw_data = self.db.get(GethKeys.block_receipts(block_number, header_hash))
        if raw_data is not None:
            return raw_data

        raw_data = self.ancient_receipts.get(block_number)
        return raw_data


class ImportDatabase:
    "Creates a 'ChainDB' which can be passed to the trie_iteration utils"
    def __init__(self, gethdb, trinitydb):
        self.gethdb = gethdb
        self.trinitydb = trinitydb

    def get(self, node_hash):
        trinity_result = self.trinitydb.get(node_hash)
        if trinity_result is not None:
            return trinity_result

        geth_result = self.gethdb.get(node_hash)
        if geth_result is None:
            logger.error(f'could not find node for hash: {node_hash.hex()}')
            assert False

        self.trinitydb.put(node_hash, geth_result)
        return geth_result


def open_gethdb(location):
    gethdb = GethDatabase(location)

    last_block = gethdb.last_block_hash
    last_block_num = gethdb.block_num_for_hash(last_block)
    logger.info('geth database opened')
    logger.info(f'found geth chain tip: header_hash={humanize_hash(last_block)} block_number={last_block_num}')

    genesis_hash = gethdb.header_hash_for_block_number(0)
    genesis_header = gethdb.block_header(0, genesis_hash)
    assert genesis_header == MAINNET_GENESIS_HEADER

    return gethdb


def open_trinitydb(location):
    db_already_existed = False
    if os.path.exists(location):
        db_already_existed = True

    leveldb = LevelDB(db_path=Path(location), max_open_files=16)

    if db_already_existed:
        return MainnetChain(leveldb)

    logger.info(f'Trinity database did not already exist, initializing it now')
    chain = MainnetChain.from_genesis_header(leveldb, MAINNET_GENESIS_HEADER)

    # from_genesis_header copied the header over to our trinity db but not the state

    return chain


def main(args):
    gethdb = open_gethdb(args.gethdb)
    chain = open_trinitydb(args.destdb)
    headerdb = chain.headerdb

    # 3. Import headers + bodies

    canonical_head = headerdb.get_canonical_head()
    logger.info(f'starting import from trinity\'s canonical head: {canonical_head}')

    # fail fast if geth disagrees with trinity's canonical head
    geth_header = gethdb.block_header(canonical_head.block_number, canonical_head.hash)
    assert geth_header.hash == canonical_head.hash

    geth_last_block_hash = gethdb.last_block_hash
    geth_last_block_num = gethdb.block_num_for_hash(geth_last_block_hash)

    final_block_to_sync = geth_last_block_num
    if args.syncuntil:
        final_block_to_sync = min(args.syncuntil, final_block_to_sync)

    for i in range(canonical_head.block_number, final_block_to_sync + 1):

        if not args.nobodies:
            import_block_body(gethdb, chain, i)
        else:
            header_hash = gethdb.header_hash_for_block_number(i)
            header = gethdb.block_header(i, header_hash)
            headerdb.persist_header(header)

        if i % 1000 == 0:
            logger.debug(f'current canonical header: {headerdb.get_canonical_head()}')

    canonical_head = headerdb.get_canonical_head()
    if not args.syncuntil:
        # similar checks should be run if we added sync until!
        # some final checks, these should never fail
        assert canonical_head.hash == geth_last_block_hash
        assert canonical_head.block_number == geth_last_block_num

    logger.info('finished importing headers + bodies')

    if args.justblocks:
        return

    scan_state(gethdb, leveldb)
    return

    state_root = canonical_head.state_root
    logger.info(f'starting state trie import: {humanize_hash(state_root)}')

    # 4. Import the state trie + storage tries
    # Write something which iterates over the entire trie, from left to right
    # Pass it a database which first looks in the trinity db, and if nothing is there
    #   copies the requested node from geth->trinity before returning it

    imported_leaf_count = 0
    importdb = ImportDatabase(gethdb=gethdb.db, trinitydb=leveldb.db)
    for path, leaf_data in iterate_leaves(importdb, state_root):
        account = rlp.decode(leaf_data, sedes=Account)
        addr_hash = nibbles_to_bytes(path)


        if account.code_hash != EMPTY_SHA3:
            bytecode = importdb.get(account.code_hash)

        if account.storage_root == BLANK_ROOT_HASH:
            imported_leaf_count += 1

            if imported_leaf_count % 1000 == 0:
                logger.debug(f'progress sha(addr)={addr_hash.hex()}')
            continue

        for path, leaf_data in iterate_leaves(importdb, account.storage_root):
            item_addr = nibbles_to_bytes(path)
            imported_leaf_count += 1

            if imported_leaf_count % 1000 == 0:
                logger.debug(f'progress sha(addr)={addr_hash.hex()} sha(item)={item_addr.hex()}')

    loger.info('successfully imported state trie and all storage tries')


def scan_state(gethdb: GethDatabase, trinitydb: LevelDB):
    """
    Imports state, but by indiscriminately copying over everything which might be part of
    the state trie. This copies more data than necessary, but is likely to be much faster
    than iterating all state.
    """
    logger.debug('scan_state: bulk-importing state entries')

    iterator = gethdb.db.iterator(
        start=b'\x00'*32,
        stop=b'\xff'*32,
        include_start=True,
        include_stop=True,
    )

    imported_entries = 0
    skipped_keys = 0
    bucket = b'\x00' * 2
    for key, value in iterator:
        if len(key) != 32:
            skipped_keys += 1
            continue
        trinitydb[key] = value
        imported_entries += 1

        if key >= bucket:
            logger.debug(f'imported: {bucket.hex()} skipped={skipped_keys}')
            if bucket == b'\xff' * 2:
                break
            bucket = (int.from_bytes(bucket, 'big') + 1).to_bytes(2, 'big')

    logger.info(f'scan_state: successfully imported {imported_entries} state entries')


def import_block_body(gethdb, chain, block_number: int):
    header_hash = gethdb.header_hash_for_block_number(block_number)
    header = gethdb.block_header(block_number, header_hash)

    body = gethdb.block_body(block_number)
    block_class = chain.get_vm_class(header).get_block_class()
    block = block_class(header, body.transactions, body.uncles)
    chain.chaindb.persist_block(block)

    # persist_block saves the transactions into an index, but doesn't actually persist the
    # transaction trie, meaning that without this next block attempts to read out the
    # block will throw an exception
    tx_root_hash, tx_kv_nodes = make_trie_root_and_nodes(body.transactions)
    assert tx_root_hash == block.header.transaction_root
    chain.chaindb.persist_trie_data_dict(tx_kv_nodes)


def import_body_range(gethdb, chain, start_block, end_block):
    logger.debug(
        f'importing block bodies for blocks in range({start_block}, {end_block + 1})'
    )
    previous_log_time = time.time()

    for i in range(start_block, end_block + 1):
        import_block_body(gethdb, chain, i)

        if time.time() - previous_log_time > 5:
            logger.debug(f'importing bodies. block_number={i}')
            previous_log_time = time.time()


def process_blocks(gethdb, chain, end_block):
    "Imports blocks read out of the gethdb. Simulates a full sync but w/o network traffic"

    canonical_head = chain.headerdb.get_canonical_head()
    logger.info(f'starting block processing from chain tip: {canonical_head}')

    start_block = max(canonical_head.block_number, 1)
    for i in range(start_block, end_block + 1):
        header_hash = gethdb.header_hash_for_block_number(i)
        header = gethdb.block_header(i, header_hash)
        vm_class = chain.get_vm_class(header)
        block_class = vm_class.get_block_class()
        transaction_class = vm_class.get_transaction_class()

        body = gethdb.block_body(i)
        transactions = [
            transaction_class.from_base_transaction(txn) for txn in body.transactions
        ]
        block = block_class(header, transactions, body.uncles)
        imported_block, _, _ = chain.import_block(block, perform_validation = True)
        logger.debug(f'imported block: {imported_block}')


def read_receipts(gethdb, block_number):
    logger.info(f'reading receipts for block. block_number={block_number}')

    raw_data = gethdb.block_receipts(block_number)
    decoded = rlp.decode(raw_data)

    logger.info(f'- receipt_count={len(decoded)}')

    for receipt in decoded:
        post_state, raw_gas_used, logs = receipt
        if len(raw_gas_used) < 8:
            padded = (b'\x00' * (8 - len(raw_gas_used))) + raw_gas_used
            gas_used = struct.unpack('>Q', padded)[0]
        logger.info(f'- post_state_or_status={post_state} gas_used={gas_used} len(logs)={len(logs)}')


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s.%(msecs)03d %(levelname)s: %(message)s',
        datefmt='%H:%M:%S'
    )

    parser = argparse.ArgumentParser()
    parser.add_argument('-gethdb', type=str, required=True)
    parser.add_argument('-destdb', type=str, required=True)
    parser.add_argument('-justblocks', action='store_true')
    parser.add_argument('-nobodies', action='store_true')
    parser.add_argument('-syncuntil', type=int, action='store')

    subparsers = parser.add_subparsers(dest="command")

    import_body_range_parser = subparsers.add_parser('import_body_range')
    import_body_range_parser.add_argument('-startblock', type=int, required=True)
    import_body_range_parser.add_argument('-endblock', type=int, required=True)

    process_blocks_parser = subparsers.add_parser('process_blocks')
    process_blocks_parser.add_argument('-endblock', type=int, required=True)

    read_receipts_parser = subparsers.add_parser('read_receipts')
    read_receipts_parser.add_argument('-block', type=int, required=True)

    args = parser.parse_args()

    if args.command == 'import_body_range':
        gethdb = open_gethdb(args.gethdb)
        chain = open_trinitydb(args.destdb)
        import_body_range(gethdb, chain, args.startblock, args.endblock)
    elif args.command == 'process_blocks':
        gethdb = open_gethdb(args.gethdb)
        chain = open_trinitydb(args.destdb)
        process_blocks(gethdb, chain, args.endblock)
    elif args.command == 'read_receipts':
        gethdb = open_gethdb(args.gethdb)
        read_receipts(gethdb, args.block)
    else:
        main(args)

    logger.warning('Some features are not yet implemented:')
    logger.warning('- Receipts were not imported')
    logger.warning('- This script did not verify that the chain configs match')
