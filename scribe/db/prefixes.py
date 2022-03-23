import typing
import struct
import array
import base64
import rocksdb
import rocksdb.interfaces
from typing import Union, Tuple, NamedTuple, Optional
from scribe.db.common import DB_PREFIXES
from scribe.db.interface import BasePrefixDB, ROW_TYPES, PrefixRow
from scribe.schema.url import normalize_name

ACTIVATED_CLAIM_TXO_TYPE = 1
ACTIVATED_SUPPORT_TXO_TYPE = 2


def length_encoded_name(name: str) -> bytes:
    encoded = name.encode('utf-8')
    return len(encoded).to_bytes(2, byteorder='big') + encoded


def length_prefix(key: str) -> bytes:
    return len(key).to_bytes(1, byteorder='big') + key.encode()


class UTXOKey(NamedTuple):
    hashX: bytes
    tx_num: int
    nout: int

    def __str__(self):
        return f"{self.__class__.__name__}(hashX={self.hashX.hex()}, tx_num={self.tx_num}, nout={self.nout})"


class UTXOValue(NamedTuple):
    amount: int


class HashXUTXOKey(NamedTuple):
    short_tx_hash: bytes
    tx_num: int
    nout: int

    def __str__(self):
        return f"{self.__class__.__name__}(short_tx_hash={self.short_tx_hash.hex()}, tx_num={self.tx_num}, nout={self.nout})"


class HashXUTXOValue(NamedTuple):
    hashX: bytes

    def __str__(self):
        return f"{self.__class__.__name__}(hashX={self.hashX.hex()})"


class HashXHistoryKey(NamedTuple):
    hashX: bytes
    height: int

    def __str__(self):
        return f"{self.__class__.__name__}(hashX={self.hashX.hex()}, height={self.height})"


class HashXHistoryValue(NamedTuple):
    hashXes: typing.List[int]


class BlockHashKey(NamedTuple):
    height: int


class BlockHashValue(NamedTuple):
    block_hash: bytes

    def __str__(self):
        return f"{self.__class__.__name__}(block_hash={self.block_hash.hex()})"


class BlockTxsKey(NamedTuple):
    height: int


class BlockTxsValue(NamedTuple):
    tx_hashes: typing.List[bytes]


class TxCountKey(NamedTuple):
    height: int


class TxCountValue(NamedTuple):
    tx_count: int


class TxHashKey(NamedTuple):
    tx_num: int


class TxHashValue(NamedTuple):
    tx_hash: bytes

    def __str__(self):
        return f"{self.__class__.__name__}(tx_hash={self.tx_hash[::-1].hex()})"


class TxNumKey(NamedTuple):
    tx_hash: bytes

    def __str__(self):
        return f"{self.__class__.__name__}(tx_hash={self.tx_hash[::-1].hex()})"


class TxNumValue(NamedTuple):
    tx_num: int


class TxKey(NamedTuple):
    tx_hash: bytes

    def __str__(self):
        return f"{self.__class__.__name__}(tx_hash={self.tx_hash[::-1].hex()})"


class TxValue(NamedTuple):
    raw_tx: bytes

    def __str__(self):
        return f"{self.__class__.__name__}(raw_tx={base64.b64encode(self.raw_tx).decode()})"


class BlockHeaderKey(NamedTuple):
    height: int


class BlockHeaderValue(NamedTuple):
    header: bytes

    def __str__(self):
        return f"{self.__class__.__name__}(header={base64.b64encode(self.header)})"


class ClaimToTXOKey(typing.NamedTuple):
    claim_hash: bytes

    def __str__(self):
        return f"{self.__class__.__name__}(claim_hash={self.claim_hash.hex()})"


class ClaimToTXOValue(typing.NamedTuple):
    tx_num: int
    position: int
    root_tx_num: int
    root_position: int
    amount: int
    # activation: int
    channel_signature_is_valid: bool
    name: str

    @property
    def normalized_name(self) -> str:
        try:
            return normalize_name(self.name)
        except UnicodeDecodeError:
            return self.name


class TXOToClaimKey(typing.NamedTuple):
    tx_num: int
    position: int


class TXOToClaimValue(typing.NamedTuple):
    claim_hash: bytes
    name: str

    def __str__(self):
        return f"{self.__class__.__name__}(claim_hash={self.claim_hash.hex()}, name={self.name})"


class ClaimShortIDKey(typing.NamedTuple):
    normalized_name: str
    partial_claim_id: str
    root_tx_num: int
    root_position: int

    def __str__(self):
        return f"{self.__class__.__name__}(normalized_name={self.normalized_name}, " \
               f"partial_claim_id={self.partial_claim_id}, " \
               f"root_tx_num={self.root_tx_num}, root_position={self.root_position})"


class ClaimShortIDValue(typing.NamedTuple):
    tx_num: int
    position: int


class ClaimToChannelKey(typing.NamedTuple):
    claim_hash: bytes
    tx_num: int
    position: int

    def __str__(self):
        return f"{self.__class__.__name__}(claim_hash={self.claim_hash.hex()}, " \
               f"tx_num={self.tx_num}, position={self.position})"


class ClaimToChannelValue(typing.NamedTuple):
    signing_hash: bytes

    def __str__(self):
        return f"{self.__class__.__name__}(signing_hash={self.signing_hash.hex()})"


class ChannelToClaimKey(typing.NamedTuple):
    signing_hash: bytes
    name: str
    tx_num: int
    position: int

    def __str__(self):
        return f"{self.__class__.__name__}(signing_hash={self.signing_hash.hex()}, name={self.name}, " \
               f"tx_num={self.tx_num}, position={self.position})"


class ChannelToClaimValue(typing.NamedTuple):
    claim_hash: bytes

    def __str__(self):
        return f"{self.__class__.__name__}(claim_hash={self.claim_hash.hex()})"


class ChannelCountKey(typing.NamedTuple):
    channel_hash: bytes

    def __str__(self):
        return f"{self.__class__.__name__}(channel_hash={self.channel_hash.hex()})"


class ChannelCountValue(typing.NamedTuple):
    count: int


class SupportAmountKey(typing.NamedTuple):
    claim_hash: bytes

    def __str__(self):
        return f"{self.__class__.__name__}(claim_hash={self.claim_hash.hex()})"


class SupportAmountValue(typing.NamedTuple):
    amount: int


class ClaimToSupportKey(typing.NamedTuple):
    claim_hash: bytes
    tx_num: int
    position: int

    def __str__(self):
        return f"{self.__class__.__name__}(claim_hash={self.claim_hash.hex()}, tx_num={self.tx_num}, " \
               f"position={self.position})"


class ClaimToSupportValue(typing.NamedTuple):
    amount: int


class SupportToClaimKey(typing.NamedTuple):
    tx_num: int
    position: int


class SupportToClaimValue(typing.NamedTuple):
    claim_hash: bytes

    def __str__(self):
        return f"{self.__class__.__name__}(claim_hash={self.claim_hash.hex()})"


class ClaimExpirationKey(typing.NamedTuple):
    expiration: int
    tx_num: int
    position: int


class ClaimExpirationValue(typing.NamedTuple):
    claim_hash: bytes
    normalized_name: str

    def __str__(self):
        return f"{self.__class__.__name__}(claim_hash={self.claim_hash.hex()}, normalized_name={self.normalized_name})"


class ClaimTakeoverKey(typing.NamedTuple):
    normalized_name: str


class ClaimTakeoverValue(typing.NamedTuple):
    claim_hash: bytes
    height: int

    def __str__(self):
        return f"{self.__class__.__name__}(claim_hash={self.claim_hash.hex()}, height={self.height})"


class PendingActivationKey(typing.NamedTuple):
    height: int
    txo_type: int
    tx_num: int
    position: int

    @property
    def is_support(self) -> bool:
        return self.txo_type == ACTIVATED_SUPPORT_TXO_TYPE

    @property
    def is_claim(self) -> bool:
        return self.txo_type == ACTIVATED_CLAIM_TXO_TYPE


class PendingActivationValue(typing.NamedTuple):
    claim_hash: bytes
    normalized_name: str

    def __str__(self):
        return f"{self.__class__.__name__}(claim_hash={self.claim_hash.hex()}, normalized_name={self.normalized_name})"


class ActivationKey(typing.NamedTuple):
    txo_type: int
    tx_num: int
    position: int


class ActivationValue(typing.NamedTuple):
    height: int
    claim_hash: bytes
    normalized_name: str

    def __str__(self):
        return f"{self.__class__.__name__}(height={self.height}, claim_hash={self.claim_hash.hex()}, " \
               f"normalized_name={self.normalized_name})"


class ActiveAmountKey(typing.NamedTuple):
    claim_hash: bytes
    txo_type: int
    activation_height: int
    tx_num: int
    position: int

    def __str__(self):
        return f"{self.__class__.__name__}(claim_hash={self.claim_hash.hex()}, txo_type={self.txo_type}, " \
               f"activation_height={self.activation_height}, tx_num={self.tx_num}, position={self.position})"


class ActiveAmountValue(typing.NamedTuple):
    amount: int


class EffectiveAmountKey(typing.NamedTuple):
    normalized_name: str
    effective_amount: int
    tx_num: int
    position: int


class EffectiveAmountValue(typing.NamedTuple):
    claim_hash: bytes

    def __str__(self):
        return f"{self.__class__.__name__}(claim_hash={self.claim_hash.hex()})"


class RepostKey(typing.NamedTuple):
    claim_hash: bytes

    def __str__(self):
        return f"{self.__class__.__name__}(claim_hash={self.claim_hash.hex()})"


class RepostValue(typing.NamedTuple):
    reposted_claim_hash: bytes

    def __str__(self):
        return f"{self.__class__.__name__}(reposted_claim_hash={self.reposted_claim_hash.hex()})"


class RepostedKey(typing.NamedTuple):
    reposted_claim_hash: bytes
    tx_num: int
    position: int

    def __str__(self):
        return f"{self.__class__.__name__}(reposted_claim_hash={self.reposted_claim_hash.hex()}, " \
               f"tx_num={self.tx_num}, position={self.position})"


class RepostedValue(typing.NamedTuple):
    claim_hash: bytes

    def __str__(self):
        return f"{self.__class__.__name__}(claim_hash={self.claim_hash.hex()})"


class TouchedOrDeletedClaimKey(typing.NamedTuple):
    height: int


class TouchedOrDeletedClaimValue(typing.NamedTuple):
    touched_claims: typing.Set[bytes]
    deleted_claims: typing.Set[bytes]

    def __str__(self):
        return f"{self.__class__.__name__}(" \
               f"touched_claims={','.join(map(lambda x: x.hex(), self.touched_claims))}," \
               f"deleted_claims={','.join(map(lambda x: x.hex(), self.deleted_claims))})"


class DBState(typing.NamedTuple):
    genesis: bytes
    height: int
    tx_count: int
    tip: bytes
    utxo_flush_count: int
    wall_time: int
    catching_up: bool
    db_version: int
    hist_flush_count: int
    comp_flush_count: int
    comp_cursor: int
    es_sync_height: int


class ActiveAmountPrefixRow(PrefixRow):
    prefix = DB_PREFIXES.active_amount.value
    key_struct = struct.Struct(b'>20sBLLH')
    value_struct = struct.Struct(b'>Q')
    key_part_lambdas = [
        lambda: b'',
        struct.Struct(b'>20s').pack,
        struct.Struct(b'>20sB').pack,
        struct.Struct(b'>20sBL').pack,
        struct.Struct(b'>20sBLL').pack,
        struct.Struct(b'>20sBLLH').pack
    ]
    cache_size = 1024 * 1024 * 128

    @classmethod
    def pack_key(cls, claim_hash: bytes, txo_type: int, activation_height: int, tx_num: int, position: int):
        return super().pack_key(claim_hash, txo_type, activation_height, tx_num, position)

    @classmethod
    def unpack_key(cls, key: bytes) -> ActiveAmountKey:
        return ActiveAmountKey(*super().unpack_key(key))

    @classmethod
    def unpack_value(cls, data: bytes) -> ActiveAmountValue:
        return ActiveAmountValue(*super().unpack_value(data))

    @classmethod
    def pack_value(cls, amount: int) -> bytes:
        return cls.value_struct.pack(amount)

    @classmethod
    def pack_item(cls, claim_hash: bytes, txo_type: int, activation_height: int, tx_num: int, position: int, amount: int):
        return cls.pack_key(claim_hash, txo_type, activation_height, tx_num, position), cls.pack_value(amount)


class ClaimToTXOPrefixRow(PrefixRow):
    prefix = DB_PREFIXES.claim_to_txo.value
    key_struct = struct.Struct(b'>20s')
    value_struct = struct.Struct(b'>LHLHQB')
    key_part_lambdas = [
        lambda: b'',
        struct.Struct(b'>20s').pack
    ]
    cache_size = 1024 * 1024 * 128

    @classmethod
    def pack_key(cls, claim_hash: bytes):
        return super().pack_key(claim_hash)

    @classmethod
    def unpack_key(cls, key: bytes) -> ClaimToTXOKey:
        assert key[:1] == cls.prefix and len(key) == 21
        return ClaimToTXOKey(key[1:])

    @classmethod
    def unpack_value(cls, data: bytes) -> ClaimToTXOValue:
        tx_num, position, root_tx_num, root_position, amount, channel_signature_is_valid = cls.value_struct.unpack(
            data[:21]
        )
        name_len = int.from_bytes(data[21:23], byteorder='big')
        name = data[23:23 + name_len].decode()
        return ClaimToTXOValue(
            tx_num, position, root_tx_num, root_position, amount, bool(channel_signature_is_valid), name
        )

    @classmethod
    def pack_value(cls, tx_num: int, position: int, root_tx_num: int, root_position: int, amount: int,
                   channel_signature_is_valid: bool, name: str) -> bytes:
        return cls.value_struct.pack(
            tx_num, position, root_tx_num, root_position, amount, int(channel_signature_is_valid)
        ) + length_encoded_name(name)

    @classmethod
    def pack_item(cls, claim_hash: bytes, tx_num: int, position: int, root_tx_num: int, root_position: int,
                  amount: int, channel_signature_is_valid: bool, name: str):
        return cls.pack_key(claim_hash), \
               cls.pack_value(tx_num, position, root_tx_num, root_position, amount, channel_signature_is_valid, name)


class TXOToClaimPrefixRow(PrefixRow):
    prefix = DB_PREFIXES.txo_to_claim.value
    key_struct = struct.Struct(b'>LH')
    value_struct = struct.Struct(b'>20s')
    cache_size = 1024 * 1024 * 128

    @classmethod
    def pack_key(cls, tx_num: int, position: int):
        return super().pack_key(tx_num, position)

    @classmethod
    def unpack_key(cls, key: bytes) -> TXOToClaimKey:
        return TXOToClaimKey(*super().unpack_key(key))

    @classmethod
    def unpack_value(cls, data: bytes) -> TXOToClaimValue:
        claim_hash, = cls.value_struct.unpack(data[:20])
        name_len = int.from_bytes(data[20:22], byteorder='big')
        name = data[22:22 + name_len].decode()
        return TXOToClaimValue(claim_hash, name)

    @classmethod
    def pack_value(cls, claim_hash: bytes, name: str) -> bytes:
        return cls.value_struct.pack(claim_hash) + length_encoded_name(name)

    @classmethod
    def pack_item(cls, tx_num: int, position: int, claim_hash: bytes, name: str):
        return cls.pack_key(tx_num, position), \
               cls.pack_value(claim_hash, name)


def shortid_key_helper(struct_fmt):
    packer = struct.Struct(struct_fmt).pack
    def wrapper(name, *args):
        return length_encoded_name(name) + packer(*args)
    return wrapper


def shortid_key_partial_claim_helper(name: str, partial_claim_id: str):
    assert len(partial_claim_id) < 40
    return length_encoded_name(name) + length_prefix(partial_claim_id)


class ClaimShortIDPrefixRow(PrefixRow):
    prefix = DB_PREFIXES.claim_short_id_prefix.value
    key_struct = struct.Struct(b'>LH')
    value_struct = struct.Struct(b'>LH')
    key_part_lambdas = [
        lambda: b'',
        length_encoded_name,
        shortid_key_partial_claim_helper
    ]

    @classmethod
    def pack_key(cls, name: str, short_claim_id: str, root_tx_num: int, root_position: int):
        return cls.prefix + length_encoded_name(name) + length_prefix(short_claim_id) +\
               cls.key_struct.pack(root_tx_num, root_position)

    @classmethod
    def pack_value(cls, tx_num: int, position: int):
        return super().pack_value(tx_num, position)

    @classmethod
    def unpack_key(cls, key: bytes) -> ClaimShortIDKey:
        assert key[:1] == cls.prefix
        name_len = int.from_bytes(key[1:3], byteorder='big')
        name = key[3:3 + name_len].decode()
        claim_id_len = int.from_bytes(key[3+name_len:4+name_len], byteorder='big')
        partial_claim_id = key[4+name_len:4+name_len+claim_id_len].decode()
        return ClaimShortIDKey(name, partial_claim_id, *cls.key_struct.unpack(key[4 + name_len + claim_id_len:]))

    @classmethod
    def unpack_value(cls, data: bytes) -> ClaimShortIDValue:
        return ClaimShortIDValue(*super().unpack_value(data))

    @classmethod
    def pack_item(cls, name: str, partial_claim_id: str, root_tx_num: int, root_position: int,
                  tx_num: int, position: int):
        return cls.pack_key(name, partial_claim_id, root_tx_num, root_position), \
               cls.pack_value(tx_num, position)


class ClaimToChannelPrefixRow(PrefixRow):
    prefix = DB_PREFIXES.claim_to_channel.value
    key_struct = struct.Struct(b'>20sLH')
    value_struct = struct.Struct(b'>20s')

    key_part_lambdas = [
        lambda: b'',
        struct.Struct(b'>20s').pack,
        struct.Struct(b'>20sL').pack,
        struct.Struct(b'>20sLH').pack
    ]

    @classmethod
    def pack_key(cls, claim_hash: bytes, tx_num: int, position: int):
        return super().pack_key(claim_hash, tx_num, position)

    @classmethod
    def pack_value(cls, signing_hash: bytes):
        return super().pack_value(signing_hash)

    @classmethod
    def unpack_key(cls, key: bytes) -> ClaimToChannelKey:
        return ClaimToChannelKey(*super().unpack_key(key))

    @classmethod
    def unpack_value(cls, data: bytes) -> ClaimToChannelValue:
        return ClaimToChannelValue(*super().unpack_value(data))

    @classmethod
    def pack_item(cls, claim_hash: bytes, tx_num: int, position: int, signing_hash: bytes):
        return cls.pack_key(claim_hash, tx_num, position), cls.pack_value(signing_hash)


def channel_to_claim_helper(struct_fmt):
    packer = struct.Struct(struct_fmt).pack

    def wrapper(signing_hash: bytes, name: str, *args):
        return signing_hash + length_encoded_name(name) + packer(*args)

    return wrapper


class ChannelToClaimPrefixRow(PrefixRow):
    prefix = DB_PREFIXES.channel_to_claim.value
    key_struct = struct.Struct(b'>LH')
    value_struct = struct.Struct(b'>20s')

    key_part_lambdas = [
        lambda: b'',
        struct.Struct(b'>20s').pack,
        channel_to_claim_helper(b''),
        channel_to_claim_helper(b'>s'),
        channel_to_claim_helper(b'>L'),
        channel_to_claim_helper(b'>LH'),
    ]

    @classmethod
    def pack_key(cls, signing_hash: bytes, name: str, tx_num: int, position: int):
        return cls.prefix + signing_hash + length_encoded_name(name) + cls.key_struct.pack(
            tx_num, position
        )

    @classmethod
    def unpack_key(cls, key: bytes) -> ChannelToClaimKey:
        assert key[:1] == cls.prefix
        signing_hash = key[1:21]
        name_len = int.from_bytes(key[21:23], byteorder='big')
        name = key[23:23 + name_len].decode()
        tx_num, position = cls.key_struct.unpack(key[23 + name_len:])
        return ChannelToClaimKey(
            signing_hash, name, tx_num, position
        )

    @classmethod
    def pack_value(cls, claim_hash: bytes) -> bytes:
        return super().pack_value(claim_hash)

    @classmethod
    def unpack_value(cls, data: bytes) -> ChannelToClaimValue:
        return ChannelToClaimValue(*cls.value_struct.unpack(data))

    @classmethod
    def pack_item(cls, signing_hash: bytes, name: str, tx_num: int, position: int,
                  claim_hash: bytes):
        return cls.pack_key(signing_hash, name, tx_num, position), \
               cls.pack_value(claim_hash)


class ClaimToSupportPrefixRow(PrefixRow):
    prefix = DB_PREFIXES.claim_to_support.value
    key_struct = struct.Struct(b'>20sLH')
    value_struct = struct.Struct(b'>Q')

    key_part_lambdas = [
        lambda: b'',
        struct.Struct(b'>20s').pack,
        struct.Struct(b'>20sL').pack,
        struct.Struct(b'>20sLH').pack
    ]

    @classmethod
    def pack_key(cls, claim_hash: bytes, tx_num: int, position: int):
        return super().pack_key(claim_hash, tx_num, position)

    @classmethod
    def unpack_key(cls, key: bytes) -> ClaimToSupportKey:
        return ClaimToSupportKey(*super().unpack_key(key))

    @classmethod
    def pack_value(cls, amount: int) -> bytes:
        return super().pack_value(amount)

    @classmethod
    def unpack_value(cls, data: bytes) -> ClaimToSupportValue:
        return ClaimToSupportValue(*super().unpack_value(data))

    @classmethod
    def pack_item(cls, claim_hash: bytes, tx_num: int, position: int, amount: int):
        return cls.pack_key(claim_hash, tx_num, position), \
               cls.pack_value(amount)


class SupportToClaimPrefixRow(PrefixRow):
    prefix = DB_PREFIXES.support_to_claim.value
    key_struct = struct.Struct(b'>LH')
    value_struct = struct.Struct(b'>20s')

    @classmethod
    def pack_key(cls, tx_num: int, position: int):
        return super().pack_key(tx_num, position)

    @classmethod
    def unpack_key(cls, key: bytes) -> SupportToClaimKey:
        return SupportToClaimKey(*super().unpack_key(key))

    @classmethod
    def pack_value(cls, claim_hash: bytes) -> bytes:
        return super().pack_value(claim_hash)

    @classmethod
    def unpack_value(cls, data: bytes) -> SupportToClaimValue:
        return SupportToClaimValue(*super().unpack_value(data))

    @classmethod
    def pack_item(cls, tx_num: int, position: int, claim_hash: bytes):
        return cls.pack_key(tx_num, position), \
               cls.pack_value(claim_hash)


class ClaimExpirationPrefixRow(PrefixRow):
    prefix = DB_PREFIXES.claim_expiration.value
    key_struct = struct.Struct(b'>LLH')
    value_struct = struct.Struct(b'>20s')
    key_part_lambdas = [
        lambda: b'',
        struct.Struct(b'>L').pack,
        struct.Struct(b'>LL').pack,
        struct.Struct(b'>LLH').pack,
    ]

    @classmethod
    def pack_key(cls, expiration: int, tx_num: int, position: int) -> bytes:
        return super().pack_key(expiration, tx_num, position)

    @classmethod
    def pack_value(cls, claim_hash: bytes, name: str) -> bytes:
        return cls.value_struct.pack(claim_hash) + length_encoded_name(name)

    @classmethod
    def pack_item(cls, expiration: int, tx_num: int, position: int, claim_hash: bytes, name: str) -> typing.Tuple[bytes, bytes]:
        return cls.pack_key(expiration, tx_num, position), cls.pack_value(claim_hash, name)

    @classmethod
    def unpack_key(cls, key: bytes) -> ClaimExpirationKey:
        return ClaimExpirationKey(*super().unpack_key(key))

    @classmethod
    def unpack_value(cls, data: bytes) -> ClaimExpirationValue:
        name_len = int.from_bytes(data[20:22], byteorder='big')
        name = data[22:22 + name_len].decode()
        claim_id, = cls.value_struct.unpack(data[:20])
        return ClaimExpirationValue(claim_id, name)

    @classmethod
    def unpack_item(cls, key: bytes, value: bytes) -> typing.Tuple[ClaimExpirationKey, ClaimExpirationValue]:
        return cls.unpack_key(key), cls.unpack_value(value)


class ClaimTakeoverPrefixRow(PrefixRow):
    prefix = DB_PREFIXES.claim_takeover.value
    value_struct = struct.Struct(b'>20sL')

    key_part_lambdas = [
        lambda: b'',
        length_encoded_name
    ]

    @classmethod
    def pack_key(cls, name: str):
        return cls.prefix + length_encoded_name(name)

    @classmethod
    def pack_value(cls, claim_hash: bytes, takeover_height: int):
        return super().pack_value(claim_hash, takeover_height)

    @classmethod
    def unpack_key(cls, key: bytes) -> ClaimTakeoverKey:
        assert key[:1] == cls.prefix
        name_len = int.from_bytes(key[1:3], byteorder='big')
        name = key[3:3 + name_len].decode()
        return ClaimTakeoverKey(name)

    @classmethod
    def unpack_value(cls, data: bytes) -> ClaimTakeoverValue:
        return ClaimTakeoverValue(*super().unpack_value(data))

    @classmethod
    def pack_item(cls, name: str, claim_hash: bytes, takeover_height: int):
        return cls.pack_key(name), cls.pack_value(claim_hash, takeover_height)


class PendingActivationPrefixRow(PrefixRow):
    prefix = DB_PREFIXES.pending_activation.value
    key_struct = struct.Struct(b'>LBLH')
    key_part_lambdas = [
        lambda: b'',
        struct.Struct(b'>L').pack,
        struct.Struct(b'>LB').pack,
        struct.Struct(b'>LBL').pack,
        struct.Struct(b'>LBLH').pack
    ]

    @classmethod
    def pack_key(cls, height: int, txo_type: int, tx_num: int, position: int):
        return super().pack_key(height, txo_type, tx_num, position)

    @classmethod
    def unpack_key(cls, key: bytes) -> PendingActivationKey:
        return PendingActivationKey(*super().unpack_key(key))

    @classmethod
    def pack_value(cls, claim_hash: bytes, name: str) -> bytes:
        return claim_hash + length_encoded_name(name)

    @classmethod
    def unpack_value(cls, data: bytes) -> PendingActivationValue:
        claim_hash = data[:20]
        name_len = int.from_bytes(data[20:22], byteorder='big')
        name = data[22:22 + name_len].decode()
        return PendingActivationValue(claim_hash, name)

    @classmethod
    def pack_item(cls, height: int, txo_type: int, tx_num: int, position: int, claim_hash: bytes, name: str):
        return cls.pack_key(height, txo_type, tx_num, position), \
               cls.pack_value(claim_hash, name)


class ActivatedPrefixRow(PrefixRow):
    prefix = DB_PREFIXES.activated_claim_and_support.value
    key_struct = struct.Struct(b'>BLH')
    value_struct = struct.Struct(b'>L20s')
    key_part_lambdas = [
        lambda: b'',
        struct.Struct(b'>B').pack,
        struct.Struct(b'>BL').pack,
        struct.Struct(b'>BLH').pack
    ]

    @classmethod
    def pack_key(cls, txo_type: int, tx_num: int, position: int):
        return super().pack_key(txo_type, tx_num, position)

    @classmethod
    def unpack_key(cls, key: bytes) -> ActivationKey:
        return ActivationKey(*super().unpack_key(key))

    @classmethod
    def pack_value(cls, height: int, claim_hash: bytes, name: str) -> bytes:
        return cls.value_struct.pack(height, claim_hash) + length_encoded_name(name)

    @classmethod
    def unpack_value(cls, data: bytes) -> ActivationValue:
        height, claim_hash = cls.value_struct.unpack(data[:24])
        name_len = int.from_bytes(data[24:26], byteorder='big')
        name = data[26:26 + name_len].decode()
        return ActivationValue(height, claim_hash, name)

    @classmethod
    def pack_item(cls, txo_type: int, tx_num: int, position: int, height: int, claim_hash: bytes, name: str):
        return cls.pack_key(txo_type, tx_num, position), \
               cls.pack_value(height, claim_hash, name)


def effective_amount_helper(struct_fmt):
    packer = struct.Struct(struct_fmt).pack

    def wrapper(name, *args):
        if not args:
            return length_encoded_name(name)
        if len(args) == 1:
            return length_encoded_name(name) + packer(0xffffffffffffffff - args[0])
        return length_encoded_name(name) + packer(0xffffffffffffffff - args[0], *args[1:])

    return wrapper


class EffectiveAmountPrefixRow(PrefixRow):
    prefix = DB_PREFIXES.effective_amount.value
    key_struct = struct.Struct(b'>QLH')
    value_struct = struct.Struct(b'>20s')
    key_part_lambdas = [
        lambda: b'',
        length_encoded_name,
        shortid_key_helper(b'>Q'),
        shortid_key_helper(b'>QL'),
        shortid_key_helper(b'>QLH'),
    ]
    cache_size = 1024 * 1024 * 128

    @classmethod
    def pack_key(cls, name: str, effective_amount: int, tx_num: int, position: int):
        return cls.prefix + length_encoded_name(name) + cls.key_struct.pack(
                    0xffffffffffffffff - effective_amount, tx_num, position
        )

    @classmethod
    def unpack_key(cls, key: bytes) -> EffectiveAmountKey:
        assert key[:1] == cls.prefix
        name_len = int.from_bytes(key[1:3], byteorder='big')
        name = key[3:3 + name_len].decode()
        ones_comp_effective_amount, tx_num, position = cls.key_struct.unpack(key[3 + name_len:])
        return EffectiveAmountKey(name, 0xffffffffffffffff - ones_comp_effective_amount, tx_num, position)

    @classmethod
    def unpack_value(cls, data: bytes) -> EffectiveAmountValue:
        return EffectiveAmountValue(*super().unpack_value(data))

    @classmethod
    def pack_value(cls, claim_hash: bytes) -> bytes:
        return super().pack_value(claim_hash)

    @classmethod
    def pack_item(cls, name: str, effective_amount: int, tx_num: int, position: int, claim_hash: bytes):
        return cls.pack_key(name, effective_amount, tx_num, position), cls.pack_value(claim_hash)


class RepostPrefixRow(PrefixRow):
    prefix = DB_PREFIXES.repost.value
    key_struct = struct.Struct(b'>20s')

    key_part_lambdas = [
        lambda: b'',
        struct.Struct(b'>20s').pack
    ]

    @classmethod
    def pack_key(cls, claim_hash: bytes):
        return super().pack_key(claim_hash)

    @classmethod
    def unpack_key(cls, key: bytes) -> RepostKey:
        return RepostKey(*super().unpack_key(key))

    @classmethod
    def pack_value(cls, reposted_claim_hash: bytes) -> bytes:
        return reposted_claim_hash

    @classmethod
    def unpack_value(cls, data: bytes) -> RepostValue:
        return RepostValue(data)

    @classmethod
    def pack_item(cls, claim_hash: bytes, reposted_claim_hash: bytes):
        return cls.pack_key(claim_hash), cls.pack_value(reposted_claim_hash)


class RepostedPrefixRow(PrefixRow):
    prefix = DB_PREFIXES.reposted_claim.value
    key_struct = struct.Struct(b'>20sLH')
    value_struct = struct.Struct(b'>20s')
    key_part_lambdas = [
        lambda: b'',
        struct.Struct(b'>20s').pack,
        struct.Struct(b'>20sL').pack,
        struct.Struct(b'>20sLH').pack
    ]

    @classmethod
    def pack_key(cls, reposted_claim_hash: bytes, tx_num: int, position: int):
        return super().pack_key(reposted_claim_hash, tx_num, position)

    @classmethod
    def unpack_key(cls, key: bytes) -> RepostedKey:
        return RepostedKey(*super().unpack_key(key))

    @classmethod
    def pack_value(cls, claim_hash: bytes) -> bytes:
        return super().pack_value(claim_hash)

    @classmethod
    def unpack_value(cls, data: bytes) -> RepostedValue:
        return RepostedValue(*super().unpack_value(data))

    @classmethod
    def pack_item(cls, reposted_claim_hash: bytes, tx_num: int, position: int, claim_hash: bytes):
        return cls.pack_key(reposted_claim_hash, tx_num, position), cls.pack_value(claim_hash)


class UndoKey(NamedTuple):
    height: int
    block_hash: bytes


class UndoPrefixRow(PrefixRow):
    prefix = DB_PREFIXES.undo.value
    key_struct = struct.Struct(b'>Q32s')

    key_part_lambdas = [
        lambda: b'',
        struct.Struct(b'>Q').pack,
        struct.Struct(b'>Q32s').pack
    ]

    @classmethod
    def pack_key(cls, height: int, block_hash: bytes):
        return super().pack_key(height, block_hash)

    @classmethod
    def unpack_key(cls, key: bytes) -> UndoKey:
        return UndoKey(*super().unpack_key(key))

    @classmethod
    def pack_value(cls, undo_ops: bytes) -> bytes:
        return undo_ops

    @classmethod
    def unpack_value(cls, data: bytes) -> bytes:
        return data

    @classmethod
    def pack_item(cls, height: int, block_hash: bytes, undo_ops: bytes):
        return cls.pack_key(height, block_hash), cls.pack_value(undo_ops)


class BlockHashPrefixRow(PrefixRow):
    prefix = DB_PREFIXES.block_hash.value
    key_struct = struct.Struct(b'>L')
    value_struct = struct.Struct(b'>32s')

    key_part_lambdas = [
        lambda: b'',
        struct.Struct(b'>L').pack
    ]

    @classmethod
    def pack_key(cls, height: int) -> bytes:
        return super().pack_key(height)

    @classmethod
    def unpack_key(cls, key: bytes) -> BlockHashKey:
        return BlockHashKey(*super().unpack_key(key))

    @classmethod
    def pack_value(cls, block_hash: bytes) -> bytes:
        return super().pack_value(block_hash)

    @classmethod
    def unpack_value(cls, data: bytes) -> BlockHashValue:
        return BlockHashValue(*super().unpack_value(data))

    @classmethod
    def pack_item(cls, height: int, block_hash: bytes):
        return cls.pack_key(height), cls.pack_value(block_hash)


class BlockHeaderPrefixRow(PrefixRow):
    prefix = DB_PREFIXES.header.value
    key_struct = struct.Struct(b'>L')
    value_struct = struct.Struct(b'>112s')

    key_part_lambdas = [
        lambda: b'',
        struct.Struct(b'>L').pack
    ]

    @classmethod
    def pack_key(cls, height: int) -> bytes:
        return super().pack_key(height)

    @classmethod
    def unpack_key(cls, key: bytes) -> BlockHeaderKey:
        return BlockHeaderKey(*super().unpack_key(key))

    @classmethod
    def pack_value(cls, header: bytes) -> bytes:
        return super().pack_value(header)

    @classmethod
    def unpack_value(cls, data: bytes) -> BlockHeaderValue:
        return BlockHeaderValue(*super().unpack_value(data))

    @classmethod
    def pack_item(cls, height: int, header: bytes):
        return cls.pack_key(height), cls.pack_value(header)


class TXNumPrefixRow(PrefixRow):
    prefix = DB_PREFIXES.tx_num.value
    key_struct = struct.Struct(b'>32s')
    value_struct = struct.Struct(b'>L')

    key_part_lambdas = [
        lambda: b'',
        struct.Struct(b'>32s').pack
    ]

    @classmethod
    def pack_key(cls, tx_hash: bytes) -> bytes:
        return super().pack_key(tx_hash)

    @classmethod
    def unpack_key(cls, tx_hash: bytes) -> TxNumKey:
        return TxNumKey(*super().unpack_key(tx_hash))

    @classmethod
    def pack_value(cls, tx_num: int) -> bytes:
        return super().pack_value(tx_num)

    @classmethod
    def unpack_value(cls, data: bytes) -> TxNumValue:
        return TxNumValue(*super().unpack_value(data))

    @classmethod
    def pack_item(cls, tx_hash: bytes, tx_num: int):
        return cls.pack_key(tx_hash), cls.pack_value(tx_num)


class TxCountPrefixRow(PrefixRow):
    prefix = DB_PREFIXES.tx_count.value
    key_struct = struct.Struct(b'>L')
    value_struct = struct.Struct(b'>L')

    key_part_lambdas = [
        lambda: b'',
        struct.Struct(b'>L').pack
    ]

    @classmethod
    def pack_key(cls, height: int) -> bytes:
        return super().pack_key(height)

    @classmethod
    def unpack_key(cls, key: bytes) -> TxCountKey:
        return TxCountKey(*super().unpack_key(key))

    @classmethod
    def pack_value(cls, tx_count: int) -> bytes:
        return super().pack_value(tx_count)

    @classmethod
    def unpack_value(cls, data: bytes) -> TxCountValue:
        return TxCountValue(*super().unpack_value(data))

    @classmethod
    def pack_item(cls, height: int, tx_count: int):
        return cls.pack_key(height), cls.pack_value(tx_count)


class TXHashPrefixRow(PrefixRow):
    prefix = DB_PREFIXES.tx_hash.value
    key_struct = struct.Struct(b'>L')
    value_struct = struct.Struct(b'>32s')

    key_part_lambdas = [
        lambda: b'',
        struct.Struct(b'>L').pack
    ]

    @classmethod
    def pack_key(cls, tx_num: int) -> bytes:
        return super().pack_key(tx_num)

    @classmethod
    def unpack_key(cls, key: bytes) -> TxHashKey:
        return TxHashKey(*super().unpack_key(key))

    @classmethod
    def pack_value(cls, tx_hash: bytes) -> bytes:
        return super().pack_value(tx_hash)

    @classmethod
    def unpack_value(cls, data: bytes) -> TxHashValue:
        return TxHashValue(*super().unpack_value(data))

    @classmethod
    def pack_item(cls, tx_num: int, tx_hash: bytes):
        return cls.pack_key(tx_num), cls.pack_value(tx_hash)


class TXPrefixRow(PrefixRow):
    prefix = DB_PREFIXES.tx.value
    key_struct = struct.Struct(b'>32s')

    key_part_lambdas = [
        lambda: b'',
        struct.Struct(b'>32s').pack
    ]

    @classmethod
    def pack_key(cls, tx_hash: bytes) -> bytes:
        return super().pack_key(tx_hash)

    @classmethod
    def unpack_key(cls, tx_hash: bytes) -> TxKey:
        return TxKey(*super().unpack_key(tx_hash))

    @classmethod
    def pack_value(cls, tx: bytes) -> bytes:
        return tx

    @classmethod
    def unpack_value(cls, data: bytes) -> TxValue:
        return TxValue(data)

    @classmethod
    def pack_item(cls, tx_hash: bytes, raw_tx: bytes):
        return cls.pack_key(tx_hash), cls.pack_value(raw_tx)


class UTXOPrefixRow(PrefixRow):
    prefix = DB_PREFIXES.utxo.value
    key_struct = struct.Struct(b'>11sLH')
    value_struct = struct.Struct(b'>Q')

    key_part_lambdas = [
        lambda: b'',
        struct.Struct(b'>11s').pack,
        struct.Struct(b'>11sL').pack,
        struct.Struct(b'>11sLH').pack
    ]

    @classmethod
    def pack_key(cls, hashX: bytes, tx_num, nout: int):
        return super().pack_key(hashX, tx_num, nout)

    @classmethod
    def unpack_key(cls, key: bytes) -> UTXOKey:
        return UTXOKey(*super().unpack_key(key))

    @classmethod
    def pack_value(cls, amount: int) -> bytes:
        return super().pack_value(amount)

    @classmethod
    def unpack_value(cls, data: bytes) -> UTXOValue:
        return UTXOValue(*cls.value_struct.unpack(data))

    @classmethod
    def pack_item(cls, hashX: bytes, tx_num: int, nout: int, amount: int):
        return cls.pack_key(hashX, tx_num, nout), cls.pack_value(amount)


class HashXUTXOPrefixRow(PrefixRow):
    prefix = DB_PREFIXES.hashx_utxo.value
    key_struct = struct.Struct(b'>4sLH')
    value_struct = struct.Struct(b'>11s')

    key_part_lambdas = [
        lambda: b'',
        struct.Struct(b'>4s').pack,
        struct.Struct(b'>4sL').pack,
        struct.Struct(b'>4sLH').pack
    ]

    @classmethod
    def pack_key(cls, short_tx_hash: bytes, tx_num, nout: int):
        return super().pack_key(short_tx_hash, tx_num, nout)

    @classmethod
    def unpack_key(cls, key: bytes) -> HashXUTXOKey:
        return HashXUTXOKey(*super().unpack_key(key))

    @classmethod
    def pack_value(cls, hashX: bytes) -> bytes:
        return super().pack_value(hashX)

    @classmethod
    def unpack_value(cls, data: bytes) -> HashXUTXOValue:
        return HashXUTXOValue(*cls.value_struct.unpack(data))

    @classmethod
    def pack_item(cls, short_tx_hash: bytes, tx_num: int, nout: int, hashX: bytes):
        return cls.pack_key(short_tx_hash, tx_num, nout), cls.pack_value(hashX)


class HashXHistoryPrefixRow(PrefixRow):
    prefix = DB_PREFIXES.hashx_history.value
    key_struct = struct.Struct(b'>11sL')

    key_part_lambdas = [
        lambda: b'',
        struct.Struct(b'>11s').pack,
        struct.Struct(b'>11sL').pack
    ]

    @classmethod
    def pack_key(cls, hashX: bytes, height: int):
        return super().pack_key(hashX, height)

    @classmethod
    def unpack_key(cls, key: bytes) -> HashXHistoryKey:
        return HashXHistoryKey(*super().unpack_key(key))

    @classmethod
    def pack_value(cls, history: typing.List[int]) -> bytes:
        a = array.array('I')
        a.fromlist(history)
        return a.tobytes()

    @classmethod
    def unpack_value(cls, data: bytes) -> array.array:
        a = array.array('I')
        a.frombytes(data)
        return a

    @classmethod
    def pack_item(cls, hashX: bytes, height: int, history: typing.List[int]):
        return cls.pack_key(hashX, height), cls.pack_value(history)


class TouchedOrDeletedPrefixRow(PrefixRow):
    prefix = DB_PREFIXES.touched_or_deleted.value
    key_struct = struct.Struct(b'>L')
    value_struct = struct.Struct(b'>LL')
    key_part_lambdas = [
        lambda: b'',
        struct.Struct(b'>L').pack
    ]

    @classmethod
    def pack_key(cls, height: int):
        return super().pack_key(height)

    @classmethod
    def unpack_key(cls, key: bytes) -> TouchedOrDeletedClaimKey:
        return TouchedOrDeletedClaimKey(*super().unpack_key(key))

    @classmethod
    def pack_value(cls, touched: typing.Set[bytes], deleted: typing.Set[bytes]) -> bytes:
        assert True if not touched else all(len(item) == 20 for item in touched)
        assert True if not deleted else all(len(item) == 20 for item in deleted)
        return cls.value_struct.pack(len(touched), len(deleted)) + b''.join(sorted(touched)) + b''.join(sorted(deleted))

    @classmethod
    def unpack_value(cls, data: bytes) -> TouchedOrDeletedClaimValue:
        touched_len, deleted_len = cls.value_struct.unpack(data[:8])
        data = data[8:]
        assert len(data) == 20 * (touched_len + deleted_len)
        touched_bytes, deleted_bytes = data[:touched_len*20], data[touched_len*20:]
        return TouchedOrDeletedClaimValue(
            {touched_bytes[20*i:20*(i+1)] for i in range(touched_len)},
            {deleted_bytes[20*i:20*(i+1)] for i in range(deleted_len)}
        )

    @classmethod
    def pack_item(cls, height, touched, deleted):
        return cls.pack_key(height), cls.pack_value(touched, deleted)


class ChannelCountPrefixRow(PrefixRow):
    prefix = DB_PREFIXES.channel_count.value
    key_struct = struct.Struct(b'>20s')
    value_struct = struct.Struct(b'>L')
    key_part_lambdas = [
        lambda: b'',
        struct.Struct(b'>20s').pack
    ]

    @classmethod
    def pack_key(cls, channel_hash: bytes):
        return super().pack_key(channel_hash)

    @classmethod
    def unpack_key(cls, key: bytes) -> ChannelCountKey:
        return ChannelCountKey(*super().unpack_key(key))

    @classmethod
    def pack_value(cls, count: int) -> bytes:
        return super().pack_value(count)

    @classmethod
    def unpack_value(cls, data: bytes) -> ChannelCountValue:
        return ChannelCountValue(*super().unpack_value(data))

    @classmethod
    def pack_item(cls, channel_hash, count):
        return cls.pack_key(channel_hash), cls.pack_value(count)


class SupportAmountPrefixRow(PrefixRow):
    prefix = DB_PREFIXES.support_amount.value
    key_struct = struct.Struct(b'>20s')
    value_struct = struct.Struct(b'>Q')
    key_part_lambdas = [
        lambda: b'',
        struct.Struct(b'>20s').pack
    ]

    @classmethod
    def pack_key(cls, claim_hash: bytes):
        return super().pack_key(claim_hash)

    @classmethod
    def unpack_key(cls, key: bytes) -> SupportAmountKey:
        return SupportAmountKey(*super().unpack_key(key))

    @classmethod
    def pack_value(cls, amount: int) -> bytes:
        return super().pack_value(amount)

    @classmethod
    def unpack_value(cls, data: bytes) -> SupportAmountValue:
        return SupportAmountValue(*super().unpack_value(data))

    @classmethod
    def pack_item(cls, claim_hash, amount):
        return cls.pack_key(claim_hash), cls.pack_value(amount)


class DBStatePrefixRow(PrefixRow):
    prefix = DB_PREFIXES.db_state.value
    value_struct = struct.Struct(b'>32sLL32sLLBBlllL')
    key_struct = struct.Struct(b'')

    key_part_lambdas = [
        lambda: b''
    ]

    @classmethod
    def pack_key(cls) -> bytes:
        return cls.prefix

    @classmethod
    def unpack_key(cls, key: bytes):
        return

    @classmethod
    def pack_value(cls, genesis: bytes, height: int, tx_count: int, tip: bytes, utxo_flush_count: int, wall_time: int,
                   catching_up: bool, db_version: int, hist_flush_count: int, comp_flush_count: int,
                   comp_cursor: int, es_sync_height: int) -> bytes:
        return super().pack_value(
            genesis, height, tx_count, tip, utxo_flush_count,
            wall_time, 1 if catching_up else 0, db_version, hist_flush_count,
            comp_flush_count, comp_cursor, es_sync_height
        )

    @classmethod
    def unpack_value(cls, data: bytes) -> DBState:
        if len(data) == 94:
            # TODO: delete this after making a new snapshot - 10/20/21
            # migrate in the es_sync_height if it doesnt exist
            data += data[32:36]
        return DBState(*super().unpack_value(data))

    @classmethod
    def pack_item(cls, genesis: bytes, height: int, tx_count: int, tip: bytes, utxo_flush_count: int, wall_time: int,
                  catching_up: bool, db_version: int, hist_flush_count: int, comp_flush_count: int,
                  comp_cursor: int, es_sync_height: int):
        return cls.pack_key(), cls.pack_value(
            genesis, height, tx_count, tip, utxo_flush_count, wall_time, catching_up, db_version, hist_flush_count,
            comp_flush_count, comp_cursor, es_sync_height
        )


class BlockTxsPrefixRow(PrefixRow):
    prefix = DB_PREFIXES.block_tx.value
    key_struct = struct.Struct(b'>L')
    key_part_lambdas = [
        lambda: b'',
        struct.Struct(b'>L').pack
    ]

    @classmethod
    def pack_key(cls, height: int):
        return super().pack_key(height)

    @classmethod
    def unpack_key(cls, key: bytes) -> BlockTxsKey:
        return BlockTxsKey(*super().unpack_key(key))

    @classmethod
    def pack_value(cls, tx_hashes: typing.List[bytes]) -> bytes:
        assert all(len(tx_hash) == 32 for tx_hash in tx_hashes)
        return b''.join(tx_hashes)

    @classmethod
    def unpack_value(cls, data: bytes) -> BlockTxsValue:
        return BlockTxsValue([data[i*32:(i+1)*32] for i in range(len(data) // 32)])

    @classmethod
    def pack_item(cls, height, tx_hashes):
        return cls.pack_key(height), cls.pack_value(tx_hashes)


class MempoolTxKey(NamedTuple):
    tx_hash: bytes

    def __str__(self):
        return f"{self.__class__.__name__}(tx_hash={self.tx_hash[::-1].hex()})"


class MempoolTxValue(NamedTuple):
    raw_tx: bytes

    def __str__(self):
        return f"{self.__class__.__name__}(raw_tx={base64.b64encode(self.raw_tx).decode()})"


class MempoolTXPrefixRow(PrefixRow):
    prefix = DB_PREFIXES.mempool_tx.value
    key_struct = struct.Struct(b'>32s')

    MAX_TX_HASH = b'\xff' * 32
    MIN_TX_HASH = b'\x00' * 32

    key_part_lambdas = [
        lambda: b'',
        struct.Struct(b'>32s').pack
    ]

    @classmethod
    def pack_key(cls, tx_hash: bytes) -> bytes:
        return super().pack_key(tx_hash)

    @classmethod
    def unpack_key(cls, tx_hash: bytes) -> MempoolTxKey:
        return MempoolTxKey(*super().unpack_key(tx_hash))

    @classmethod
    def pack_value(cls, tx: bytes) -> bytes:
        return tx

    @classmethod
    def unpack_value(cls, data: bytes) -> MempoolTxValue:
        return MempoolTxValue(data)

    @classmethod
    def pack_item(cls, tx_hash: bytes, raw_tx: bytes):
        return cls.pack_key(tx_hash), cls.pack_value(raw_tx)


class TrendingNotificationKey(typing.NamedTuple):
    height: int
    claim_hash: bytes


class TrendingNotificationValue(typing.NamedTuple):
    previous_amount: int
    new_amount: int


class TrendingNotificationPrefixRow(PrefixRow):
    prefix = DB_PREFIXES.trending_notifications.value
    key_struct = struct.Struct(b'>L20s')
    value_struct = struct.Struct(b'>QQ')
    key_part_lambdas = [
        lambda: b'',
        struct.Struct(b'>L').pack,
        struct.Struct(b'>L20s').pack
    ]

    @classmethod
    def pack_key(cls, height: int, claim_hash: bytes):
        return super().pack_key(height, claim_hash)

    @classmethod
    def unpack_key(cls, key: bytes) -> TrendingNotificationKey:
        return TrendingNotificationKey(*super().unpack_key(key))

    @classmethod
    def pack_value(cls, previous_amount: int, new_amount: int) -> bytes:
        return super().pack_value(previous_amount, new_amount)

    @classmethod
    def unpack_value(cls, data: bytes) -> TrendingNotificationValue:
        return TrendingNotificationValue(*super().unpack_value(data))

    @classmethod
    def pack_item(cls, height, claim_hash, previous_amount, new_amount):
        return cls.pack_key(height, claim_hash), cls.pack_value(previous_amount, new_amount)


class TouchedHashXKey(NamedTuple):
    height: int


class TouchedHashXValue(NamedTuple):
    touched_hashXs: typing.List[bytes]

    def __str__(self):
        return f"{self.__class__.__name__}(touched_hashXs=[{', '.join(map(lambda x: x.hex(), self.touched_hashXs))}])"


class TouchedHashXPrefixRow(PrefixRow):
    prefix = DB_PREFIXES.touched_hashX.value
    key_struct = struct.Struct(b'>L')

    key_part_lambdas = [
        lambda: b'',
        struct.Struct(b'>L').pack
    ]

    @classmethod
    def pack_key(cls, height: int):
        return super().pack_key(height)

    @classmethod
    def unpack_key(cls, key: bytes) -> TouchedHashXKey:
        return TouchedHashXKey(*super().unpack_key(key))

    @classmethod
    def pack_value(cls, touched: typing.List[bytes]) -> bytes:
        assert all(map(lambda item: len(item) == 11, touched))
        return b''.join(touched)

    @classmethod
    def unpack_value(cls, data: bytes) -> TouchedHashXValue:
        return TouchedHashXValue([data[idx*11:(idx*11)+11] for idx in range(len(data) // 11)])

    @classmethod
    def pack_item(cls, height: int, touched: typing.List[bytes]):
        return cls.pack_key(height), cls.pack_value(touched)


class PrefixDB(BasePrefixDB):
    def __init__(self, path: str, cache_mb: int = 128, reorg_limit: int = 200, max_open_files: int = 64,
                 secondary_path: str = '', unsafe_prefixes: Optional[typing.Set[bytes]] = None):
        super().__init__(path, max_open_files=max_open_files, secondary_path=secondary_path,
                         max_undo_depth=reorg_limit, unsafe_prefixes=unsafe_prefixes)
        db = self._db
        self.claim_to_support = ClaimToSupportPrefixRow(db, self._op_stack)
        self.support_to_claim = SupportToClaimPrefixRow(db, self._op_stack)
        self.claim_to_txo = ClaimToTXOPrefixRow(db, self._op_stack)
        self.txo_to_claim = TXOToClaimPrefixRow(db, self._op_stack)
        self.claim_to_channel = ClaimToChannelPrefixRow(db, self._op_stack)
        self.channel_to_claim = ChannelToClaimPrefixRow(db, self._op_stack)
        self.claim_short_id = ClaimShortIDPrefixRow(db, self._op_stack)
        self.claim_expiration = ClaimExpirationPrefixRow(db, self._op_stack)
        self.claim_takeover = ClaimTakeoverPrefixRow(db, self._op_stack)
        self.pending_activation = PendingActivationPrefixRow(db, self._op_stack)
        self.activated = ActivatedPrefixRow(db, self._op_stack)
        self.active_amount = ActiveAmountPrefixRow(db, self._op_stack)
        self.effective_amount = EffectiveAmountPrefixRow(db, self._op_stack)
        self.repost = RepostPrefixRow(db, self._op_stack)
        self.reposted_claim = RepostedPrefixRow(db, self._op_stack)
        self.undo = UndoPrefixRow(db, self._op_stack)
        self.utxo = UTXOPrefixRow(db, self._op_stack)
        self.hashX_utxo = HashXUTXOPrefixRow(db, self._op_stack)
        self.hashX_history = HashXHistoryPrefixRow(db, self._op_stack)
        self.block_hash = BlockHashPrefixRow(db, self._op_stack)
        self.tx_count = TxCountPrefixRow(db, self._op_stack)
        self.tx_hash = TXHashPrefixRow(db, self._op_stack)
        self.tx_num = TXNumPrefixRow(db, self._op_stack)
        self.tx = TXPrefixRow(db, self._op_stack)
        self.header = BlockHeaderPrefixRow(db, self._op_stack)
        self.touched_or_deleted = TouchedOrDeletedPrefixRow(db, self._op_stack)
        self.channel_count = ChannelCountPrefixRow(db, self._op_stack)
        self.db_state = DBStatePrefixRow(db, self._op_stack)
        self.support_amount = SupportAmountPrefixRow(db, self._op_stack)
        self.block_txs = BlockTxsPrefixRow(db, self._op_stack)
        self.mempool_tx = MempoolTXPrefixRow(db, self._op_stack)
        self.trending_notification = TrendingNotificationPrefixRow(db, self._op_stack)
        self.touched_hashX = TouchedHashXPrefixRow(db, self._op_stack)


def auto_decode_item(key: bytes, value: bytes) -> Union[Tuple[NamedTuple, NamedTuple], Tuple[bytes, bytes]]:
    try:
        return ROW_TYPES[key[:1]].unpack_item(key, value)
    except KeyError:
        return key, value
