import rlp

from evm.vm.forks.homestead.transactions import (
    HomesteadTransaction,
    HomesteadUnsignedTransaction,
)

from evm.utils.numeric import (
    int_to_big_endian,
)
from evm.utils.transactions import (
    create_transaction_signature,
    extract_chain_id,
    is_eip_155_signed_transaction,
)


class SpuriousDragonTransaction(HomesteadTransaction):
    def get_message_for_signing(self):
        if is_eip_155_signed_transaction(self):
            txn_parts = rlp.decode(rlp.encode(self))
            txn_parts_for_signing = txn_parts[:-3] + [int_to_big_endian(self.chain_id), b'', b'']
            return rlp.encode(txn_parts_for_signing)
        else:
            return rlp.encode(SpuriousDragonUnsignedTransaction(
                nonce=self.nonce,
                gas_price=self.gas_price,
                gas=self.gas,
                to=self.to,
                value=self.value,
                data=self.data,
            ))

    @classmethod
    def create_unsigned_transaction(cls, nonce, gas_price, gas, to, value, data):
        return SpuriousDragonUnsignedTransaction(nonce, gas_price, gas, to, value, data)

    @property
    def chain_id(self):
        if is_eip_155_signed_transaction(self):
            return extract_chain_id(self.v)
        else:
            return None

    @property
    def v_min(self):
        if is_eip_155_signed_transaction(self):
            return 35 + (2 * self.chain_id)
        else:
            return 27

    @property
    def v_max(self):
        if is_eip_155_signed_transaction(self):
            return 36 + (2 * self.chain_id)
        else:
            return 28


class SpuriousDragonUnsignedTransaction(HomesteadUnsignedTransaction):
    def as_signed_transaction(self, private_key, chain_id=None):
        v, r, s = create_transaction_signature(self, private_key, chain_id=chain_id)
        return SpuriousDragonTransaction(
            nonce=self.nonce,
            gas_price=self.gas_price,
            gas=self.gas,
            to=self.to,
            value=self.value,
            data=self.data,
            v=v,
            r=r,
            s=s,
        )
