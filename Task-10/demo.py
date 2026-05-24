import asyncio
import time
import sys
from blockchain import Wallet, Transaction, Block
from node import Node

async def mine_with_output(node, node_name):
    print(f"\n=== Mining ===")
    
    reward_tx = Transaction("SYSTEM", node.wallet.address, node.blockchain.mining_reward)
    txs = node.mempool + [reward_tx]
    
    idx = node.blockchain.get_latest_block().index + 1
    prev_hash = node.blockchain.get_latest_block().hash
    print(f"[{node_name}] Mining block #{idx} ({len(txs)} transactions in mempool)...")
    print(f"         Difficulty: {node.blockchain.difficulty} (hash must start with \"{'0'*node.blockchain.difficulty}\")")
    
    block = Block(idx, prev_hash, txs)
    
    start_time = time.time()
    target = "0" * node.blockchain.difficulty
    
    # Print nonce 0 and 1 explicitly
    block.nonce = 0
    block.hash = block.calculate_hash()
    print(f"         Nonce: 0      -> hash: {block.hash[:6]}...     MISS")
    
    block.nonce = 1
    block.hash = block.calculate_hash()
    print(f"         Nonce: 1      -> hash: {block.hash[:6]}...     MISS")
    print("         ...")
    
    while not block.hash.startswith(target):
        block.nonce += 1
        block.hash = block.calculate_hash()
        
    end_time = time.time()
    
    print(f"         Nonce: {block.nonce:,} -> hash: {block.hash[:10]}... FOUND!")
    
    elapsed = end_time - start_time
    print(f"\n[{node_name}] Block #{idx} mined in {elapsed:.2f}s")
    print(f"         Hash:        {block.hash[:16]}...")
    print(f"         Prev Hash:   {block.previous_hash[:16]}...")
    print(f"         Merkle Root: {block.merkle_root[:6]}...")
    print(f"         Transactions: {len(txs)}")
    print(f"         Miner Reward: {node.blockchain.mining_reward:.1f} coin -> {node.wallet.address}")
    
    node.blockchain.add_block(block)
    node.mempool = []
    
    return block

class MockWallet(Wallet):
    def __init__(self, mock_address):
        super().__init__()
        self._mock_addr = mock_address
    @property
    def address(self):
        return self._mock_addr

async def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=== Node Startup (3 nodes) ===")
    
    w1 = MockWallet("0xa3f8...c1d2")
    w2 = MockWallet("0xb7d4...e5f6")
    w3 = MockWallet("0xc9e2...a7b8")

    pubkey_to_addr = {
        w1.public_key_hex: w1.address,
        w2.public_key_hex: w2.address,
        w3.public_key_hex: w3.address,
    }

    initial_balances = {
        w1.address: 10.0,
        w2.address: 10.0,
        w3.address: 4.0
    }
    
    node1 = Node("NODE-1", 5001, w1, initial_balances)
    node2 = Node("NODE-2", 5002, w2, initial_balances)
    node3 = Node("NODE-3", 5003, w3, initial_balances)
    
    await node1.start()
    await node2.start()
    await node3.start()
    
    node1.connect_peer(5002)
    node1.connect_peer(5003)
    node2.connect_peer(5001)
    node2.connect_peer(5003)
    node3.connect_peer(5001)
    node3.connect_peer(5002)

    await asyncio.sleep(0.5)

    print("\n=== Transaction ===")
    tx = Transaction(w1.public_key_hex, w2.address, 2.5)
    tx.sign(w1)
    
    print(f"[NODE-1] Creating transaction:")
    print(f"         From:   {w1.address}")
    print(f"         To:     {w2.address}")
    print(f"         Amount: 2.5 coins")
    is_valid = tx.is_valid()
    print(f"         Signature: {tx.signature[:10]}...  {'Valid' if is_valid else 'Invalid'}")
    
    node2.mempool.append(tx)
    
    mined_block = await mine_with_output(node2, "NODE-2")
    
    print("\n=== Propagation ===")
    await node2.broadcast_block(mined_block)
    
    await asyncio.sleep(0.5)
    
    print("\n=== Wallet Balances ===")
    for w in [w1, w2, w3]:
        bal = node1.blockchain.get_balance(w.address, pubkey_to_addr)
        if w.address == w2.address:
            print(f"{w.address}: {bal:.1f} coins (includes mining rewards)")
        else:
            print(f"{w.address}:  {bal:.1f} coins")
            
    # Cleanup servers
    node1.server.close()
    node2.server.close()
    node3.server.close()
    await node1.server.wait_closed()
    await node2.server.wait_closed()
    await node3.server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
