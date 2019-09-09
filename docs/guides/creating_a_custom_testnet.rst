Creating a custom developer testnet
===================================

In this guide we'll learn how to use Trinity to run a custom developer testnet.

Background
~~~~~~~~~~

Although Trinity's default mode uses the *Mainnet* and *Ropsten* can be enabled via the
``--ropsten`` flag, network support does not end with these two networks.

Trinity connects to various networks via configuration files according to
`EIP-1085 <https://github.com/ethereum/EIPs/issues/1085>`_ and while it ships with support for
*Mainnet* and *Ropsten*, we can also create our own configuration files to connect to other
networks.




The genesis configuration file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Trinity's chain support is read from a configuration file. We can even look up the
specific configuration files for *Mainnet* and *Ropsten* in the *assets* directory of Trinity's
source code.

The configuration file describes:

- The mechanism by which blocks are mined

- The block number at which a specific set of EVM rules should apply

- The genesis block parameters

- The genesis account states


Creating a custom chain for local development
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Now that we have learned about the mechanism that enables Trinity to support different networks,
let's build a network just for us! Building our own network can be useful for local development
and testing, but it's also an exciting way to get to familiarize ourselves with Trinity!

.. warning::

  Trinity does currently only support Proof-Of-Work (POW) based networks. For general purpose testnets,
  Proof-Of-Authority (POA) is more useful. What we are building in this guide is a fun exercise to
  get familar with the general chain configuration support. **Don't build POW test nets for productive use.**


Creating our own configuration file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

We start by creating a ``devnet.json`` file.

.. literalinclude:: ../../trinity/assets/eip1085/devnet.json
   :language: json

There are several interesting things to highlight here:


- All numbers except for the ``version`` are written in hexadecimal.

  - e.g. a ``gasLimit`` of ``0x900000`` means ``9437184`` in decimal.

- We give a balance to two accounts: ``0x00000000000000000000000000000000deadbeef`` and
  ``0x00000000000000000000000000000000deadcafe``.

- Because this is our very own development network we can make the ``gasLimit`` any number we want!

  - setting a very high gas limit can be useful for testing smart contracts that arent't yet optimized
    for efficient gas use.

- We chose a really low difficulty of ``0x1`` so that we can mine blocks cheaply.

- Notice that we set ``petersburgForkBlock`` to ``0x0``. It means that the EVM rules of the ``Petersburg``
  fork will apply from the very first block on.

  - We are free to apply any supported EVM rules to any particular range of blocks but we chose to
    simply start with the latest rule that exist at the time of writing.


Let's run our first node
~~~~~~~~~~~~~~~~~~~~~~~~

Now that we have defined the parameters of our network, let's run a node! Since Trinity does not
know about our network yet, we need to tell it about our configuration file, the data directory it
should use as well as the id of the new network.

.. code:: sh

  trinity --genesis /tmp/devnet.json --trinity-root-dir /tmp/node1 --data-dir /tmp/node1/devnet --network-id 4711

As we observe Trinity booting, we should look out for two important pieces of information it will print:

- The ``enode`` URI of our node
- The current block header

.. code:: sh

  enode://f07d2459f82148d11a033c00353a0efb798ef585da9cade0d7196160a5c5b55e6c7efd95288df083b4f417a36f9f6189b4b2e5ade0f456ce131c701f78f64a41@0.0.0.0:30303
  ...
  Starting beam-sync; current head: <BlockHeader #0 065fd78e>


Mining the chain
~~~~~~~~~~~~~~~~

Obviously, this exercise is much more fun if we can get **two nodes** to sync! But before we get
there we need to have an actual chain, otherwise, both nodes would just be stuck at the very same
genesis header.

Trinity does not support an actual mining mode which tries to continously create blocks.
However, we can create blocks manually on a REPL. Buckle up!

We'll run almost the same command as before but with the subcommand `db-shell` appended.

.. code:: sh

  trinity --genesis /tmp/devnet.json --trinity-root-dir /tmp/node1 --data-dir /tmp/node1/devnet --network-id 4711 db-shell

Think of the ``db-shell`` as a built-in developer tool for Trinity. Today, we'll hijack it to create
some blocks!

.. code:: sh

  Trinity DB Shell
  ---------------
  An instance of `ChainDB` connected to the database is available as the `chaindb` variable

      Head: #0
      Hash: 0x065fd78e53dcef113bf9d7732dac7c5132dcf85c9588a454d832722ceb097422
      State Root: 0x96afaf18b5d2a2c2b0f2e670ba7d3d8d60d56d42398185e94adcdc95362811d3
      Inspecting active Trinity? False

      Available Context Variables:
        - `db`: base database object
        - `chaindb`: `ChainDB` instance
        - `trinity_config`: `TrinityConfig` instance
        - `chain_config`: `ChainConfig` instance
        - `chain`: `Chain` instance
        - `mining_chain: `MiningChain` instance. (use a REPL to create blocks)

  In [1]:

Let's just copy the following lines and paste them in and hit enter.

.. code:: python

  from eth.consensus.pow import mine_pow_nonce
  block = mining_chain.get_vm().finalize_block(mining_chain.get_block())
  nonce, mix_hash = mine_pow_nonce(block.number, block.header.mining_hash, block.header.difficulty)
  mining_chain.mine_block(mix_hash=mix_hash, nonce=nonce)

We should see a freshly mined block!

.. code:: sh

  Out[4]: <PetersburgBlock(#Block #1)>

We can repeat this for as many blocks as we like.

If we start Trinity again in it's normal mode of operation (without ``db-shell``) we should see it
acknowleding our new blocks.

.. code:: sh

  Starting beam-sync; current head: <BlockHeader #4 4c71d77b>


Getting a second node to catch up
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

We're almost there, what's left to do is to open up another terminal to spin up a second node
while our first node is also running.

Considering that we are running both of these Trinity nodes on the same host computer we have
to take care that:

1. We choose a different ``trinity-root-dir`` for the second node
2. We run the second node on a different network port.

Also without bootnodes and our super tiny network of just two nodes, we can not expect both nodes
to find each other so we have to use the ``enode`` URI from the first node and feed it to
our second node via the ``--preferred-node`` flag.

With that in mind, let's go:

.. code:: sh

  trinity --genesis /tmp/devnet.json --trinity-root-dir /tmp/node2 --data-dir /tmp/node2/devnet --network-id 4711 --port 30305 --preferred-node enode://f07d2459f82148d11a033c00353a0efb798ef585da9cade0d7196160a5c5b55e6c7efd95288df083b4f417a36f9f6189b4b2e5ade0f456ce131c701f78f64a41@0.0.0.0:30303

Voila! Here we go.

.. code:: sh

  Starting beam-sync; current head: <BlockHeader #0 065fd78e>
  ...
  Finished beam-sync; previous head: <BlockHeader #0 065fd78e>, current head: <BlockHeader #4 4c71d77b>
  Missing state for current head <BlockHeader #4 4c71d77b>, downloading it
  Starting state sync for root hash 0xd548c6d3b14d0549bf1aeaa413769f5877c72c3e88b5c82f916a6c3b2f955daa

Notice, how the second node starts off from the same genesis as our first node and then quickly catches
up to the blocks that we had manually mined before.