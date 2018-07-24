# Release Process

1. Populate CHANGELOG
2. Release `py-evm`
3. Bump py-evm dependency version in `setup_trinity.py`
3. Manual bump of trinity version in `setup_trinity.py`
4. Release `trinity`


## Environment Configuration

- `TRINITY_MP_CONTEXT` - The context that new processes will be spawned from the python `multiprocessing` library.
- `XDG_TRINITY_ROOT` - Base directory where trinity stores data
- `TRINITY_DATA_DIR` - The root directory where the chain data will be stored for the currently running chain.
- `TRINITY_NODEKEY` - The path to a file where the devp2p private key is stored.
- `TRINITY_DATABASE_IPC` - The path to the socket which connects to the database manager.
