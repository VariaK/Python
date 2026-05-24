import hashlib
import json
import time
import binascii
from ecdsa import SigningKey, SECP256k1, VerifyingKey, BadSignatureError

def build_merkle_root(tx_hashes):
    if not tx_hashes:
        return hashlib.sha256(b"").hexdigest()
    if len(tx_hashes) == 1:
        return tx_hashes[0]
    
    new_level = []
    for i in range(0, len(tx_hashes), 2):
        left = tx_hashes[i]
        right = tx_hashes[i+1] if i+1 < len(tx_hashes) else left
        combined = left + right
        new_level.append(hashlib.sha256(combined.encode()).hexdigest())
    return build_merkle_root(new_level)

class Wallet:
    def __init__(self, private_key_hex=None):
        if private_key_hex:
            self.private_key = SigningKey.from_string(binascii.unhexlify(private_key_hex), curve=SECP256k1)
        else:
            self.private_key = SigningKey.generate(curve=SECP256k1)
        self.public_key = self.private_key.get_verifying_key()
        
    @property
    def public_key_hex(self):
        return binascii.hexlify(self.public_key.to_string()).decode('utf-8')

    @property
    def address(self):
        sha = hashlib.sha256(self.public_key.to_string()).digest()
        hex_addr = binascii.hexlify(sha).decode('utf-8')
        return "0x" + hex_addr[:4] + "..." + hex_addr[-4:]

    def sign(self, data: str):
        signature = self.private_key.sign(data.encode('utf-8'))
        return binascii.hexlify(signature).decode('utf-8')

    @staticmethod
    def verify(public_key_hex, signature_hex, data: str):
        try:
            vk = VerifyingKey.from_string(binascii.unhexlify(public_key_hex), curve=SECP256k1)
            return vk.verify(binascii.unhexlify(signature_hex), data.encode('utf-8'))
        except (BadSignatureError, binascii.Error, ValueError):
            return False

class Transaction:
    def __init__(self, sender_pub, receiver_addr, amount, signature="", hash=""):
        self.sender_pub = sender_pub
        self.receiver_addr = receiver_addr
        self.amount = float(amount)
        self.signature = signature
        self.hash = hash or self.calculate_hash()

    def to_dict(self, include_sig=False):
        d = {
            "sender_pub": self.sender_pub,
            "receiver_addr": self.receiver_addr,
            "amount": self.amount
        }
        if include_sig:
            d["signature"] = self.signature
            d["hash"] = self.hash
        return d

    def calculate_hash(self):
        data = json.dumps(self.to_dict(include_sig=False), sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()

    def sign(self, wallet):
        self.signature = wallet.sign(self.hash)

    def is_valid(self):
        if self.sender_pub == "SYSTEM": 
            return True
        return Wallet.verify(self.sender_pub, self.signature, self.hash)

class Block:
    def __init__(self, index, previous_hash, transactions, timestamp=None, nonce=0, hash=""):
        self.index = index
        self.timestamp = timestamp or time.time()
        self.previous_hash = previous_hash
        self.transactions = transactions
        self.nonce = nonce
        self.merkle_root = self.calculate_merkle_root()
        self.hash = hash or self.calculate_hash()

    def calculate_merkle_root(self):
        hashes = [tx.hash for tx in self.transactions]
        return build_merkle_root(hashes)

    def calculate_hash(self):
        data = f"{self.index}{self.timestamp}{self.previous_hash}{self.merkle_root}{self.nonce}"
        return hashlib.sha256(data.encode()).hexdigest()

    def to_dict(self):
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "transactions": [tx.to_dict(include_sig=True) for tx in self.transactions],
            "nonce": self.nonce,
            "merkle_root": self.merkle_root,
            "hash": self.hash
        }

    @classmethod
    def from_dict(cls, data):
        txs = [Transaction(**tx_data) for tx_data in data["transactions"]]
        return cls(data["index"], data["previous_hash"], txs, data["timestamp"], data["nonce"], data["hash"])

class Blockchain:
    def __init__(self, initial_balances=None):
        self.chain = []
        self.difficulty = 4
        self.mining_reward = 1.0
        
        # Genesis block
        genesis_txs = []
        if initial_balances:
            for addr, amount in initial_balances.items():
                genesis_txs.append(Transaction("SYSTEM", addr, amount))
        
        genesis_block = Block(0, "0", genesis_txs, timestamp=1600000000)
        # Mine genesis silently
        target = "0" * self.difficulty
        while not genesis_block.hash.startswith(target):
            genesis_block.nonce += 1
            genesis_block.hash = genesis_block.calculate_hash()
        self.chain.append(genesis_block)
        
        # Fake history up to block 6
        for i in range(1, 7):
            b = Block(i, self.chain[-1].hash, [], timestamp=1600000000+i)
            while not b.hash.startswith(target):
                b.nonce += 1
                b.hash = b.calculate_hash()
            self.chain.append(b)

    def get_latest_block(self):
        return self.chain[-1]

    def add_block(self, block):
        self.chain.append(block)

    def get_balance(self, address, pubkey_to_addr):
        balance = 0.0
        for block in self.chain:
            for tx in block.transactions:
                if tx.sender_pub != "SYSTEM":
                    # use the lookup mapping to get address
                    sender_addr = pubkey_to_addr.get(tx.sender_pub)
                    if sender_addr == address:
                        balance -= tx.amount
                if tx.receiver_addr == address:
                    balance += tx.amount
        return balance
