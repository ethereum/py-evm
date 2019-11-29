#!/usr/bin/env python

"""
Create a Trinity database by importing the current state of a Geth database
"""

import argparse
import os
import os.path
from pathlib import Path
import shutil
import snappy
import struct

import plyvel

from eth_utils import humanize_hash
import rlp

from eth.chains.mainnet import MAINNET_GENESIS_HEADER, MainnetChain
from eth.db.backends.level import LevelDB
from eth.rlp.headers import BlockHeader


class GethKeys:
    # from https://github.com/ethereum/go-ethereum/blob/master/core/rawdb/schema.go
    DatabaseVersion = b'DatabaseVersion'
    HeadBlock = b'LastBlock'

    headerPrefix = b'h'
    headerNumberPrefix = b'H'
    headerHashSuffix = b'n'

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
        print(f'opening freezer table. name={self.name}')

        self.index_file = open(os.path.join(ancient_path, self.index_file_name), 'rb')
        stat_result = os.stat(self.index_file.fileno())
        index_file_size = stat_result.st_size
        assert index_file_size % 6 == 0, index_file_size
        print(f'index_size={index_file_size} ({index_file_size // 6} entries)')
        self.entries = index_file_size // 6

        first_index_bytes = self.index_file.read(6)
        first_index = GethFreezerIndexEntry.from_bytes(first_index_bytes)
        print(f'first_index={first_index}')

        self.index_file.seek(-6, 2)
        last_index_bytes = self.index_file.read(6)
        last_index = GethFreezerIndexEntry.from_bytes(last_index_bytes)
        print(f'last_index={last_index}')

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

    def block_header(self, block_number: int, header_hash: bytes) -> BlockHeader:
        # This also needs to check the ancient db
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


def main(args):
    # Open geth database
    gethdb = GethDatabase(args.gethdb)

    last_block = gethdb.last_block_hash
    last_block_num = gethdb.block_num_for_hash(last_block)
    print('geth database opened')
    print(f'found chain tip: header_hash={humanize_hash(last_block)} block_number={last_block_num}')

    print(f'header: {len(gethdb.block_header(last_block_num, last_block))}')

    genesis_hash = gethdb.header_hash_for_block_number(0)
    genesis_header = gethdb.block_header(0, genesis_hash)
    print(f'genesis header: {genesis_header}')
    assert genesis_header == MAINNET_GENESIS_HEADER

    first_hash = gethdb.header_hash_for_block_number(1)
    first_block = gethdb.block_header(1, first_hash)
    print(f'first header: {first_block}')

    # Create trinity database

    db_already_existed = False
    if os.path.exists(args.destdb):
        db_already_existed = True

    leveldb = LevelDB(db_path=Path(args.destdb), max_open_files=16)

    if not db_already_existed:
        print(f'Trinity database did not already exist, initializing it now')
        chain = MainnetChain.from_genesis_header(leveldb, MAINNET_GENESIS_HEADER)
    else:
        chain = MainnetChain(leveldb)

    headerdb = chain.headerdb

    canonical_head = headerdb.get_canonical_head()
    print(f'starting copy from trinity\'s canonical head: {canonical_head}')

    # verify the trinity database matches what geth has
    geth_header = gethdb.block_header(canonical_head.block_number, canonical_head.hash)
    assert geth_header.hash == canonical_head.hash

    for i in range(canonical_head.block_number, last_block_num + 1):
        header_hash = gethdb.header_hash_for_block_number(i)
        header = gethdb.block_header(i, header_hash)

        headerdb.persist_header(header)

        if i % 1000 == 0:
            print(f'current canonical header: {headerdb.get_canonical_head()}')

    return


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-gethdb', type=str, required=True)
    parser.add_argument('-destdb', type=str, required=True)
    args = parser.parse_args()

    main(args)
