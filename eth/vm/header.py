from eth.vm.forks.cancun.blocks import (
    CancunBackwardsHeader,
)

HeaderSedes = CancunBackwardsHeader
"""
An RLP codec that can decode *all* known header types.

Unfortunately, we often cannot look up the VM to determine the valid codec. For
example, when looking up a header by hash, we don't have the block number yet,
and so can't load the VM configuration to find out which VM's rules to use to
decode the header. Also, it's useful to have this universal sedes class when
decoding multiple uncles that span a fork block.
"""
