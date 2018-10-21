Command Line Interface (CLI)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
    --light               Shortcut for `--sync-mode=light`

    chain:
    --data-dir DATA_DIR   The directory where chain data is stored
    --nodekey NODEKEY     Hexadecimal encoded private key to use for the nodekey
    --nodekey-path NODEKEY_PATH
                            The filesystem path to the file which contains the
                            nodekey
