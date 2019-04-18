Release notes
=============

Unreleased (latest source)
--------------------------

- `#1732 <https://github.com/ethereum/py-evm/pull/1732>`_: Bugfix: squashed an occasional "mix hash mismatch" while syncing
- `#1716 <https://github.com/ethereum/py-evm/pull/1716>`_: Performance: only calculate & persist state root at end of block (post-Byzantium)
- `#1747 <https://github.com/ethereum/py-evm/pull/1747>`_: Maintenance: Lazily generate VM.block on first access. Enables loading the VM when you don't have its block body.
- `#1747 <https://github.com/ethereum/py-evm/pull/1747>`_: Performance: Same as above ^. Fewer DB reads when block is never accessed.
- `#1751 <https://github.com/ethereum/py-evm/pull/1751>`_: Maintenance: Add placeholder for Istanbul fork

0.2.0-alpha.42
--------------------------

Released 2019-02-28

- `#1719 <https://github.com/ethereum/py-evm/pull/1719>`_: Implement and activate Petersburg fork (aka Constantinople fixed)
- `#1718 <https://github.com/ethereum/py-evm/pull/1718>`_: Performance: faster account lookups in EVM
- `#1670 <https://github.com/ethereum/py-evm/pull/1670>`_: Performance: lazily look up ancestor block hashes, and cache result, so looking up parent hash in EVM is faster than grand^100 parent


0.2.0-alpha.40
--------------

Released Jan 15, 2019

- `#1717 <https://github.com/ethereum/py-evm/pull/1717>`_: Indefinitely postpone the pending Constantinople release
- `#1715 <https://github.com/ethereum/py-evm/pull/1715>`_: Remove Eth2 Beacon code, moving to
  trinity project
