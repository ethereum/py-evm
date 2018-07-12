from eth.rlp.blocks import BaseBlock
from eth.utils.hexadecimal import (
    encode_hex,
)


def format_block(block: BaseBlock) -> str:
    return (
        "\n\n"
        "------------------------Block------------------------------------\n"
        "Number #{b.number:>12} Hash {hash}\n"
        "-----------------------------------------------------------------\n"
    ).format(b=block, hash=encode_hex(block.hash))
