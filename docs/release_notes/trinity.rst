Trinity 
=======

0.1.0-alpha.14
--------------

- `#1081 <https://github.com/ethereum/py-evm/pull/1081>`_ `#1115 <https://github.com/ethereum/py-evm/pull/1115>`_ `#1116 <https://github.com/ethereum/py-evm/pull/1116>`_: Reduce logging output during state sync.
- `#1063 <https://github.com/ethereum/py-evm/pull/1063>`_ `#1035 <https://github.com/ethereum/py-evm/pull/1035>`_ `#1089 <https://github.com/ethereum/py-evm/pull/1089>`_ `#1131 <https://github.com/ethereum/py-evm/pull/1131>`_ `#1132 <https://github.com/ethereum/py-evm/pull/1132>`_ `#1138 <https://github.com/ethereum/py-evm/pull/1138>`_ `#1149 <https://github.com/ethereum/py-evm/pull/1149>`_ `#1159 <https://github.com/ethereum/py-evm/pull/1159>`_: Implement round trip request/response API.
- `#1094 <https://github.com/ethereum/py-evm/pull/1094>`_ `#1124 <https://github.com/ethereum/py-evm/pull/1124>`_: Make the node processing during state sync more async friendly.
- `#1097 <https://github.com/ethereum/py-evm/pull/1097>`_: Keep track of which peers are missing trie nodes during state sync.
- `#1109 <https://github.com/ethereum/py-evm/pull/1109>`_ `#1135 <https://github.com/ethereum/py-evm/pull/1135>`_: Python 3.7 testing and experimental support.
- `#1136 <https://github.com/ethereum/py-evm/pull/1136>`_ `#1120 <https://github.com/ethereum/py-evm/pull/1120>`_: Module re-organization in preparation of extracting ``p2p`` and ``trinity`` modules.
- `#1137 <https://github.com/ethereum/py-evm/pull/1137>`_: Peer subscriber API now supports specifying specific msg types to reduce msg queue traffic.
- `#1142 <https://github.com/ethereum/py-evm/pull/1142>`_ `#1165 <https://github.com/ethereum/py-evm/pull/1165>`_: Implement JSON-RPC endpoints for: ``eth_estimateGas``, ``eth_accounts``, ``eth_call``
- `#1150 <https://github.com/ethereum/py-evm/pull/1150>`_ `#1176 <https://github.com/ethereum/py-evm/pull/1176>`_: Better handling of malformed messages from peers.
- `#1157 <https://github.com/ethereum/py-evm/pull/1157>`_: Use shared pool of workers across all services.
- `#1158 <https://github.com/ethereum/py-evm/pull/1158>`_: Support specifying granular logging levels via CLI.
- `#1161 <https://github.com/ethereum/py-evm/pull/1161>`_: Use a tmpfile based LevelDB database for cache during state sync to reduce memory footprint.
- `#1166 <https://github.com/ethereum/py-evm/pull/1166>`_: Latency and performance tracking for peer requests.
- `#1173 <https://github.com/ethereum/py-evm/pull/1173>`_: Better APIs for background task running for ``Service`` classes.
- `#1182 <https://github.com/ethereum/py-evm/pull/1182>`_: Convert ``fix-unclean-shutdown`` command to be a plugin.


0.1.0-alpha.13
--------------

- Remove specified ``eth-account`` dependency in favor of allowing ``web3.py`` specify the correct version.


0.1.0-alpha.12
--------------

- `#1058 <https://github.com/ethereum/py-evm/pull/1058>`_  `#1044 <https://github.com/ethereum/py-evm/pull/1044>`_: Add ``fix-unclean-shutdown`` CLI command for cleaning up after a dirty shutdown of the ``trinity`` CLI process.
- `#1041 <https://github.com/ethereum/py-evm/pull/1041>`_: Bugfix for ensuring CPU count for process pool is always greater than ``0``
- `#1010 <https://github.com/ethereum/py-evm/pull/1010>`_: Performance tuning during fast sync.  Only check POW on a subset of the received headers.
- `#996 <https://github.com/ethereum/py-evm/pull/996>`_ Experimental new Plugin API:  Both the transaction pool and the ``console`` and ``attach`` commands are now written as plugins.
- `#898 <https://github.com/ethereum/py-evm/pull/898>`_: New experimental transaction pool.  Disabled by default.  Enable with ``--tx-pool``.  (**warning**: has known issues that effect sync performance)
- `#935 <https://github.com/ethereum/py-evm/pull/935>`_: Protection against eclipse attacks.
- `#869 <https://github.com/ethereum/py-evm/pull/869>`_: Ensure connected peers are on the same side of the DAO fork.

Minor Changes

- `#1081 <https://github.com/ethereum/py-evm/pull/1081>`_: Reduce ``DEBUG`` log output during state sync.
- `#1071 <https://github.com/ethereum/py-evm/pull/1071>`_: Minor fix for how version string is generated for trinity
- `#1070 <https://github.com/ethereum/py-evm/pull/1070>`_: Easier profiling of ``ChainSyncer``
- `#1068 <https://github.com/ethereum/py-evm/pull/1068>`_: Optimize ``evm.db.chain.ChainDB.persist_block`` for common case.
- `#1057 <https://github.com/ethereum/py-evm/pull/1057>`_: Additional ``DEBUG`` logging of peer uptime and msg stats.
- `#1049 <https://github.com/ethereum/py-evm/pull/1049>`_: New integration test suite for trinity CLI
- `#1045 <https://github.com/ethereum/py-evm/pull/1045>`_ `#1051 <https://github.com/ethereum/py-evm/pull/1051>`_: Bugfix for generation of block numbers for ``GetBlockHeaders`` requests.
- `#1011 <https://github.com/ethereum/py-evm/pull/1011>`_: Workaround for parity bug `parity #8038 <https://github.com/paritytech/parity-ethereum/issues/8038>`_
- `#987 <https://github.com/ethereum/py-evm/pull/987>`_: Now serving requests from peers during fast sync.
- `#971 <https://github.com/ethereum/py-evm/pull/971>`_ `#909 <https://github.com/ethereum/py-evm/pull/909>`_ `#650 <https://github.com/ethereum/py-evm/pull/650>`_: Benchmarking test suite.
- `#968 <https://github.com/ethereum/py-evm/pull/968>`_: When launching ``console`` and ``attach`` commands, check for presence of IPC socket and log informative message if not found.
- `#934 <https://github.com/ethereum/py-evm/pull/934>`_: Decouple the ``Discovery`` and ``PeerPool`` services.
- `#913 <https://github.com/ethereum/py-evm/pull/913>`_: Add validation of retrieved contract code when operating in ``--light`` mode.
- `#908 <https://github.com/ethereum/py-evm/pull/908>`_: Bugfix for transitioning from syncing chain data to state data during fast sync.
- `#905 <https://github.com/ethereum/py-evm/pull/905>`_: Support for multiple UPNP devices.


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
