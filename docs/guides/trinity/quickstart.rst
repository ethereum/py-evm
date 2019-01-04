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

  apt-get install python3.6-dev

Trinity is installed through the pip package manager, if pip isn't available on the system already,
we need to install the ``python3-pip`` package through the following command.

.. code:: sh

  apt-get install python3-pip

.. note::
  .. include:: /fragments/virtualenv_explainer.rst

Finally, we can install the ``trinity`` package via pip.

.. code:: sh

  pip3 install -U trinity

Installing on macOS
-------------------

First, install LevelDB and the latest Python 3 with brew:

.. code:: sh

  brew install python3 leveldb

.. note::
  .. include:: /fragments/virtualenv_explainer.rst

Then, install the ``trinity`` package via pip:

.. code:: sh

  pip3 install -U trinity

Installing through Docker
-------------------------

Trinity can also be installed using ``Docker`` which can be a lightweight alternative where no
changes need to be made to the host system apart from having ``Docker`` itself installed.

.. note::
  While we don't officially support Windows just yet, running Trinity through ``Docker`` is a great
  way to bypass this current limitation as Trinity can run on any system that runs ``Docker`` `with
  support for linux containers <https://docs.docker.com/docker-for-windows/#switch-between-windows-and-linux-containers>`_.

Using ``Docker`` we have two different options to choose from.


**1. Run an existing official image**

This is the default way of running Trinity through ``Docker``. If all we care about is running
a Trinity node, using one of the latest released versions, this method is perfect.

Run:

.. code:: sh

  docker run -it ethereum/trinity

Alternatively, we can run a specific image version, following the usual docker version schema.

.. code:: sh

  docker run -it ethereum/trinity:0.1.0-alpha.13

**2. Build your own image**

Alternatively, we may want to try out a specific (unreleased) version. In that case, we can create
our very own image directly from the source code.


.. code:: sh

  make create-docker-image version=my-own-version

After the image has been successfully created, we can run it by invoking:

.. code:: sh

  docker run -it ethereum/trinity:my-own-version

Running Trinity
~~~~~~~~~~~~~~~

After Trinity is installed we should have the ``trinity`` command available to start it.

.. code:: sh

  trinity

While it may take a couple of minutes before Trinity can start syncing against the Ethereum mainnet,
it should print out some valuable information right away which should look something like this.
If it doesn't please `file an issue <https://github.com/ethereum/trinity/issues/new>`_
to help us getting that bug fixed.

.. code:: sh

      INFO  05-29 01:57:02        main  
    ______     _       _ __       
  /_  __/____(_)___  (_) /___  __
    / / / ___/ / __ \/ / __/ / / /
  / / / /  / / / / / / /_/ /_/ / 
  /_/ /_/  /_/_/ /_/_/\__/\__, /  
                        /____/   
      INFO  05-29 01:57:02        main  Trinity/0.1.0a4/linux/cpython3.6.5
      INFO  05-29 01:57:02        main  network: 1
      INFO  05-29 01:57:02         ipc  IPC started at: /root/.local/share/trinity/mainnet/jsonrpc.ipc
      INFO  05-29 01:57:02      server  Running server...
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


Running as a light client
-------------------------

.. warning:: 

    It may take a **very** long time for Trinity to find an LES node with open
    slots.  This is not a bug with trinity, but rather a shortage of nodes
    serving LES.  Please consider running your own LES server to help improve
    the health of the network.

Use the ``--light`` flag to instruct Trinity to run as a light node.


Ropsten vs Mainnet
------------------

Trinity currently only supports running against either the Ethereum Mainnet or
Ropsten testnet.  Use ``--ropsten`` to run against Ropsten.


.. code:: sh

  trinity --ropsten



Connecting to preferred nodes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you would like to have Trinity prioritize connecting to specific nodes, you
can use the ``--preferred-node`` command line flag.  This flag takes an enode
URI as a single argument and will instruct Trinity to prioritize connecting to
this node.

.. code:: sh

  trinity --preferred-node enode://a41defa74e8d9d4152699cb9a0d195377da95833769ad6b386092ac3b16c184eb4ef4b4f02889e0b5097ff50fb5847ba99694d40b61f911cdea07b444b00e676@127.0.0.1:30304


Using ``--preferred-node`` is a good way to ensure Trinity running in
``--light`` mode connects to known peers who serve LES.


Retrieving Chain information via web3
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

While just running ``trinity`` already causes the node to start syncing, it doesn't let us interact
with the chain directly (apart from the JSON-RPC API).

However, we can attach an interactive shell to a running Trinity instance with the
``attach`` subcommand. The interactive ``ipython`` shell binds a
`web3 <http://web3py.readthedocs.io>`_ instance to the ``w3`` variable.

.. code:: sh

  trinity attach

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

You can attach to an existing Trinity process using the ``attach`` comand.

.. code:: sh

  trinity attach

For a list of JSON-RPC endpoints which are expected to work, see this issue: https://github.com/ethereum/py-evm/issues/178




.. warning::

  Trinity is currently in public alpha. **Keep in mind**:

  - It is expected to have bugs and is not meant to be used in production
  - Things may be ridiculously slow or not work at all
  - Only a subset of JSON-RPC API calls are currently supported


