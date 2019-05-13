Release notes
=============

Unreleased (latest source)
--------------------------

- `#1732 <https://github.com/ethereum/py-evm/pull/1732>`_: Bugfix: squashed an occasional "mix hash mismatch" while syncing
- `#1716 <https://github.com/ethereum/py-evm/pull/1716>`_: Performance: only calculate & persist state root at end of block (post-Byzantium)
- `#1735 <https://github.com/ethereum/py-evm/pull/1735>`_:

  - Performance: only calculate & persist storage roots at end of block (post-Byzantium)
  - Performance: batch all account trie writes to the database once per block
- `#1747 <https://github.com/ethereum/py-evm/pull/1747>`_:

  - Maintenance: Lazily generate VM.block on first access. Enables loading the VM when you don't have its block body.
  - Performance: Fewer DB reads when block is never accessed.
- Performance: speedups on ``chain.import_block()``:

  - `#1764 <https://github.com/ethereum/py-evm/pull/1764>`_: Speed up ``is_valid_opcode`` check, formerly 7% of total import time! (now less than 1%)
  - `#1765 <https://github.com/ethereum/py-evm/pull/1765>`_: Reduce logging overhead, ~15% speedup
  - `#1766 <https://github.com/ethereum/py-evm/pull/1766>`_: Cache transaction sender, ~3% speedup
  - `#1770 <https://github.com/ethereum/py-evm/pull/1770>`_: Faster bytecode iteration, ~2.5% speedup
  - `#1771 <https://github.com/ethereum/py-evm/pull/1771>`_: Faster opcode lookup in apply_computation, ~1.5% speedup
  - `#1772 <https://github.com/ethereum/py-evm/pull/1772>`_: Faster Journal access of latest data, ~6% speedup
  - `#1776 <https://github.com/ethereum/py-evm/pull/1776>`_: Faster Journal record & commit checkpoints, ~7% speedup
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
