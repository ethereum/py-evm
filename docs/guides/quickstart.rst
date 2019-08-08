Quickstart
==========

Installation
~~~~~~~~~~~~

This is the quickstart guide for Trinity. It teaches us how to run a Trinity node as a user.

To develop on top of Trinity or to contribute to the project, check out the
:doc:`Contributing Guide </contributing>` that explains how to set everything up for development.

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

Trinity uses Snappy Compression and hence needs the Snappy Library to be pre-installed on the system.
It can be installed through the following command.

.. code:: sh

  apt-get install libsnappy-dev

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

Now, install Snappy Library with brew as follows:

.. code:: sh

  brew install snappy

Finally, install the ``trinity`` package via pip:

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

**2. Building an image from the source**

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


What's next?
~~~~~~~~~~~~

Now that we've got things running, there's a lot ahead to learn. Check out the existing guides on
Trinity's general :doc:`Architecture </guides/architecture>`, :doc:`Writing Plugins </guides/writing_plugins>`
or scan the :doc:`Cookbook </cookbook>` for short recipes to learn how to:

- :ref:`Run Trinity as a light client<cookbook_recipe_running_as_a_light_client>`
- :ref:`Connect to Mainnet or Ropsten<cookbook_recipe_ropsten_vs_mainnet>`
- :ref:`Connect to preferred nodes<cookbook_recipe_connecting_to_preferred_nodes>`
- :ref:`Retrieve chain information via web3<cookbook_recipe_retrieving_chain_information_via_web3>`
- and many more!


.. warning::

  Trinity is currently in public alpha. **Keep in mind**:

  - It is expected to have bugs and is not meant to be used in production
  - Things may be ridiculously slow or not work at all
  - Only a subset of JSON-RPC API calls are currently supported
