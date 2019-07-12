Command Line Interface (CLI)
============================

The following is a brief description of all the configurations available on the command line.
We can also generate an always up-to-date version of them by running ``trinity --help``.

.. code-block:: shell

    usage: trinity [-h] [--version] [--trinity-root-dir TRINITY_ROOT_DIR]
                [--port PORT] [-l LEVEL] [--stderr-log-level STDERR_LOG_LEVEL]
                [--file-log-level FILE_LOG_LEVEL]
                [--network-id NETWORK_ID | --ropsten]
                [--preferred-node PREFERRED_NODES] [--discv5]
                [--max-peers MAX_PEERS] [--genesis GENESIS]
                [--data-dir DATA_DIR] [--nodekey NODEKEY] [--profile]
                [--disable-rpc]
                [--network-tracking-backend {sqlite3,memory,do-not-track}]
                [--disable-networkdb-plugin] [--disable-blacklistdb]
                [--disable-eth1-peer-db]
                [--enable-experimental-eth1-peer-tracking]
                [--disable-discovery] [--disable-request-server]
                [--disable-upnp] [--ethstats]
                [--ethstats-server-url ETHSTATS_SERVER_URL]
                [--ethstats-server-secret ETHSTATS_SERVER_SECRET]
                [--ethstats-node-id ETHSTATS_NODE_ID]
                [--ethstats-node-contact ETHSTATS_NODE_CONTACT]
                [--ethstats-interval ETHSTATS_INTERVAL]
                [--sync-mode {fast,full,beam,light,none}] [--tx-pool]
                {attach,fix-unclean-shutdown,remove-network-db,db-shell} ...

    positional arguments:
    {attach,fix-unclean-shutdown,remove-network-db,db-shell}
        attach              open an REPL attached to a currently running chain
        fix-unclean-shutdown
                            close any dangling processes from a previous unclean
                            shutdown
        remove-network-db   Remove the on-disk sqlite database that tracks data
                            about the p2p network
        db-shell            open a REPL to inspect the db

    optional arguments:
    -h, --help            show this help message and exit
    --disable-rpc         Disables the JSON-RPC Server
    --disable-discovery   Disable peer discovery
    --disable-request-server
                            Disables the Request Server
    --disable-upnp        Disable upnp mapping
    --tx-pool             Enables the Transaction Pool (experimental)

    core:
    --version             show program's version number and exit
    --trinity-root-dir TRINITY_ROOT_DIR
                            The filesystem path to the base directory that trinity
                            will store it's information. Default:
                            $XDG_DATA_HOME/.local/share/trinity
    --port PORT           Port on which trinity should listen for incoming
                            p2p/discovery connections. Default: 30303

    logging:
    -l LEVEL, --log-level LEVEL
                            Configure the logging level. LEVEL must be one of:
                            8/10/20/30/40/50 (numeric);
                            debug2/debug/info/warn/warning/error/critical
                            (lowercase);
                            DEBUG2/DEBUG/INFO/WARN/WARNING/ERROR/CRITICAL
                            (uppercase).
    --stderr-log-level STDERR_LOG_LEVEL
                            Configure the logging level for the stderr logging.
    --file-log-level FILE_LOG_LEVEL
                            Configure the logging level for file-based logging.

    network:
    --network-id NETWORK_ID
                            Network identifier (1=Mainnet, 3=Ropsten)
    --ropsten             Ropsten network: pre configured proof-of-work test
                            network. Shortcut for `--networkid=3`
    --preferred-node PREFERRED_NODES
                            An enode address which will be 'preferred' above nodes
                            found using the discovery protocol
    --discv5              Enable experimental v5 (topic) discovery mechanism
    --max-peers MAX_PEERS
                            Maximum number of network peers

    chain:
    --genesis GENESIS     File containing a custom genesis block header
    --data-dir DATA_DIR   The directory where chain data is stored
    --nodekey NODEKEY     Hexadecimal encoded private key to use for the nodekey
                            or the filesystem path to the file which contains the
                            nodekey

    debug:
    --profile             Enables profiling via cProfile.

    network db:
    --network-tracking-backend {sqlite3,memory,do-not-track}
                            Configure whether nodes are tracked and how. (sqlite3:
                            persistent tracking across runs from an on-disk
                            sqlite3 database, memory: tracking only in memory, do-
                            not-track: no tracking)
    --disable-networkdb-plugin
                            Disables the builtin 'Networkt Database' plugin.
                            **WARNING**: disabling this API without a proper
                            replacement will cause your trinity node to crash.
    --disable-blacklistdb
                            Disables the blacklist database server component of
                            the Network Database plugin.**WARNING**: disabling
                            this API without a proper replacement will cause your
                            trinity node to crash.
    --disable-eth1-peer-db
                            Disables the ETH1.0 peer database server component of
                            the Network Database plugin.**WARNING**: disabling
                            this API without a proper replacement will cause your
                            trinity node to crash.
    --enable-experimental-eth1-peer-tracking
                            Enables the experimental tracking of metadata about
                            successful connections to Eth1 peers.

    ethstats (experimental):
    --ethstats            Enable node stats reporting service
    --ethstats-server-url ETHSTATS_SERVER_URL
                            Node stats server URL (e. g. wss://example.com/api)
    --ethstats-server-secret ETHSTATS_SERVER_SECRET
                            Node stats server secret
    --ethstats-node-id ETHSTATS_NODE_ID
                            Node ID for stats server
    --ethstats-node-contact ETHSTATS_NODE_CONTACT
                            Node contact information for stats server
    --ethstats-interval ETHSTATS_INTERVAL
                            The interval at which data is reported back

    sync mode:
    --sync-mode {fast,full,beam,light,none}


Attach a REPL to a running Trinity instance
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

We can attach a REPL to a running Trinity instance to perform RPC request or
interact with a web3 instance.

.. code-block:: shell

    usage: trinity attach [-h] [ipc_path]
    positional arguments:
        ipc_path    Specify an IPC path
    optional arguments:
        -h, --help  show this help message and exit

Check out the :doc:`Quickstart </guides/quickstart>` for a full example.


Per-module logging
~~~~~~~~~~~~~~~~~~

Trinity provides rich logging output that can be of tremendous help during debugging. By default,
Trinity prints only logs of level ``INFO`` or higher to ``stderr`` and only logs of level ``DEBUG``
or higher to the log file.

This can be adjusted to other log level such as ``ERROR`` or ``DEBUG2`` and independently for both
the ``stderr`` and the file log.

Starting Trinity with ``trinity --log-level DEBUG2`` (shorthand: ``trinity -l DEBUG2``) yields the
absolute maximum of available logging output. However, running Trinity with maximum logging output
might be too overwhelming when we are only interested in logging output for a specific
module (e.g. ``p2p.discovery``).

Fortunately, Trinity allows us to configure logging on a per-module basis by using the
``--log-level`` flag in combination with specific modules and log levels such as in:
``trinity --log-level DEBUG2 --log-level p2p.discovery=ERROR``.

The following table shows various combinations of how to use logging in Trinity effectively.


+---------------------------------------------------------------------+--------------------------------+------------------------------+
| Command                                                             | Stderr log [1]_                | File log [1]_                |
+=====================================================================+================================+==============================+
| ``trinity``                                                         | ``INFO`` [2]_                  | ``DEBUG`` [2]_               |
+---------------------------------------------------------------------+--------------------------------+------------------------------+
| ``trinity --stderr-log-level ERROR``                                | ``ERROR``                      | ``DEBUG``                    |
+---------------------------------------------------------------------+--------------------------------+------------------------------+
| ``trinity --file-log-level INFO``                                   | ``INFO``                       | ``INFO``                     |
+---------------------------------------------------------------------+--------------------------------+------------------------------+
| | ``trinity --file-log-level ERROR``                                | ``ERROR``                      | ``ERROR``                    |
| | ``--stderr-log-level ERROR``                                      |                                |                              |
+---------------------------------------------------------------------+--------------------------------+------------------------------+
| ``trinity --log-level ERROR`` (``trinity -l ERROR``) [3]_           | ``ERROR``                      | ``ERROR``                    |
+---------------------------------------------------------------------+--------------------------------+------------------------------+
| ``trinity --l DEBUG2 -l 'p2p.discovery=ERROR'`` [4]_                | | ``DEBUG2`` but **only**      | | ``DEBUG2`` but **only**    |
|                                                                     | | ``ERROR`` for                | | ``ERROR`` for              |
|                                                                     | | ``p2p.discovery``            | | ``p2p.discovery``          |
+---------------------------------------------------------------------+--------------------------------+------------------------------+
| ``trinity --l ERROR -l 'p2p.discovery=DEBUG2'`` [4]_                | | ``ERROR`` but **also**       | ``ERROR`` [5]_               |
|                                                                     | | ``DEBUG2`` for               |                              |
|                                                                     | | ``p2p.discovery``            |                              |
+---------------------------------------------------------------------+--------------------------------+------------------------------+

.. [1] A stated level e.g. ``DEBUG2`` **always means** that log level **or higher** (e.g. ``INFO``)

.. [2] ``INFO`` is the default log level for the ``stderr`` log, ``DEBUG`` the default log level for the file log.

.. [3] Equivalent to the previous line

.. [4] For per-module configuration, the equal sign (``=``) needs to be used.

.. [5] **Increasing** the per-module log level above the general ``--file-log-level`` is not yet supported
       (See `issue 689 <https://github.com/ethereum/trinity/issues/689>`_ )


Enabling tab completion
~~~~~~~~~~~~~~~~~~~~~~~

Trinity can be configured to auto complete commands when the <tab> key is pressed.

After installing trinity, to activate tab-completion in future bash prompts, use:

.. code:: sh

    register-python-argcomplete trinity >> ~/.bashrc


For one-time activation of argcomplete for trinity, use:

.. code:: sh

    eval "$(register-python-argcomplete trinity)"
