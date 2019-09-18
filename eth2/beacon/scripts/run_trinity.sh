#!/bin/bash

# Helper script for running a lighthouse node and connecting to the beacon node
# that's set up by start.sh

# https://github.com/sigp/lighthouse/blob/master/docs/interop.md

set -eu

# Fetch genesis time, as set up by start.sh
if command -v jq; then
  genesis_time=$(jq '.genesis_time' data/state_snapshot.json)
  peer=$(jq -r '.addresses[0] + "/p2p/" + .peer' data/node-0/beacon_node.address)
else
  genesis_time=$(grep -oP '(?<=genesis_time": )\w+(?=,)' data/state_snapshot.json)
fi

echo Genesis time was $genesis_time

PYTHONWARNINGS=ignore::DeprecationWarning trinity-beacon -l DEBUG --trinity-root-dir /tmp/bb --preferred_nodes=$peer interop --validators 0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 --start-time $genesis_time --wipedb --keys keys.yaml
