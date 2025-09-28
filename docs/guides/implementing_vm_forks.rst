Implementing VM forks
=====================

The Ethereum protocol follows specified rules which continue to be improved through so called
`Ethereum Improvement Proposals (EIPs) <https://eips.ethereum.org/>`_. Every now and then the
community agrees on a few EIPs to become part of the next protocol upgrade. These upgrades happen
through so called `Hardforks <https://en.wikipedia.org/wiki/Fork_(blockchain)>`_ which define:

1. A name for the set of rule changes (e.g. the Istanbul hardfork)
2. A block number from which on blocks are processed according to these new rules (e.g. ``9069000``)

Every client that wants to support the official Ethereum protocol needs to implement these changes
to remain functional.


This guide covers how to implement new hardforks in Py-EVM. The specifics and impact of each rule
change many vary a lot between different hardforks and it is out of the scope of this guide to
cover these in depth. This is mainly a reference guide for developers to ensure the process of
implementing hardforks in Py-EVM is as smooth and safe as possible.


Creating the fork module
------------------------

Every fork is encapsulated in its own module under ``eth.vm.forks.<fork-name>``. To create the
scaffolding for a new fork run ``python scripts/forking/create_fork.py`` and follow the assistent.

.. code:: sh

  $ python scripts/forking/create_fork.py 
  Specify the name of the fork (e.g Muir Glacier):
  -->ancient tavira
  Specify the fork base (e.g Istanbul):
  -->istanbul
  Check your inputs:
  New fork:
  Writing(pascal_case='AncientTavira', lower_dash_case='ancient-tavira', lower_snake_case='ancient_tavira', upper_snake_case='ANCIENT_TAVIRA')
  Base fork:
  Writing(pascal_case='Istanbul', lower_dash_case='istanbul', lower_snake_case='istanbul', upper_snake_case='ISTANBUL')
  Proceed (y/n)?
  -->y
  Your fork is ready!


Configuring new opcodes
-----------------------

Configuring new precompiles
---------------------------

Activating the fork
-------------------

Ethereum is a protocol that powers different networks. Most notably, the ethereum mainnet but there
are also other networks such as testnetworks (e.g. Görli) or xDai. If and when a specific network
will activate a concrete fork remains to be configured on a per network basis.

At the time of writing, Py-EVM has supports the following three networks:

- Mainnet
- Ropsten
- Goerli

For each network that wants to activate the fork, we have to create a new constant in
``eth/chains/<network>/constants.py`` that describes the block number at which the fork becomes
active as seen in the following example:

.. literalinclude:: ../../eth/chains/mainnet/constants.py
   :language: python
   :start-after: BYZANTIUM_MAINNET_BLOCK
   :end-before: # Istanbul Block

Then,


Wiring up the tests
-------------------
