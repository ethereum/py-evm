Trinity 
=======



0.1.0-alpha.12
--------------

- `#1058 <https://github.com/ethereum/py-evm/pull/1058>`  `#1044 <https://github.com/ethereum/py-evm/pull/1044>`: Add ``fix-unclean-shutdown`` CLI command for cleaning up after a dirty shutdown of the ``trinity`` CLI process.
- `#1041 <https://github.com/ethereum/py-evm/pull/1041>`: Bugfix for ensuring CPU count for process pool is always greater than ``0``
- `#1010 <https://github.com/ethereum/py-evm/pull/1010>`: Performance tuning during fast sync.  Only check POW on a subset of the received headers.
- `#996 <https://github.com/ethereum/py-evm/pull/996>` Experimental new Plugin API:  Both the transaction pool and the ``console`` and ``attach`` commands are now written as plugins.
- `#898 <https://github.com/ethereum/py-evm/pull/898>`: New experimental transaction pool.  Disabled by default.  Enable with ``--tx-pool``.  (**warning**: has known issues that effect sync performance)
- `#935 <https://github.com/ethereum/py-evm/pull/935>`: Protection against eclipse attacks.
- `#869 <https://github.com/ethereum/py-evm/pull/869>`: Ensure connected peers are on the same side of the DAO fork.

Minor Changes

- `#1081 <https://github.com/ethereum/py-evm/pull/1081>`: Reduce ``DEBUG`` log output during state sync.
- `#1071 <https://github.com/ethereum/py-evm/pull/1071>`: Minor fix for how version string is generated for trinity
- `#1070 <https://github.com/ethereum/py-evm/pull/1070>`: Easier profiling of ``ChainSyncer``
- `#1068 <https://github.com/ethereum/py-evm/pull/1068>`: Optimize ``evm.db.chain.ChainDB.persist_block`` for common case.
- `#1057 <https://github.com/ethereum/py-evm/pull/1057>`: Additional ``DEBUG`` logging of peer uptime and msg stats.
- `#1049 <https://github.com/ethereum/py-evm/pull/1049>`: New integration test suite for trinity CLI
- `#1045 <https://github.com/ethereum/py-evm/pull/1045>` `#1051 <https://github.com/ethereum/py-evm/pull/1051>`: Bugfix for generation of block numbers for ``GetBlockHeaders`` requests.
- `#1011 <https://github.com/ethereum/py-evm/pull/1011>`: Workaround for parity bug `parity #8038 <https://github.com/paritytech/parity-ethereum/issues/8038>`
- `#987 <https://github.com/ethereum/py-evm/pull/987>`: Now serving requests from peers during fast sync.
- `#971 <https://github.com/ethereum/py-evm/pull/971>` `#909 <https://github.com/ethereum/py-evm/pull/909>` `#650 <https://github.com/ethereum/py-evm/pull/650>`: Benchmarking test suite.
- `#968 <https://github.com/ethereum/py-evm/pull/968>`: When launching ``console`` and ``attach`` commands, check for presence of IPC socket and log informative message if not found.
- `#934 <https://github.com/ethereum/py-evm/pull/934>`: Decouple the ``Discovery`` and ``PeerPool`` services.
- `#913 <https://github.com/ethereum/py-evm/pull/913>`: Add validation of retrieved contract code when operating in ``--light`` mode.
- `#908 <https://github.com/ethereum/py-evm/pull/908>`: Bugfix for transitioning from syncing chain data to state data during fast sync.
- `#905 <https://github.com/ethereum/py-evm/pull/905>`: Support for multiple UPNP devices.


0.1.0-alpha.11
--------------

- Bugfix for ``PreferredNodePeerPool`` to respect ``max_peers``


0.1.0-alpha.10
--------------

- More bugfixes to enforce ``--max-peers`` in ``PeerPool._connect_to_nodes``


0.1.0-alpha.9
-------------

- Bugfix to enforce ``--max-peers`` for incoming connections.


0.1.0-alpha.7
-------------

- Remove ``min_peers`` concept from ``PeerPool``
- Add ``--max-peers`` and enforcement of maximum peer connections maintained by
  the ``PeerPool``.


0.1.0-alpha.6
-------------

- Respond to ``GetBlockHeaders`` message during fast sync to prevent being disconnected as a *useless peer*.
- Add ``--profile`` CLI flag to Trinity to enable profiling via ``cProfile``
- Better error messaging with Trinity cannot determine the appropriate location for the data directory.
- Handle ``ListDeserializationError`` during handshake.
- Add ``net_version`` JSON-RPC endpoint.
- Add ``web3_clientVersion`` JSON-RPC endpoint.
- Handle ``rlp.DecodingError`` during handshake.
