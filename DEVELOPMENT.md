# Block Workflow

The following workflows are supported for blocks.

## 1. Block Building

Incremental creation

1. Initialize Block - `Header.from_parent(...)`:
    - `coinbase`
    - `parent_hash`
    - `difficulty`
    - `block_number`
    - `gas_limit`
    - `timestamp`
2. Apply Transaction(s) - `Block.apply_transaction(...)`:
3. Mine Block - `Block.mine(...)`:
    - `uncles_hash`
    - `state_root`
    - `transaction_root`
    - `receipts_root`
    - `bloom`
    - `gas_used`
    - `extra_data`
    - `mix_hash`
    - `nonce`


## 2. Block Ingestion

> (This is actually just a special case of use case #1.)

Full ingestion of a complete block.  
