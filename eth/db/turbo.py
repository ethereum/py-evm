from typing import Iterable, Tuple

import rlp

from eth_hash.auto import keccak
from eth_typing import Address, Hash32
from eth_utils import to_tuple

from eth.db.backends.base import BaseDB
from eth.db.block_diff import BlockDiff
from eth.db.header import HeaderDB
from eth.db.schema import Schemas, SchemaTurbo, ensure_schema

from eth.rlp.accounts import Account
from eth.rlp.headers import BlockHeader


def find_header_path(db: HeaderDB, source: BlockHeader, dest: BlockHeader) \
                     -> Tuple[Tuple[BlockHeader], Tuple[BlockHeader]]:
    """
    Returns the headers which must be unapplied in order to reach dest, followed by
    the headers which must be applied.
    """

    if source == dest:
        return ((), ())

    ancestor = find_greatest_common_ancestor(db, source, dest)

    if ancestor == source:
        forward_headers = tuple(reversed(build_header_chain(db, dest, source)))
        reverse_headers = ()
        return reverse_headers, forward_headers

    if ancestor == dest:
        reverse_headers = build_header_chain(db, source, dest)
        forward_headers = ()
        return reverse_headers, forward_headers

    reverse_headers = build_header_chain(db, source, ancestor)
    forward_headers = tuple(reversed(build_header_chain(db, dest, ancestor)))
    return reverse_headers, forward_headers


def find_greatest_common_ancestor(db: HeaderDB, source: BlockHeader,
                                  dest: BlockHeader) -> BlockHeader:
    "If you view the header chain as a meet-semilattice: this returns the meet"
    if source.block_number > dest.block_number:
        source, dest = dest, source

    assert source.block_number <= dest.block_number

    while dest.block_number > source.block_number:
        parent = db.get_block_header_by_hash(dest.parent_hash)
        dest = parent

    assert source.block_number == dest.block_number

    while dest.block_number >= 0:
        if dest.hash == source.hash:
            return dest

        dest_parent = db.get_block_header_by_hash(dest.parent_hash)
        dest = dest_parent

        source_parent = db.get_block_header_by_hash(source.parent_hash)
        source = source_parent

    assert False, "These headers do not share a genesis?"


@to_tuple
def build_header_chain(db: HeaderDB, tail: BlockHeader,
                       head: BlockHeader) -> Iterable[BlockHeader]:
    """
    Returns a chain of headers beginning with {tail} and ending with {head}.

    Will loop forever if {head} is not an ancestor of {tail}.
    """
    current_header = tail

    while True:
        yield current_header

        parent = db.get_block_header_by_hash(current_header.parent_hash)
        if parent == head:
            return
        current_header = parent


class TurboDatabase:
    """
    A helper for accessing data from the TurboDB.
    """

    def __init__(self, db: HeaderDB, header: BlockHeader = None) -> None:
        """
        {header} specifies which state to read from. If {header} is not provided then the
        most recent state is used.
        """
        self.db = db
        base_db = db.db

        ensure_schema(base_db, Schemas.TURBO)

        self.reverse_diffs = ()
        self.forward_diffs = ()


        if header is None:
            return

        if base_db[SchemaTurbo.current_state_root_key] == header.state_root:
            return

        # we've been asked to return some state which is not the current state

        # first, double-check that the turbodb hasn't gotten out of sync:
        current_header = db.get_canonical_head()
        assert base_db[SchemaTurbo.current_state_root_key] == current_header.state_root

        # next, we need to lookup the series of block diffs to get to {header}
        reverse_headers, forward_headers = find_header_path(db, current_header, header)

        # TODO: throw a better exception when the block diff is not found
        self.reverse_diffs = tuple(
            BlockDiff.from_db(base_db, header.state_root)
            for header in reverse_headers
        )
        self.forward_diffs = tuple(
            BlockDiff.from_db(base_db, header.state_root)
            for header in forward_headers
        )

    def get_encoded_account(self, address: Address) -> bytes:
        for diff in reversed(self.forward_diffs):
            if address in diff.get_changed_accounts():
                return diff.get_account(address, new=True)

        for diff in reversed(self.reverse_diffs):
            if address in diff.get_changed_accounts():
                return diff.get_account(address, new=False)

        # The account was apparently never changed, return the current value
        return self._get_encoded_account(self.db.db, address)

    def get_account(self, address: Address) -> Account:
        # TODO: merge this with _get_account
        try:
            account_rlp = self.get_encoded_account(address)

            if account_rlp == b'':
                return Account()

            return rlp.decode(account_rlp, sedes=Account)
        except KeyError:
            return Account()

    @staticmethod
    def _get_encoded_account(db: BaseDB, address: Address) -> bytes:
        ensure_schema(db, Schemas.TURBO)

        key = SchemaTurbo.make_account_state_lookup_key(keccak(address))
        return db[key]

    @classmethod
    def _get_account(cls, db: BaseDB, address: Address) -> Account:
        try:
            account_rlp = cls._get_encoded_account(db, address)

            if account_rlp == b'':
                return Account()

            return rlp.decode(account_rlp, sedes=Account)
        except KeyError:
            return Account()


class TurboBaseDB(BaseDB):
    """
    A helper so TurboDatabase can be used from inside JournalDB

    Needs: __contains__, __delitem__, __setitem__, __getitem__
    """

    def __init__(self, turbodb: TurboDatabase) -> None:
        self._turbodb = turbodb

    def _exists(self, key: bytes) -> bool:
        try:
            self.__getitem__(key)
            return True
        except KeyError:
            return False

    def __getitem__(self, key: bytes) -> bytes:
        return self._turbodb.get_encoded_account(key)

    def __setitem__(self, key: bytes, value: bytes) -> None:
        raise NotImplemented("TurboBaseDB objects cannot be mutated")

    def __delitem__(self, key: bytes) -> None:
        raise NotImplemented("TurboBaseDB objects cannot be mutated")
