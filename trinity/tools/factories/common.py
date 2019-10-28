
try:
    import factory
except ImportError:
    raise ImportError(
        "The p2p.tools.factories module requires the `factory_boy` and `faker` libraries."
    )


from trinity.protocol.common.payloads import BlockHeadersQuery


class BlockHeadersQueryFactory(factory.Factory):
    class Meta:
        model = BlockHeadersQuery

    block_number_or_hash = 0
    max_headers = 1
    skip = 0
    reverse = False
