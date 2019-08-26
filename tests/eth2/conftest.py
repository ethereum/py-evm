import functools

import eth_utils.toolz as toolz
import pytest

from eth2._utils.bls import bls
from eth2._utils.hash import hash_eth2


def _serialize_bls_pubkeys(key):
    """
    The ``pytest`` cache wants a JSON encodable value.
    Provide the hex-encoded ``key``.
    """
    return key.hex()


def _deserialize_bls_pubkey(key_data):
    return bytes.fromhex(key_data)


def _deserialize_pair(pair):
    index, pubkey = pair
    return (int(index), _deserialize_bls_pubkey(pubkey))


class privkey_view:
    def __init__(self, key_cache):
        self.key_cache = key_cache

    def __getitem__(self, index):
        """
        Index into the list of all created privkeys.
        """
        return self.key_cache._get_privkey_at(index)


class pubkey_view:
    def __init__(self, key_cache):
        self.key_cache = key_cache

    def __getitem__(self, index):
        if isinstance(index, slice):
            return list(self.key_cache._get_pubkey_at(i) for i in range(index.stop))
        return self.key_cache._get_pubkey_at(index)


class BLSKeyCache:
    keys = {}  # Dict[BLSPubkey, int] # (pubkey, privkey)

    # we use dictionaries to simulate sparse lists
    all_pubkeys_by_index = {}
    all_privkeys_by_index = {}

    def __init__(self, backing_cache_reader, backing_cache_writer):
        self.backing_cache_reader = backing_cache_reader
        self.backing_cache_writer = backing_cache_writer
        self.privkeys = privkey_view(self)
        self.pubkeys = pubkey_view(self)

    def _restore_from_cache(self, cached_data):
        self.all_pubkeys_by_index = toolz.itemmap(
            _deserialize_pair, cached_data["pubkeys_by_index"]
        )
        for index, pubkey in self.all_pubkeys_by_index.items():
            privkey = self._get_privkey_for(index)
            self.keys[pubkey] = privkey

    def _serialize(self):
        """
        Persist the expensive data to the backing cache.

        NOTE: we currently use an inexpensive determinstic computation
        for the private keys so all we need to persist are the expensive
        pubkeys and the index data (which allows derivation of the privkey).
        """
        return {
            "pubkeys_by_index": toolz.valmap(
                _serialize_bls_pubkeys, self.all_pubkeys_by_index
            )
        }

    def _privkey_view(self):
        return self.privkeys

    def _pubkey_view(self):
        return self.pubkeys

    def _mapping_view(self):
        return self.keys

    def __enter__(self):
        if self.backing_cache_reader:
            # provide empty object as default
            defaults = self._serialize()
            self._restore_from_cache(self.backing_cache_reader(defaults))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.backing_cache_writer:
            self.backing_cache_writer(self._serialize())

    def _get_privkey_for(self, index):
        # Want privkey an intger slightly less than the curve order
        privkey = (
            int.from_bytes(hash_eth2(index.to_bytes(32, "little")), "little") % 2 ** 254
        )
        self.all_privkeys_by_index[index] = privkey
        return privkey

    def _generate_pubkey(self, privkey):
        """
        NOTE: this is currently our expensive function
        """
        return bls.privtopub(privkey)

    def _add_pubkey_for_privkey(self, index, privkey):
        pubkey = self._generate_pubkey(privkey)
        self.all_pubkeys_by_index[index] = pubkey
        self.keys[pubkey] = privkey
        return pubkey

    def _get_privkey_at(self, index):
        if index in self.all_privkeys_by_index:
            return self.all_privkeys_by_index[index]

        privkey = self._get_privkey_for(index)

        self._add_pubkey_for_privkey(index, privkey)

        return privkey

    def _get_pubkey_at(self, index):
        if index in self.all_pubkeys_by_index:
            return self.all_pubkeys_by_index[index]

        if index in self.all_privkeys_by_index:
            privkey = self.all_privkeys_by_index[index]
            return self._add_pubkey_for_privkey(index, privkey)

        privkey = self._get_privkey_for(index)
        return self._add_pubkey_for_privkey(index, privkey)


@pytest.fixture(scope="session")
def _should_persist_bls_keys():
    """
    This boolean indicates if the ``BLSKeyCache`` is persisted to
    the cross-test pytest caching mechanism or not.

    NOTE this implies writing the object to disk and could become large for
    large validator set sizes.
    """
    return True


@pytest.fixture(scope="session")
def _key_cache(request, _should_persist_bls_keys):
    """
    Maintain a session-wide pubkey/privkey cache for BLS cryptography.

    Keys are generated on-demand and cached after creation.
    """
    cache_key = f"eth2/bls/key-cache/{bls.backend.__name__}"

    if _should_persist_bls_keys:
        backing_cache_reader = functools.partial(request.config.cache.get, cache_key)
        backing_cache_writer = functools.partial(request.config.cache.set, cache_key)
    else:
        backing_cache_reader = None
        backing_cache_writer = None

    with BLSKeyCache(backing_cache_reader, backing_cache_writer) as cache:
        yield cache


@pytest.fixture(scope="session")
def privkeys(_key_cache):
    return _key_cache._privkey_view()


@pytest.fixture(scope="session")
def keymap(_key_cache):
    return _key_cache._mapping_view()


@pytest.fixture(scope="session")
def pubkeys(_key_cache):
    return _key_cache._pubkey_view()
