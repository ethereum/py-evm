Release notes
=============

.. towncrier release notes start

py-evm 0.3.0-alpha.7 (2019-09-19)
---------------------------------

Features
~~~~~~~~

- Enable Istanbul fork on Ropsten chain (`#1851 <https://github.com/ethereum/py-evm/issues/1851>`__)


Bugfixes
~~~~~~~~

- Update codebase to more consistently use the ``eth_typing.BlockNumber`` type. (`#1850 <https://github.com/ethereum/py-evm/issues/1850>`__)


py-evm 0.3.0-alpha.6 (2019-09-05)
---------------------------------

Features
~~~~~~~~

- Add EIP-1344 to Istanbul: Chain ID Opcode (`#1817 <https://github.com/ethereum/py-evm/issues/1817>`__)
- Add EIP-152 to Istanbul: Blake2b F Compression precompile at address 9 (`#1818 <https://github.com/ethereum/py-evm/issues/1818>`__)
- Add EIP-2200 to Istanbul: Net gas metering (`#1825 <https://github.com/ethereum/py-evm/issues/1825>`__)
- Add EIP-1884 to Istanbul: Reprice trie-size dependent opcodes (`#1826 <https://github.com/ethereum/py-evm/issues/1826>`__)
- Add EIP-2028: Transaction data gas cost reduction (`#1832 <https://github.com/ethereum/py-evm/issues/1832>`__)
- Expose type hint information via PEP561 (`#1845 <https://github.com/ethereum/py-evm/issues/1845>`__)


Bugfixes
~~~~~~~~

- Add missing ``@abstractmethod`` decorator to ``ConfigurableAPI.configure``. (`#1822 <https://github.com/ethereum/py-evm/issues/1822>`__)


Performance improvements
~~~~~~~~~~~~~~~~~~~~~~~~

- ~20% speedup on "simple value transfer" benchmarks, ~10% overall benchmark lift. Optimized retrieval
  of transactions and receipts from the trie database. (`#1841 <https://github.com/ethereum/py-evm/issues/1841>`__)


Improved Documentation
~~~~~~~~~~~~~~~~~~~~~~

- Add a "Performance improvements" section to the release notes (`#1841 <https://github.com/ethereum/py-evm/issues/1841>`__)


Deprecations and Removals
~~~~~~~~~~~~~~~~~~~~~~~~~

- Upgrade to ``eth-utils>=1.7.0`` which removes the ``eth.tools.logging`` module implementations of ``ExtendedDebugLogger`` in favor of the ones exposed by the ``eth-utils`` library.  This also removes the automatic setup of the ``DEBUG2`` logging level which was previously a side effect of importing the ``eth`` module.  See ``eth_utils.setup_DEBUG2_logging`` for more information. (`#1846 <https://github.com/ethereum/py-evm/issues/1846>`__)


py-evm 0.3.0-alpha.5 (2019-08-22)
---------------------------------

Features
~~~~~~~~

- Add EIP-1108 to Istanbul: Reduce EC precompile costs (`#1819 <https://github.com/ethereum/py-evm/issues/1819>`__)


Bugfixes
~~~~~~~~

- Make sure ``persist_checkpoint_header`` sets the given header as canonical head. (`#1830 <https://github.com/ethereum/py-evm/issues/1830>`__)


Improved Documentation
~~~~~~~~~~~~~~~~~~~~~~

- Remove section on Trinity's goals from the Readme. It's been a leftover from when
  Py-EVM and Trinity where hosted in a single repository. (`#1827 <https://github.com/ethereum/py-evm/issues/1827>`__)


py-evm 0.3.0-alpha.4 (2019-08-19)
---------------------------------

Features
~~~~~~~~

- Add an *optional* ``genesis_parent_hash`` parameter to
  :meth:`~eth.db.header.HeaderDB.persist_header_chain` and
  :meth:`~eth.db.chain.ChainDB.persist_block` that allows to overwrite the hash that is used
  to identify the genesis header. This allows persisting headers / blocks that aren't (yet)
  connected back to the true genesis header.

  This feature opens up new, faster syncing techniques. (`#1823 <https://github.com/ethereum/py-evm/issues/1823>`__)


Bugfixes
~~~~~~~~

- Add missing ``@abstractmethod`` decorator to ``ConfigurableAPI.configure``. (`#1822 <https://github.com/ethereum/py-evm/issues/1822>`__)


Deprecations and Removals
~~~~~~~~~~~~~~~~~~~~~~~~~

- Remove ``AsyncHeaderDB`` that wasn't used anywhere (`#1823 <https://github.com/ethereum/py-evm/issues/1823>`__)


py-evm 0.3.0-alpha.3 (2019-08-13)
---------------------------------

Bugfixes
~~~~~~~~

- Add back missing ``Chain.get_vm_class`` method. (`#1821 <https://github.com/ethereum/py-evm/issues/1821>`__)


py-evm 0.3.0-alpha.2 (2019-08-13)
---------------------------------

Features
~~~~~~~~

- Package up test suites for the ``DatabaseAPI`` and ``AtomicDatabaseAPI`` to be class-based to make them reusable by other libaries. (`#1813 <https://github.com/ethereum/py-evm/issues/1813>`__)


Bugfixes
~~~~~~~~

- Fix a crash during chain reorganization on a header-only chain (which can happen during Beam Sync) (`#1810 <https://github.com/ethereum/py-evm/issues/1810>`__)


Improved Documentation
~~~~~~~~~~~~~~~~~~~~~~

- Setup towncrier to generate release notes from fragment files to  ensure a higher standard
  for release notes. (`#1796 <https://github.com/ethereum/py-evm/issues/1796>`__)


Deprecations and Removals
~~~~~~~~~~~~~~~~~~~~~~~~~

- Drop StateRootNotFound as an over-specialized version of EVMMissingData.
  Drop VMState.execute_transaction() as redundant to VMState.apply_transaction(). (`#1809 <https://github.com/ethereum/py-evm/issues/1809>`__)


v0.3.0-alpha.1
--------------------------

Released 2019-06-05
(off-schedule release to handle eth-keys dependency issue)

- `#1785 <https://github.com/ethereum/py-evm/pull/1785>`_: Breaking Change: Dropped python3.5 support
- `#1788 <https://github.com/ethereum/py-evm/pull/1788>`_: Fix dependency issue with eth-keys, don't allow v0.3+ for now


0.2.0-alpha.43
--------------------------

Released 2019-05-20

- `#1778 <https://github.com/ethereum/py-evm/pull/1778>`_: Feature: Raise custom decorated exceptions when a trie node is missing from the database (plus some bonus logging and performance improvements)
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
  - `#1773 <https://github.com/ethereum/py-evm/pull/1773>`_: Faster stack operations, ~9% speedup
  - `#1776 <https://github.com/ethereum/py-evm/pull/1776>`_: Faster Journal record & commit checkpoints, ~7% speedup
  - `#1777 <https://github.com/ethereum/py-evm/pull/1777>`_: Faster bytecode navigation, ~7% speedup
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
