Command Line Interface (CLI)
============================

.. code-block:: shell

    usage: trinity [-h] [--version] [--trinity-root-dir TRINITY_ROOT_DIR]
                [-l {debug,info}] [--network-id NETWORK_ID | --ropsten]
                [--sync-mode {full,light} | --light] [--data-dir DATA_DIR]
                [--nodekey NODEKEY] [--nodekey-path NODEKEY_PATH]
                {console,attach} ...

    positional arguments:
    {console,attach}
        console             run the chain and start the trinity REPL
        attach              open an REPL attached to a currently running chain

    optional arguments:
    -h, --help            show this help message and exit

    sync mode:
    --version             show program's version number and exit
    --trinity-root-dir TRINITY_ROOT_DIR
                            The filesystem path to the base directory that trinity
                            will store it's information. Default:
                            $XDG_DATA_HOME/.local/share/trinity

    logging:
    -l {debug,info}, --log-level {debug,info}
                            Sets the logging level

    network:
    --network-id NETWORK_ID
                            Network identifier (1=Mainnet, 3=Ropsten)
    --ropsten             Ropsten network: pre configured proof-of-work test
                            network. Shortcut for `--networkid=3`

    sync mode:
    --sync-mode {full,light}

    chain:
    --data-dir DATA_DIR   The directory where chain data is stored
    --nodekey NODEKEY     Hexadecimal encoded private key to use for the nodekey
    --nodekey-path NODEKEY_PATH
                            The filesystem path to the file which contains the
                            nodekey



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