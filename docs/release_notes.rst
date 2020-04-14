Release notes
=============

.. towncrier release notes start

py-evm 0.3.0-alpha.15 (2020-04-14)
----------------------------------

Features
~~~~~~~~

- :meth:`eth.chains.base.Chain.import_block()` now returns some meta-information about the witness.
  You can get a list of trie node hashes needed to build the witness, as well
  as the accesses of accounts, storage slots, and bytecodes. (`#1917
  <https://github.com/ethereum/py-evm/issues/1917>`__)


Internal Changes - for Contributors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Use a more recent eth-keys, which calls an eth-typing that's not deprecated. (`#1665 <https://github.com/ethereum/py-evm/issues/1665>`__)
- Upgrade pytest-xdist from 1.18.1 to 1.31.0, to fix a CI crash. (`#1917 <https://github.com/ethereum/py-evm/issues/1917>`__)
- Added :class:`~eth.db.accesslog.KeyAccessLoggerDB` and its atomic twin; faster ``make
  validate-docs`` (but you have to remember to ``pip install -e .[doc]`` yourself); ``str(block)`` now
  includes some bytes of the block hash. (`#1918 <https://github.com/ethereum/py-evm/issues/1918>`__)
- Fix for creating a duplicate "ghost" Computation that was never used. It didn't
  break anything, but was inelegant and surprising to get extra objects created
  that were mostly useless. This was achieved by changing
  :meth:`eth.abc.ComputationAPI.apply_message` and
  :meth:`eth.abc.ComputationAPI.apply_create_message` to be class methods. (`#1921 <https://github.com/ethereum/py-evm/issues/1921>`__)


py-evm 0.3.0-alpha.14 (2020-02-10)
----------------------------------

Features
~~~~~~~~

- Change return type for ``import_block`` from ``Tuple[BlockAPI, Tuple[BlockAPI, ...], Tuple[BlockAPI, ...]]`` to ``BlockImportResult`` (NamedTuple). (`#1910 <https://github.com/ethereum/py-evm/issues/1910>`__)


Bugfixes
~~~~~~~~

- Fixed a consensus-critical bug for contracts that are created and destroyed in the same block,
  especially pre-Byzantium. (`#1912 <https://github.com/ethereum/py-evm/issues/1912>`__)


Internal Changes - for Contributors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Add explicit tests for ``validate_header`` (`#1911 <https://github.com/ethereum/py-evm/issues/1911>`__)


py-evm 0.3.0-alpha.13 (2020-01-13)
----------------------------------

Features
~~~~~~~~

- Make handling of different consensus mechanisms more flexible and sound.

  1. ``validate_seal`` and ``validate_header`` are now instance methods. The only reason they can
  be classmethods today is because our Pow implementation relies on a globally shared cache
  which should be refactored to use the ``ConsensusContextAPI``.

  2. There a two new methods: ``chain.validate_chain_extension(header, parents)`` and
  ``vm.validate_seal_extension``. They perform extension seal checks to support consensus schemes
  where headers can not be checked if parents are missing.

  3. The consensus mechanism is now abstracted via ``ConsensusAPI`` and ``ConsensusContextAPI``.
  VMs instantiate a consensus api based on the set ``consensus_class`` and pass it a context which
  they receive from the chain upon instantiation. The chain instantiates the consensus context api
  based on the ``consensus_context_class``. (`#1899 <https://github.com/ethereum/py-evm/issues/1899>`__)
- Support Istanbul fork in ``GOERLI_VM_CONFIGURATION`` (`#1904 <https://github.com/ethereum/py-evm/issues/1904>`__)


Bugfixes
~~~~~~~~

- Do not mention PoW in the logging message that we log when `validate_seal` fails.
  The VM could also be running under a non-PoW consensus mechanism. (`#1907 <https://github.com/ethereum/py-evm/issues/1907>`__)


Deprecations and Removals
~~~~~~~~~~~~~~~~~~~~~~~~~

- Drop optional ``check_seal`` param from ``VM.validate_header`` and turn it into a ``classmethod``.
  Seal checks now need to be made explicitly via ``VM.check_seal`` which is also aligned
  with ``VM.check_seal_extension``. (`#1909 <https://github.com/ethereum/py-evm/issues/1909>`__)


py-evm 0.3.0-alpha.12 (2019-12-19)
----------------------------------

Features
~~~~~~~~

- Implement the Muir Glacier fork

  See: https://eips.ethereum.org/EIPS/eip-2387 (`#1901 <https://github.com/ethereum/py-evm/issues/1901>`__)


py-evm 0.3.0-alpha.11 (2019-12-12)
----------------------------------

Bugfixes
~~~~~~~~

- When double-deleting a storage slot, got ``KeyError: (b'\x03', 'key could not be deleted in
  JournalDB, because it was missing')``. This was fallout from `#1893
  <https://github.com/ethereum/py-evm/pull/1893>`_ (`#1898 <https://github.com/ethereum/py-evm/issues/1898>`__)


Performance improvements
~~~~~~~~~~~~~~~~~~~~~~~~

- Improve performance when importing a header which is a child of the current canonical
  chain tip. (`#1891 <https://github.com/ethereum/py-evm/issues/1891>`__)


py-evm 0.3.0-alpha.10 (2019-12-09)
----------------------------------

Bugfixes
~~~~~~~~

- Bug: if data was missing during a call to :meth:`~eth.vm.base.VM.apply_all_transactions`,
  then the call would revert and continue processing transactions. Fix: we re-raise
  the :class:`~eth.exceptions.EVMMissingData` and do not continue processing transactions. (`#1889 <https://github.com/ethereum/py-evm/issues/1889>`__)
- Fix for net gas metering (EIP-2200) in Istanbul. The "original value" used to calculate gas
  costs was incorrectly accessing the value at the start of the block, instead of the start of the
  transaction. (`#1893 <https://github.com/ethereum/py-evm/issues/1893>`__)


Improved Documentation
~~~~~~~~~~~~~~~~~~~~~~

- Add Matomo Tracking to Docs site.

  Matomo is an Open Source web analytics platform that allows us
  to get better insights and optimize for our audience without
  the negative consequences of other compareable platforms.

  Read more: https://matomo.org/why-matomo/ (`#1892 <https://github.com/ethereum/py-evm/issues/1892>`__)


py-evm 0.3.0-alpha.9 (2019-12-02)
---------------------------------

Features
~~~~~~~~

- Add new Chain APIs (`#1887 <https://github.com/ethereum/py-evm/issues/1887>`__):

  - :meth:`~eth.chains.base.Chain.get_canonical_block_header_by_number` (parallel to :meth:`~eth.chains.base.Chain.get_canonical_block_by_number`)
  - :meth:`~eth.chains.base.Chain.get_canonical_transaction_index`
  - :meth:`~eth.chains.base.Chain.get_canonical_transaction_by_index`
  - :meth:`~eth.chains.base.Chain.get_transaction_receipt_by_index`


Bugfixes
~~~~~~~~

- Remove the ice age delay that was accidentally left in Istanbul (`#1877 <https://github.com/ethereum/py-evm/issues/1877>`__)


Improved Documentation
~~~~~~~~~~~~~~~~~~~~~~

- In the API docs display class methods, static methods and methods as one group "methods".
  While we ideally wish to separate these, Sphinx keeps them all as one group which we'll
  be following until we find a better option. (`#794 <https://github.com/ethereum/py-evm/issues/794>`__)
- Tweak layout of API docs to improve readability

  Group API docs by member (methods, attributes) (`#1797 <https://github.com/ethereum/py-evm/issues/1797>`__)
- API doc additions (`#1880 <https://github.com/ethereum/py-evm/issues/1880>`__)

  - Add missing API docs for :class:`~eth.chains.base.MiningChain`.
  - Add missing API docs for :mod:`eth.db.*`
  - Add missing API docs for :class:`~eth.vm.forks.constantinople.ConstantinopleVM`,
    :class:`~eth.vm.forks.petersburg.PetersburgVM` and
    :class:`~eth.vm.forks.istanbul.IstanbulVM` forks
  - Move all docstrings that aren't overly specific to a particular implementation from
    the implementation to the interface. This has the effect that the docstring will
    appear both on the interface as well as on the implementation except for when the
    implementation overwrites the docstring with a more specific descriptions.
- Add docstrings to all public APIs that were still lacking one. (`#1882 <https://github.com/ethereum/py-evm/issues/1882>`__)


py-evm 0.3.0-alpha.8 (2019-11-05)
---------------------------------

Features
~~~~~~~~

- *Partly* implement Clique consensus according to EIP 225. The implementation doesn't yet cover
  a mode of operation that would allow to operate as a signer and create blocks. It does however,
  allow syncing a chain (e.g. Görli) by following the ruleset that is defined in EIP-225. (`#1855 <https://github.com/ethereum/py-evm/issues/1855>`__)
- Set Istanbul block number for mainnet to 9069000, and for Görli to 1561651, as per
  `EIP-1679 <https://eips.ethereum.org/EIPS/eip-1679#activation>`_. (`#1858 <https://github.com/ethereum/py-evm/issues/1858>`__)
- Make the *max length validation* of the `extra_data` field configurable. The reason for that is that
  different consensus engines such as Clique repurpose this field using different max length limits. (`#1864 <https://github.com/ethereum/py-evm/issues/1864>`__)


Bugfixes
~~~~~~~~

- Resolve version conflict regarding `pluggy` dependency that came up during installation. (`#1860 <https://github.com/ethereum/py-evm/issues/1860>`__)
- Fix issue where Py-EVM crashes when `0` is used as a value for `seal_check_random_sample_rate`.
  Previously, this would lead to a DivideByZero error, whereas now it is recognized as not performing
  any seal check. This is also symmetric to the current *opposite* behavior of passing `1` to check
  every single header instead of taking samples. (`#1862 <https://github.com/ethereum/py-evm/issues/1862>`__)
- Improve usability of error message by including hex values of affected hashes. (`#1863 <https://github.com/ethereum/py-evm/issues/1863>`__)
- Gas estimation bugfix: storage values are now correctly reset to original value if the transaction
  includes a self-destruct, when running estimation iterations. Previously, estimation iterations
  would produce undefined results, if the transaction included a self-destruct. (`#1865 <https://github.com/ethereum/py-evm/issues/1865>`__)


Performance improvements
~~~~~~~~~~~~~~~~~~~~~~~~

- Use new `blake2b-py library <https://github.com/davesque/blake2b-py>`_ for 560x speedup of
  Blake2 F compression function. (`#1836 <https://github.com/ethereum/py-evm/issues/1836>`__)


Internal Changes - for Contributors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Update upstream test fixtures to `v7.0.0 beta.1 <https://github.com/ethereum/tests/releases/tag/v7.0.0-beta.1>`_
  and address the two arising disagreements on what accounts should be collected for state trie clearing (as per
  `EIP-161 <https://eips.ethereum.org/EIPS/eip-161>`_) if a nested call frame had an error. (`#1858 <https://github.com/ethereum/py-evm/issues/1858>`__)


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
