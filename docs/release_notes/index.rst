Release notes
=============

Unreleased (latest source)
--------------------------

- `#1732 <https://github.com/ethereum/py-evm/pull/1732>`_: Bugfix: squashed an occasional "mix hash mismatch" while syncing

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
