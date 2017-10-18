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
    create_eip155_transaction_signature,
    extract_chain_id,
    is_eip_155_signed_transaction,
    validate_eip155_transaction_signature,
    validate_transaction_signature,
)


class SpuriousDragonTransaction(HomesteadTransaction):
    def get_message_for_signing(self):
        if is_eip_155_signed_transaction(self):
            chain_id = extract_chain_id(self.v)
            txn_parts = rlp.decode(rlp.encode(self))
            txn_parts_for_signing = txn_parts[:-3] + [int_to_big_endian(chain_id), b'', b'']
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

    def check_signature_validity(self):
        if is_eip_155_signed_transaction(self):
            validate_eip155_transaction_signature(self)
        else:
            validate_transaction_signature(self)

    @classmethod
    def create_unsigned_transaction(cls, nonce, gas_price, gas, to, value, data):
        return SpuriousDragonUnsignedTransaction(nonce, gas_price, gas, to, value, data)


class SpuriousDragonUnsignedTransaction(HomesteadUnsignedTransaction):
    def as_signed_transaction(self, private_key, chain_id=None):
        if chain_id is None:
            v, r, s = create_transaction_signature(self, private_key)
        else:
            v, r, s = create_eip155_transaction_signature(self, private_key)
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
