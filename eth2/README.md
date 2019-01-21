# Python beacon chain implementation overview

## tl;dr

The Python Ethereum client [Trinity](https://trinity.ethereum.org) is developed by Ethereum Foundation (EF) Python team. To see all the Python tooling for the Ethereum ecosystem, please visit: http://python.ethereum.org/

Recently, EF Research team is collaborating with Python team to implement [the Ethereum 2.0/Serenity beacon chain](https://github.com/ethereum/eth2.0-specs/blob/master/specs/core/0_beacon-chain.md) testnet on Trinity. This document is a snapshot of the overview and the goals Ethereum 2.0/Serenity Python implementation at the beginning of 2019.

## ToC

<!-- TOC -->

- [Python beacon chain implementation overview](#python-beacon-chain-implementation-overview)
    - [tl;dr](#tldr)
    - [ToC](#toc)
    - [Short-term goals](#short-term-goals)
    - [Mid-term goals](#mid-term-goals)
    - [Long-term goals](#long-term-goals)
    - [Components overview](#components-overview)
        - [Networking](#networking)
        - [State Execution: Beacon State Machine v.s. Sharded State Engine v.s. EVM](#state-execution-beacon-state-machine-vs-sharded-state-engine-vs-evm)
        - [Chain: Beacon Chain v.s. Shard Chain v.s. Proof-of-Work (PoW) Chain](#chain-beacon-chain-vs-shard-chain-vs-proof-of-work-pow-chain)
    - [Python modules for Serenity developement](#python-modules-for-serenity-developement)
    - [`eth2` module introduction](#eth2-module-introduction)
        - [`BeaconChainDB`](#beaconchaindb)
        - [`BeaconStateMachine`](#beaconstatemachine)
        - [`BeaconChain`](#beaconchain)
    - [Contribution guideline](#contribution-guideline)

<!-- /TOC -->

## Short-term goals

1. **Phase 0 Milestone 1, [M1]: MVP testnet**
	* see: https://github.com/ethereum/trinity/issues/136
2. Supporting cross-client common tests: [eth2.0-tests](https://github.com/ethereum/eth2.0-tests)
3. Verifying [the spec](https://github.com/ethereum/eth2.0-specs) logic (Research team, WIP [Spec January Release Milestone](https://github.com/ethereum/eth2.0-specs/milestone/1))

## Mid-term goals

1. **Phase 0 Milestone 2, [M2]: March release - the "fully-reflecting-phase-0-spec" testnet**
2. Maintaining [eth2.0-tests](https://github.com/ethereum/eth2.0-tests)

## Long-term goals

1. Providing a reference implementation of an Ethereum 2.0 / Serenity beacon node.
2. Moving on shard node implementation (Phase 1).

## Components overview

Unlike other brand new beacon chain clients, Trinity is also an Ethereum 1.0 Proof-of-Work chain client. The beacon chain design adopts the similar abstract architecture, and leave some placeholders for the shard chain design:

![](https://storage.googleapis.com/ethereum-hackmd/upload_99545a6bd6a23f7d3fbb34e7c74d248a.png)

From bottom to top:

### Networking

- libp2p v.s. RLPx
    - We're planning to use libp2p library to support the transport layer.
- Sharded Networks Peer management v.s. current Peer Management
    - **(Phase 1)** The shard block validators have to be shuffled and to be assigned to validate a specific shard of a specific slot. It requires different peer management design for the shard networks.

### State Execution: Beacon State Machine v.s. Sharded State Engine v.s. EVM

- **(Phase 0)** The beacon chain state represents the consensus of the Ethereum 2.0 validators.
- **(Phase 1)** The shard state execution engine will be the new VM that replace EVM to support smart contract execution. Our current most promising candidate is eWASM.

### Chain: Beacon Chain v.s. Shard Chain v.s. Proof-of-Work (PoW) Chain

`Chain` object is the component that represents a blockchain in Py-EVM. Currently, Trinity provides different PoW chains like `Mainnet` and `Ropsten`; for beacon chain, we're developing a different class with beacon-chain-specific features; likewise for the shard chain.

## Python modules for Serenity developement

- **`eth2`**: Ethereum 2.0/Serenity, beacon chain protocol codebase
    - Located in [`ethereum/trinity`](https://github.com/ethereum/trinity/) temporarily for accelerating development.
- **`trinity`**: Python Ethereum client implementation
    - [`ethereum/trinity`](https://github.com/ethereum/trinity/)
- **`ssz`**: SimpleSerialize implementation
    - [`ethereum/py-ssz`](https://github.com/ethereum/py-ssz)
- **`py_ecc`**: BLS12-381 curve implementation
    - [`ethereum/py_ecc`](https://github.com/ethereum/py_ecc)

## `eth2` module introduction

The beacon chain implementation is based on the similar architecture of PoW chain module ([`eth` module in Py-EVM repository](https://github.com/ethereum/py-evm/tree/master/eth)). The main components includes:

### `BeaconChainDB`

The database interface for storing block data in local storage.

![](https://storage.googleapis.com/ethereum-hackmd/upload_c5be9ed3eab4f9a071b3bb655e7c13cd.png)

### `BeaconStateMachine`

The state machine interface for applying a new block. The principle is that the `BeaconState` object would have enough context to perform:

```python
state_1 = state_transition_function(state_0, block_1)
```

Py-EVM abstracts EVM with `BaseVM` that defines the interfaces, and implements subclasses for the different mainnet forks. For example, `FrontierVM` inherits `VM` and represents the VM for Frontier fork; beacon chain has the similar architecture as we implemented `SerenityStateMachine` as the first fork of beacon chain.

![](https://storage.googleapis.com/ethereum-hackmd/upload_14a701ef308508cd7f837eeca56ed251.png)


The in-protocol data structures are defined in `eth2.beacon.types`. If the data fields might be different from the future forks, we can implement a new subclass in the future.

![](https://storage.googleapis.com/ethereum-hackmd/upload_be262ea6aac671174463882ed3f11420.png)

### `BeaconChain`

The `Chain` represents a single blockchain. One chain might fork by the block number setting, or slot number in beacon chain, we call it *versioning*.

![](https://storage.googleapis.com/ethereum-hackmd/upload_46c3b4a92edeaa18d66f5e2e367f1276.png)

In `BeaconChain` initialization, a `BeaconChainDB` will be set in `BeaconChain`. While processing each block, it will initialize a `BeaconStateMachine` object via `get_sm()` function, and use this particular `BeaconStateMachine` to apply state transition of the given block.

## Contribution guideline

* [Trinity](https://trinity-client.readthedocs.io/en/latest/contributing.html)
