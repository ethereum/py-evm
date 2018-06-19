Trinity 
=======


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
