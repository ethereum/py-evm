Quickstart
==========

Installation
~~~~~~~~~~~~

This is the quickstart guide for Trinity. If you only care about running a Trinity node, this
guide will help you to get things set up. If you plan to develop on top of Py-EVM or contribute
to the project you may rather want to checkout the :doc:`Contributing Guide </contributing>` which
explains how to set everything up for development.

Installing on Ubuntu
--------------------

Trinity requires Python 3.6 as well as some tools to compile its dependencies. On Ubuntu, the
``python3.6-dev`` package contains everything we need. Run the following command to install it.

.. code:: sh

  apt-get python3.6-dev

Trinity is installed through the pip package manager, if pip isn't available on the system already,
we need to install the ``python3-pip`` package through the following command.

.. code:: sh

  apt-get python3-pip

Finally, we can install the ``trinity`` package via pip.

.. code:: sh

  pip3 install trinity

Running Trinity
~~~~~~~~~~~~~~~

After Trinity is installed we should have the ``trinity`` command available to start it.

.. code:: sh

  trinity

While it may take a couple of minutes before Trinity can start syncing against the Ethereum mainnet,
it should print out some valuable information right away which should look something like this.
If it doesn't please `file an issue <https://github.com/ethereum/py-evm/issues/new>`_
to help us getting that bug fixed.

.. code:: sh

      INFO  05-29 01:57:02        main  
    ______     _       _ __       
  /_  __/____(_)___  (_) /___  __
    / / / ___/ / __ \/ / __/ / / /
  / / / /  / / / / / / /_/ /_/ / 
  /_/ /_/  /_/_/ /_/_/\__/\__, /  
                        /____/   
      INFO  05-29 01:57:02        main  Trinity/0.2.0a18/linux/cpython3.6.5
      INFO  05-29 01:57:02        main  enode://781245c14c5885cf79df99e233733ec7a8fcdf8a9e3bfeef50aedd43b3e42d03@[:]:30303
      INFO  05-29 01:57:02        main  network: 1
      INFO  05-29 01:57:02         ipc  IPC started at: /root/.local/share/trinity/mainnet/jsonrpc.ipc
      INFO  05-29 01:57:02      server  Running server...
      INFO  05-29 01:57:07      server  No UPNP-enabled devices found
      INFO  05-29 01:57:07      server  enode://09d34ecb0de1806ab0e68cb2d822b967292dc021df06aab9a55aa4d2e1b2e04ae73560137407a48073286026e12dd60d265a1b1ae0505e44e60d55cea9c7b100@0.0.0.0:30303
      INFO  05-29 01:57:07      server  network: 1
      INFO  05-29 01:57:07        peer  Running PeerPool...
      INFO  05-29 01:57:07        sync  Starting fast-sync; current head: #0

Once Trinity successfully connected to other peers we should see it starting to sync the chain.

.. code:: sh

  INFO  05-29 02:23:13       chain  Starting sync with ETHPeer <Node(0xaff0@90.114.124.196)>
  INFO  05-29 02:23:14       chain  Imported chain segment in 0 seconds, new head: #191 (739b)
  INFO  05-29 02:23:15       chain  Imported chain segment in 0 seconds, new head: #383 (789c)
  INFO  05-29 02:23:16       chain  Imported chain segment in 0 seconds, new head: #575 (a1d0)
  INFO  05-29 02:23:17       chain  Imported chain segment in 0 seconds, new head: #767 (aeb6)

Retrieving Chain information via web3
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

While just running ``trinity`` will start syncing the chain just fine, it doesn't let us interact
with the chain directly (apart from the JSON-RPC API). However, we can run Trinity with the
``console`` subcommand to get an interactive ``ipython`` shell that binds a
`web3 <http://web3py.readthedocs.io>`_ instance to the ``w3`` variable.

.. code:: sh

  trinity console

Now that Trinity runs in an interactive shell mode, let's try to get some information about the
latest block by calling ``w3.eth.getBlock('latest')``.

.. code:: sh

  In [9]: w3.eth.getBlock('latest')
  Out[9]: 
  AttributeDict({'difficulty': 743444339302,
  'extraData': HexBytes('0x476574682f4c5649562f76312e302e302f6c696e75782f676f312e342e32'),
  'gasLimit': 5000,
  'gasUsed': 0,
  'hash': HexBytes('0x1a8487dfb8de7ee27b9cca30b6f3f6c9676eae29c10eef39b86890ed15eeed01'),
  'logsBloom': HexBytes('0x00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'),
  'mixHash': HexBytes('0xf693b8e4bc30728600da40a0578c14ddb7ad08a64e329a19d9355d5665588aef'),
  'nonce': HexBytes('0x7382884a72533c59'),
  'number': 12479,
  'parentHash': HexBytes('0x889c36c51463f100cf50ec2e2a92886aa7ebb3f99fa8c817343214a92f967a29'),
  'receiptsRoot': HexBytes('0x56e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421'),
  'sha3Uncles': HexBytes('0x1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347'),
  'stateRoot': HexBytes('0x6ad1ecb7d516c679e7c476956159051fa32848f3ba631a47c3fb72937ed86987'),
  'timestamp': 1438368997,
  'transactionsRoot': HexBytes('0x56e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421'),
  'miner': '0xbb7B8287f3F0a933474a79eAe42CBCa977791171',
  'totalDifficulty': 3961372514945562,
  'uncles': [],
  'size': 544,
  'transactions': []})

.. warning::

  Trinity is currently in public alpha. **Keep in mind**:

  - It is expected to have bugs and is not meant to be used in production
  - Things may be ridiculously slow or not work at all
  - Only a subset of JSON-RPC API calls are currently supported