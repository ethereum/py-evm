from eth_utils import (
    ValidationError,
    to_tuple,
)
from eth_utils.toolz import (
    sliding_window,
)
import pytest

from eth.chains.mainnet import (
    MainnetHomesteadVM,
)
from eth.rlp.headers import (
    BlockHeader,
)


class ETC_VM(MainnetHomesteadVM):
    support_dao_fork = False


# Ethereum mainnet headers, from two headers before to ten headers after the fork:
ETH_HEADERS_NEAR_FORK = [
    BlockHeader(
        difficulty=62352470509925,
        block_number=1919998,
        gas_limit=4712388,
        timestamp=1469020835,
        coinbase=b"\xbc\xdf\xc3[\x86\xbe\xdfr\xf0\xcd\xa0F\xa3\xc1h)\xa2\xefA\xd1",
        parent_hash=b"\xe7\xe3\xe8+\xf3C\xbe\xf9\xa2R\xb8\x7f\x06r\x9adZop\x9b.RK\x9e\xf4\xf9;\xb9\xf2]S\x8d",  # noqa: E501
        uncles_hash=b"\x1d\xccM\xe8\xde\xc7]z\xab\x85\xb5g\xb6\xcc\xd4\x1a\xd3\x12E\x1b\x94\x8at\x13\xf0\xa1B\xfd@\xd4\x93G",  # noqa: E501
        state_root=b"\x1f!\x88?4\xde&\x93\xb4\xadGD\xc26a\xdbd\xca\xcb=\xa2\x1dr \xceW\xb97d\xb3\xbb\xfe",  # noqa: E501
        transaction_root=b"\xf2n\xb9\x94\x0e\xbb\xe8\x0c\xc3\xab\xbc\x9ev\xe9\xb7\xb1\x0f\xbcG\xc0\xd2\x12\xf9\x81\xa6q/\xf7\xf4\x97\xd3\xb4",  # noqa: E501
        receipt_root=b"D\xda\xa2\x9c4?\xa0/\xe8\x8fH\xf8?z\xc2\x1e\xfa\xc8j\xb0w8\r\xed\x81[(n\xd2jx\x1f",  # noqa: E501
        bloom=0,
        gas_used=420000,
        extra_data=b"\xd7\x83\x01\x04\n\x84Geth\x87go1.6.2\x85linux",
        mix_hash=b"\x8d\x03\xe0$?1\xa6\xcd\x11\x04E\x1f\xfc\x10#[\x04\x16N\xbe[\xd4u-\xa6\xb54t\x8d\x87}\x9f",  # noqa: E501
        nonce=b"a\xd8\xc5\xdf\xfd\x0e\xb2v",
    ),
    BlockHeader(
        difficulty=62382916183238,
        block_number=1919999,
        gas_limit=4707788,
        timestamp=1469020838,
        coinbase=b"*e\xac\xa4\xd5\xfc[\\\x85\x90\x90\xa6\xc3M\x16A59\x82&",
        parent_hash=b"P_\xfd!\xf4\xcb\xf2\xc5\xc3O\xa8L\xd8\xc9%%\xf3\xa7\x19\xb7\xad\x18\x85+\xff\xdd\xad`\x105\xf5\xf4",  # noqa: E501
        uncles_hash=b"\x1d\xccM\xe8\xde\xc7]z\xab\x85\xb5g\xb6\xcc\xd4\x1a\xd3\x12E\x1b\x94\x8at\x13\xf0\xa1B\xfd@\xd4\x93G",  # noqa: E501
        state_root=b"\xfd\xf2\xfc\x04X\x0b\x95\xca\x15\xde\xfcc\x90\x80\xb9\x02\xe98\x92\xdc\xce(\x8b\xe0\xc1\xf7\xa7\xbb\xc7x$\x8b",  # noqa: E501
        transaction_root=b"V\xe8\x1f\x17\x1b\xccU\xa6\xff\x83E\xe6\x92\xc0\xf8n[H\xe0\x1b\x99l\xad\xc0\x01b/\xb5\xe3c\xb4!",  # noqa: E501
        receipt_root=b"V\xe8\x1f\x17\x1b\xccU\xa6\xff\x83E\xe6\x92\xc0\xf8n[H\xe0\x1b\x99l\xad\xc0\x01b/\xb5\xe3c\xb4!",  # noqa: E501
        bloom=0,
        gas_used=0,
        extra_data=b"DwarfPool",
        mix_hash=b"\xa0#\n\xf0\xa0\xd3\xd2\x97\xb7\xe8\xc2G=\x16;\x1e\xb0\xb1\xbb\xbbN\x9d\x93>_\xde\xa0\x85F\xb5nY",  # noqa: E501
        nonce=b"`\x83'\t\xc8\x97\x9d\xaa",
    ),
    BlockHeader(
        difficulty=62413376722602,
        block_number=1920000,
        gas_limit=4712384,
        timestamp=1469020840,
        coinbase=b"\xbc\xdf\xc3[\x86\xbe\xdfr\xf0\xcd\xa0F\xa3\xc1h)\xa2\xefA\xd1",
        parent_hash=b"\xa2\x18\xe2\xc6\x11\xf2\x122\xd8W\xe3\xc8\xce\xcd\xcd\xf1\xf6_%\xa4G\x7f\x98\xf6\xf4~@c\x80\x7f#\x08",  # noqa: E501
        uncles_hash=b"\x1d\xccM\xe8\xde\xc7]z\xab\x85\xb5g\xb6\xcc\xd4\x1a\xd3\x12E\x1b\x94\x8at\x13\xf0\xa1B\xfd@\xd4\x93G",  # noqa: E501
        state_root=b"\xc5\xe3\x89Aa\x16\xe3il\xce\x82\xecE3\xcc\xe3>\xfc\xcb$\xce$Z\xe9TjK\x8f\r^\x9au",  # noqa: E501
        transaction_root=b"w\x01\xdf\x8e\x07\x16\x94RUM\x14\xaa\xdd{\xfa%mJ\x1d\x03U\xc1\xd1t\xab7>>-\n7C",  # noqa: E501
        receipt_root=b'&\xcf\x9d\x94"\xe9\xdd\x95\xae\xdcy\x14\xdbi\x0b\x92\xba\xb6\x90/R!\xd6&\x94\xa2\xfa]\x06_SK',  # noqa: E501
        bloom=0,
        gas_used=84000,
        extra_data=b"dao-hard-fork",
        mix_hash=b"[Z\xcb\xf4\xbf0_\x94\x8b\xd7\xbe\x17`G\xb2\x06#\xe1A\x7fuYsA\xa0Yr\x91e\xb9#\x97",  # noqa: E501
        nonce=b"\xbe\xde\x87 \x1d\xe4$&",
    ),
    BlockHeader(
        difficulty=62321951008868,
        block_number=1920001,
        gas_limit=4712388,
        timestamp=1469020887,
        coinbase=b"\xbc\xdf\xc3[\x86\xbe\xdfr\xf0\xcd\xa0F\xa3\xc1h)\xa2\xefA\xd1",
        parent_hash=b"I\x85\xf5\xca=*\xfb\xec6R\x9a\xa9ot\xde<\xc1\n*JlD\xf2\x15zW\xd2\xc6\x05\x9a\x11\xbb",  # noqa: E501
        uncles_hash=b"\x1d\xccM\xe8\xde\xc7]z\xab\x85\xb5g\xb6\xcc\xd4\x1a\xd3\x12E\x1b\x94\x8at\x13\xf0\xa1B\xfd@\xd4\x93G",  # noqa: E501
        state_root=b"\x16N\x1e\x81\x9a\x06\xa5\xc4\xa1\xf3\x9ew\xa5\xe4\x03cR\xe1\xab\r\xe7t\x1f\x8b\xb9\x06z\x8d\xae\xe1%a",  # noqa: E501
        transaction_root=b"\x01\xdd\xd2\xd5%r\x0f\xb2&\x0b\x979\xc6\xa8\xb7\xd5EZ\xbe\xec5\x88R\x8aVZn\xc6\x1c\xe8}N",  # noqa: E501
        receipt_root=b"/\xdc|\n\xc9\xcfw\xd7\xa5\xd5\xb0\x15f\x1a\x96\xd2c%\x9f!\x00hV>\xf9}\xf7QR\xd8\x01\xb6",  # noqa: E501
        bloom=0,
        gas_used=1235000,
        extra_data=b"dao-hard-fork",
        mix_hash=b"t\xb4)\xd1\xbef\xfa]F*R\x03\xf4L*&yh\xcf/\xd6w/bxn\x0fC\xb9Gl\xb8",
        nonce=b")\xc7\xf1\xe0%\xean\x01",
    ),
    BlockHeader(
        difficulty=62230659219517,
        block_number=1920002,
        gas_limit=4712388,
        timestamp=1469020934,
        coinbase=b"K\xb9`\x91\xee\x9d\x80.\xd09\xc4\xd1\xa5\xf6!o\x90\xf8\x1b\x01",
        parent_hash=b"\x87\xb2\xbc?\x12\xe3\xde\xd8\x08\xc6\xd4\xb9\xb5(8\x1f\xa2\xa7\xe9_\xf26\x8b\xa91\x91\xa9I]\xaa\x7fP",  # noqa: E501
        uncles_hash=b"\x1d\xccM\xe8\xde\xc7]z\xab\x85\xb5g\xb6\xcc\xd4\x1a\xd3\x12E\x1b\x94\x8at\x13\xf0\xa1B\xfd@\xd4\x93G",  # noqa: E501
        state_root=b"S\x80.\x83\xb4\xe3\x93\xf0\xab\xb4\xfd+\xe5l\x88}\xc4\xcb\xbc\xcd\x13\xe7|r8\xb7\xfe\xd54\xac\xfd\xc4",  # noqa: E501
        transaction_root=b"\x0b\x86\xb9\x0c-\xb3\x12\xc6q\x0e\xf7\xeb\x9e\xf5\xde\x99\x91Y\x80}\xd0\n\x8d\xa9(\xd8(\xa84>+8",  # noqa: E501
        receipt_root=b"\xc9\xa2Z\xa1\xd1.\x9fXI\x87\xc5\x08k\xfe\x90\xe3-\x93\xef\xb3\xe3\xe3\xaf[\xe2\xfbM\x04zfaM",  # noqa: E501
        bloom=3503816819074275522498983613412458896725558513531951144198912651112726391715434473024323518887540683470941518777685692917027783902019483338356101340370684135250547410323500275574052226757638964811580778892900093856919093643792002902267556228080698834041887158756496963934643887614742092547614979826888138922300667242594899411608406519454743353970681153031134657480524727368449008182798323268209920507340887449029987958994336950110988308468738014311555748072974626364212283567279699186212273917530435799651853887594592689819317881446004999842501274571244063011292512938351776866758052806050141175808,  # noqa: E501
        gas_used=1043630,
        extra_data=b"dao-hard-fork",
        mix_hash=b"Hz\xfc\x7f\xe0\xf9\xdfT\xda@,:\xcc\xbcX\xa8\xc1D\xaa\xfb5\xf9\x04\xd1T\x19\xe3q\xf3\x89&\xaa",  # noqa: E501
        nonce=b"\xa0Q\xf7L\x12J\x8f]",
    ),
    BlockHeader(
        difficulty=62139501158373,
        block_number=1920003,
        gas_limit=4707788,
        timestamp=1469020981,
        coinbase=b"*e\xac\xa4\xd5\xfc[\\\x85\x90\x90\xa6\xc3M\x16A59\x82&",
        parent_hash=b"\xf1\x92;\xd6\x81'vQ#\x87;\xf4v\xd3\x97\x19\x85\x081\xe5\x80\x96=\x8f\xb7\xac\xfc\xc6\xa1\xc5c\x0e",  # noqa: E501
        uncles_hash=b"\x1d\xccM\xe8\xde\xc7]z\xab\x85\xb5g\xb6\xcc\xd4\x1a\xd3\x12E\x1b\x94\x8at\x13\xf0\xa1B\xfd@\xd4\x93G",  # noqa: E501
        state_root=b"\x96\x06\xb3\xc4\xf0\xebq\\](\xf0\xac\x10\xc7\x8c\x10\xc9\xa3\x9d\xablz.\x92\xe5\x15:XI-\xa8k",  # noqa: E501
        transaction_root=b"\xe3\xc7\xcb*b\x1f\xb0\x80E\x10\xb1!\xe0:\xbcK\x89\x9f\x90\xbf\xc3\xeb\xabC\xc1Z\xb9\xe8\xb6p\xbe2",  # noqa: E501
        receipt_root=b"\xd0M3=\xe9\xd5\x9c\xfeF\xfe\x9f\xea\xf0\x10\xbc3'\x8c\x90\xd9\x12\x16[\xe3\x022\xb6v9\xb0\xd5\xa1",  # noqa: E501
        bloom=3503816819074275522498960427097717493126582568741009766032410983139535351910031395664053122354624875615022871654264152609465304174558821883238513745294194625706511748483041075722267280897622726803426914919583747696269528655018673450980542770247998502170164498691657326098343128584421550000014465360765929276706740111998829706528527883195968951541817626946595474619814856141390717852666132865336230563278933901318619362757144590028657919138181194906405052784502275378019280751501518559445972969458028423906108641586199053579802745691039312723628214134292229941367409906398555500673781588875265703936,  # noqa: E501
        gas_used=45672,
        extra_data=b"dao-hard-fork",
        mix_hash=b'\x18\xfa"~?\xad_\xec\xa5\xa4\xb1\x13uD#\x8e\x94L?\xe4\t\x83\x16\xaa\xc7\xb7)]\xac\xa9b0',  # noqa: E501
        nonce=b"z\x86aL\x0b\xaap\xb4",
    ),
    BlockHeader(
        difficulty=62139501289445,
        block_number=1920004,
        gas_limit=4712384,
        timestamp=1469021000,
        coinbase=b"R\xbcD\xd57\x83\t\xee*\xbf\x159\xbfq\xde\x1b}{\xe3\xb5",
        parent_hash=b"\x93\xe4\xcb\xf8\x1c:a\xe1\xcan\xfd\xc8\x1b\x03\x9b\xb2\xeb\xac\xcafT\xa8\xa8@\x01z^9\xf5@\xc1\x8d",  # noqa: E501
        uncles_hash=b"\x1d\xccM\xe8\xde\xc7]z\xab\x85\xb5g\xb6\xcc\xd4\x1a\xd3\x12E\x1b\x94\x8at\x13\xf0\xa1B\xfd@\xd4\x93G",  # noqa: E501
        state_root=b"\xb4]\x0c/\xffS{\xc1}`T=\x17!1^0\xef)\xaf$[\x0e\x99\xf3\xa8}[\xc7\x18\xeb\xe2",  # noqa: E501
        transaction_root=b'\xd4Ven\xc3qKq\xd6vM\xda\x9a}z\xcf\xc5\x17\xbd\x15\x15M1}"\xe2\xc6\xff<$\x93I',  # noqa: E501
        receipt_root=b"\xec\xc8`\xb3\xaeI\x7f\xb5\x1e\xd4y'\x80\x99\xa6$z\xac\"\xd5\xa8W\xf5\x81>Y\xd32\xbep:g",  # noqa: E501
        bloom=3503816819074275522522726399707656182076925979455922386696585768771397670901134712106969810459214691939717965629765969171071021109061686786459055758612060627492775503290275345015230881717959096523025020059003914097519539329373743120219681507190107459889674131663814249507313285530547168301246084033275461581105232382055750746451810516868095715055946268545015943608699821675416462213277467320639816295110024634329298639928569397813657987160203214882014774015478928134939456373922168196173315103896320739696945130969784916675797706508072919145837322632719338531657089495324884345247169409861713657856,  # noqa: E501
        gas_used=289003,
        extra_data=b"dao-hard-fork",
        mix_hash=b"\xa9\x9c\x0e&\xf7m6S/.O\x15\xc2s'\xc7m\x99v\xa6_\xcby\x9d\xe5\xeb\x00\xcf\x96\x10E@",  # noqa: E501
        nonce=b"<\xc0\xf5\xb8:A\xfd}",
    ),
    BlockHeader(
        difficulty=62169842973880,
        block_number=1920005,
        gas_limit=4707784,
        timestamp=1469021004,
        coinbase=b"*e\xac\xa4\xd5\xfc[\\\x85\x90\x90\xa6\xc3M\x16A59\x82&",
        parent_hash=b"\x83\x96Gy\x87\xe3\x1a\x9fD\x04Fo\x90\xde\xd4 \x7f2\xb5;7\x1e\xdb\x8d[+\xdf\xe3=\x16\x08\x8c",  # noqa: E501
        uncles_hash=b"\x1d\xccM\xe8\xde\xc7]z\xab\x85\xb5g\xb6\xcc\xd4\x1a\xd3\x12E\x1b\x94\x8at\x13\xf0\xa1B\xfd@\xd4\x93G",  # noqa: E501
        state_root=b"\xf1-\xe0\xc9\xbaA\x94\x96k\x82\xf5s\xbdfw\\=\xa0\x0e,\x95\xc0\x18QG\xcf\x88M[>\x0e\xfc",  # noqa: E501
        transaction_root=b"V\xe8\x1f\x17\x1b\xccU\xa6\xff\x83E\xe6\x92\xc0\xf8n[H\xe0\x1b\x99l\xad\xc0\x01b/\xb5\xe3c\xb4!",  # noqa: E501
        receipt_root=b"V\xe8\x1f\x17\x1b\xccU\xa6\xff\x83E\xe6\x92\xc0\xf8n[H\xe0\x1b\x99l\xad\xc0\x01b/\xb5\xe3c\xb4!",  # noqa: E501
        bloom=0,
        gas_used=0,
        extra_data=b"dao-hard-fork",
        mix_hash=b"oj\xefC\xe4\xe9\xc3\xbai\x91@q\x8dW\xc5\xe7\x1bUW\xe2PY\xeaRDx\x19\x92\xb5\xd3a\xa7",  # noqa: E501
        nonce=b"\x00o\x83 \x05?\xb6\xc9",
    ),
    BlockHeader(
        difficulty=62200199473591,
        block_number=1920006,
        gas_limit=4712380,
        timestamp=1469021008,
        coinbase=b"\xeagO\xdd\xe7\x14\xfd\x97\x9d\xe3\xed\xf0\xf5j\xa9qk\x89\x8e\xc8",
        parent_hash=b"\xf9\x04\x0bM\x1a4v\xda\x17\xe8S\xb8\xc05e\\0\x89\xc8\x1c\x85\x9b\xf0@\r\xed\x98\xf0+\t\x04\xab",  # noqa: E501
        uncles_hash=b"\x1d\xccM\xe8\xde\xc7]z\xab\x85\xb5g\xb6\xcc\xd4\x1a\xd3\x12E\x1b\x94\x8at\x13\xf0\xa1B\xfd@\xd4\x93G",  # noqa: E501
        state_root=b"\x1e.\r\xc8\xb9\xf9\xea4\x17\x8fk#\xfc\xc0XF\x07KI[\xe5M\x059\xab\xba\x9aeT=\xa5\xb8",  # noqa: E501
        transaction_root=b"V\xe8\x1f\x17\x1b\xccU\xa6\xff\x83E\xe6\x92\xc0\xf8n[H\xe0\x1b\x99l\xad\xc0\x01b/\xb5\xe3c\xb4!",  # noqa: E501
        receipt_root=b"V\xe8\x1f\x17\x1b\xccU\xa6\xff\x83E\xe6\x92\xc0\xf8n[H\xe0\x1b\x99l\xad\xc0\x01b/\xb5\xe3c\xb4!",  # noqa: E501
        bloom=0,
        gas_used=0,
        extra_data=b"dao-hard-fork",
        mix_hash=b"9:\x1cw`v\xc4\xab5J\x8f\x85\x1c\x1a\xf5\x8c\xffp?\xec`?\x00\xda\x94\xb7\xfd\x89sz\xc5p",  # noqa: E501
        nonce=b"\x80\x00\xb2\xe0\x04\x1b\xec\x8c",
    ),
    BlockHeader(
        difficulty=62200199604663,
        block_number=1920007,
        gas_limit=4712388,
        timestamp=1469021022,
        coinbase=b"\xa0'#\x1fB\xc8\x0c\xa4\x12[\\\xb9b\xa2\x1c\xd4\xf8\x12\xe8\x8f",
        parent_hash=b"pm\xccC<+\xe2\xf71\xac|\xed(\xb3p\xad\x9a\x14\x06L3\xa1\xb4\xe1.\xfd\xd4\xd0'L\xfb+",  # noqa: E501
        uncles_hash=b"\x1d\xccM\xe8\xde\xc7]z\xab\x85\xb5g\xb6\xcc\xd4\x1a\xd3\x12E\x1b\x94\x8at\x13\xf0\xa1B\xfd@\xd4\x93G",  # noqa: E501
        state_root=b"zX\x10Z\x96B\x1eNr\xc6jT\xa8\x15\x87\x83.(\xcf\xf6\x1c?\n\x8d\xdb\xd2l\x03\x7f%\xb7\xe0",  # noqa: E501
        transaction_root=b"V\xe8\x1f\x17\x1b\xccU\xa6\xff\x83E\xe6\x92\xc0\xf8n[H\xe0\x1b\x99l\xad\xc0\x01b/\xb5\xe3c\xb4!",  # noqa: E501
        receipt_root=b"V\xe8\x1f\x17\x1b\xccU\xa6\xff\x83E\xe6\x92\xc0\xf8n[H\xe0\x1b\x99l\xad\xc0\x01b/\xb5\xe3c\xb4!",  # noqa: E501
        bloom=0,
        gas_used=0,
        extra_data=b"dao-hard-fork",
        mix_hash=b"N\x88\xda\x1d}V|\x9d\x9e\xd24D\x0b\xe4'vlz\xfbe\xf7\x18\xe2\"\xef=*\xff\x15XDM",  # noqa: E501
        nonce=b"\xc6\xafn\x0e\xb1[\xf5D",
    ),
    BlockHeader(
        difficulty=62230570926948,
        block_number=1920008,
        gas_limit=4707788,
        timestamp=1469021025,
        coinbase=b"*e\xac\xa4\xd5\xfc[\\\x85\x90\x90\xa6\xc3M\x16A59\x82&",
        parent_hash=b"\x05\xc4\\\x96q\xee1sk\x9f7\xee\x98\xfa\xa7,\x89\xe3\x14\x05\x9e\xcf\xf3%r\x06\xe6\xabI\x8e\xb9\xd1",  # noqa: E501
        uncles_hash=b"\x1d\xccM\xe8\xde\xc7]z\xab\x85\xb5g\xb6\xcc\xd4\x1a\xd3\x12E\x1b\x94\x8at\x13\xf0\xa1B\xfd@\xd4\x93G",  # noqa: E501
        state_root=b"\xfa\x8d;<\xbd7\xca\xba/\xaf\t\xd5\xe4r\xaelG\xa5\x8d\x84gQ\xbcr0af\xa7\x1d\x0f\xa4\xfa",  # noqa: E501
        transaction_root=b"V\xe8\x1f\x17\x1b\xccU\xa6\xff\x83E\xe6\x92\xc0\xf8n[H\xe0\x1b\x99l\xad\xc0\x01b/\xb5\xe3c\xb4!",  # noqa: E501
        receipt_root=b"V\xe8\x1f\x17\x1b\xccU\xa6\xff\x83E\xe6\x92\xc0\xf8n[H\xe0\x1b\x99l\xad\xc0\x01b/\xb5\xe3c\xb4!",  # noqa: E501
        bloom=0,
        gas_used=0,
        extra_data=b"dao-hard-fork",
        mix_hash=b"\xe74!9\x0c\x1b\x08J\x98\x06uK#\x87\x15\xec3<\xdc\xcc\x8d\t\xb9\x0c\xb6\xe3\x8a\x9d\x1e$}o",  # noqa: E501
        nonce=b"\xc2\x07\xc88\x13\x05\xbe\xf2",
    ),
    BlockHeader(
        difficulty=62230571058020,
        block_number=1920009,
        gas_limit=4712384,
        timestamp=1469021040,
        coinbase=b"\xeagO\xdd\xe7\x14\xfd\x97\x9d\xe3\xed\xf0\xf5j\xa9qk\x89\x8e\xc8",
        parent_hash=b"A%G#\xe1.\xb76\xdd\xef\x15\x13q\xe4\xc3\xd6\x14#>l\xad\x95\xf2\xd9\x01}\xe2\xab\x8bF\x9a\x18",  # noqa: E501
        uncles_hash=b'\x80\x8d\x06\x17`I\xae\xcf\xd5\x04\x19}\xdeI\xf4l=\xd7_\x1a\xf0U\xe4\x17\xd1\x00"\x81b\xee\xfd\xd8',  # noqa: E501
        state_root=b"I\xeb31Rq;x\xd9 D\x0e\xf0e\xed\x7fh\x16\x11\xe0\xc2\xe6\x93=e}oJ\x7f\x196\xee",  # noqa: E501
        transaction_root=b"\xa8\x06\x0f\x13\x91\xfdL\xbd\xe4\xb0=\x83\xb3*\x1b\xdaDUx\xcdn\xc6\xb7\x98-\xb2\x0cI\x9e\xd3h+",  # noqa: E501
        receipt_root=b"\xabf\xb1\x98nq>\xafV!\x05\x9ey\xf0K\xa9\xc5(\x18|\x1b\x9d\xa9i\xf4dB\xc3\xf9\x15\xc1 ",  # noqa: E501
        bloom=3503816819074275522498960427097720192368875169843853640258612003572928383490400796708623938265877060708391387364016286831406418652928454048516814675999945258468219600263973006774496314291058294120097117005968023338050598132606027446812661455584028823194473549875877851833320717839457898529435936790381772983783935160942168072313522526284021440214276502305303318071999804685589999214158116275794981463742802217224191210740480296996358038574028963938480933199822424029865854719675112094317415808896505407591701483917211929124606585670771723431764581242555097615034951201515889985218711283146439000064,  # noqa: E501
        gas_used=109952,
        extra_data=b"dao-hard-fork",
        mix_hash=b"[\xdey\xf4\xdc[\xe2\x8a\xf2\xd9V\xe7H\xa0\xd6\xeb\xc1\xf8\xeb\\\x13\x97\xe7g)&\x9es\x06\x11\xcb\x99",  # noqa: E501
        nonce=b"+KFL\nM\xa8*",
    ),
    BlockHeader(
        difficulty=62230571189092,
        block_number=1920010,
        gas_limit=4712388,
        timestamp=1469021050,
        coinbase=b"K\xb9`\x91\xee\x9d\x80.\xd09\xc4\xd1\xa5\xf6!o\x90\xf8\x1b\x01",
        parent_hash=b"i\xd0J\xec\x94\xadi\xd7\xd1\x90\xd3\xb5\x1d$\xcdB\xdd\xed\x0cGgY\x8a\x1d0H\x03cP\x9a\xcb\xef",  # noqa: E501
        uncles_hash=b"\x1d\xccM\xe8\xde\xc7]z\xab\x85\xb5g\xb6\xcc\xd4\x1a\xd3\x12E\x1b\x94\x8at\x13\xf0\xa1B\xfd@\xd4\x93G",  # noqa: E501
        state_root=b"n\xe6:\xbe\xe7Am:g\x1b\xcb\xef\xa0\x1a\xa5\xd4\xeaB~$mT\x8e\x15\xc5\xf3\xd9\xa1\x08\xe78\xfd",  # noqa: E501
        transaction_root=b"\x0cmJd>\xd0\x81\xf9.8JXS\xf1M\x7f_\xf5\xd6\x8be\xd0\xc9\x0bF\x15\x95\x84\xa8\x0e\xff\xe0",  # noqa: E501
        receipt_root=b"\xa7\xd1\xdd\xb8\x00`\xd4\xb7|\x07\x00~\x9a\x9f\x0b\x83A;\xd2\xc5\xdeqP\x16\x83\xbaGd\x98.\xefK",  # noqa: E501
        bloom=3503816819074275522498983613412458896725558513531951144198912651112726391715434473024323518887540683470941518777685692917027783902019483338356083399681014648239728242191617691611781491792595615260549520467704031205245705389131282672424044435385879678301689182416084367551304361209870387287019685673582977657278039952649631967994278397105831292567484946522026316697341380637450599908888465587759093755140827184983414178514788825100006548115492954679773101066280924028086424550153611018470545507595737363558115597332088606631745017984602135428311413275262889840004619047769563842103612040861362159616,  # noqa: E501
        gas_used=114754,
        extra_data=b"ethpool.org (US1)",
        mix_hash=b'\x8f\x86a}d"\xc2j\x89\xb8\xb3I\xb1`\x97<\xa4O\x902nu\x8f\x1e\xf6i\xc4\x04gA\xdd\x06',  # noqa: E501
        nonce=b"\xc7\xde\x19\xe0\n\x8c>2",
    ),
]

ETC_HEADER_AT_FORK = BlockHeader(
    difficulty=62413376722602,
    block_number=1920000,
    gas_limit=4712384,
    timestamp=1469020839,
    coinbase=b"a\xc8\x08\xd8*:\xc521u\r\xad\xc1<w{Y1\x0b\xd9",
    parent_hash=b"\xa2\x18\xe2\xc6\x11\xf2\x122\xd8W\xe3\xc8\xce\xcd\xcd\xf1\xf6_%\xa4G\x7f\x98\xf6\xf4~@c\x80\x7f#\x08",  # noqa: E501
    uncles_hash=b"\x1d\xccM\xe8\xde\xc7]z\xab\x85\xb5g\xb6\xcc\xd4\x1a\xd3\x12E\x1b\x94\x8at\x13\xf0\xa1B\xfd@\xd4\x93G",  # noqa: E501
    state_root=b"aM}5\x8b\x03\xcb\xda\xf045)g;\xe2\n\xd4X\t\xd0$\x87\xf0#\xe0G\xef\xdc\xe9\xda\x8a\xff",  # noqa: E501
    transaction_root=b"\xd30h\xa7\xf2\x1b\xffP\x18\xa0\x0c\xa0\x8a5f\xa0k\xe4\x19m\xfe\x9e9\xf9nC\x15e\xa6\x19\xd4U",  # noqa: E501
    receipt_root=b"{\xda\x9a\xa6Yw\x80\x03v\x12\x91H\xcb\xfe\x89\xd3Z\x01m\xd5\x1c\x95\xd6\xe6\xdc\x1ev0}1Th",  # noqa: E501
    bloom=0,
    gas_used=84000,
    extra_data=b"\xe4\xb8\x83\xe5\xbd\xa9\xe7\xa5\x9e\xe4\xbb\x99\xe9\xb1\xbc",
    mix_hash=b"\xc5-\xaapT\xba\xbeQ[\x17\xee\x98T\x0c\x08\x89\xcf^\x15\x95\xc5\xddwIi\x97\xca\x84\xa6\x8c\x8d\xa1",  # noqa: E501
    nonce=b"\x05'j`\t\x80\x19\x9d",
)


@to_tuple
def header_pairs(VM, headers, valid):
    for pair in sliding_window(2, headers):
        yield VM, pair[1], pair[0], valid


@pytest.mark.parametrize(
    "VM, header, previous_header, valid",
    header_pairs(MainnetHomesteadVM, ETH_HEADERS_NEAR_FORK, valid=True)
    + (
        (MainnetHomesteadVM, ETC_HEADER_AT_FORK, ETH_HEADERS_NEAR_FORK[1], False),
        # ETC VM should accept the header right before the DAO fork
        (ETC_VM, ETH_HEADERS_NEAR_FORK[1], ETH_HEADERS_NEAR_FORK[0], True),
        # ... and accept its own non-fork header at the fork block
        (ETC_VM, ETC_HEADER_AT_FORK, ETH_HEADERS_NEAR_FORK[1], True),
        # ... and reject the DAO-fork header at the fork
        (ETC_VM, ETH_HEADERS_NEAR_FORK[2], ETH_HEADERS_NEAR_FORK[1], False),
    ),
)
def test_mainnet_dao_fork_header_validation(VM, header, previous_header, valid):
    if valid:
        VM.validate_header(header, previous_header)
    else:
        try:
            VM.validate_header(header, previous_header)
        except ValidationError:
            pass
        else:
            raise AssertionError(f"The invalid header {repr(header)} must fail")
