from hypothesis import (
    strategies as st,
)

from p2p.discv5.constants import (
    AES128_KEY_SIZE,
    NONCE_SIZE,
    ID_NONCE_SIZE,
    MAGIC_SIZE,
    TAG_SIZE,
)


tag_st = st.binary(min_size=TAG_SIZE, max_size=TAG_SIZE)
nonce_st = st.binary(min_size=NONCE_SIZE, max_size=NONCE_SIZE)
key_st = st.binary(min_size=AES128_KEY_SIZE, max_size=AES128_KEY_SIZE)
random_data_st = st.binary(min_size=3, max_size=8)
# arbitrary size as we're not specifying an identity scheme
pubkey_st = st.binary(min_size=32, max_size=32)
node_id_st = st.binary(min_size=32, max_size=32)
magic_st = st.binary(min_size=MAGIC_SIZE, max_size=MAGIC_SIZE)
id_nonce_st = st.binary(min_size=ID_NONCE_SIZE, max_size=ID_NONCE_SIZE)
enr_seq_st = st.integers(min_value=0)
