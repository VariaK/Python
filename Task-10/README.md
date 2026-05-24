# Blockchain Prototype

A Python-based mock blockchain system implementing full cryptographic transaction signing, Proof-of-Work (PoW) consensus, and a peer-to-peer gossip networking layer.

## Key Features

1. **Transaction Signing (`wallet.py`)**: 
   - Utilizes `ecdsa` (Elliptic Curve Digital Signature Algorithm) with the SECP256k1 curve (same as Bitcoin).
   - Generates authentic public/private keypairs, hashes messages with SHA-256, and supports full signature verification against a simulated mempool.

2. **Blockchain & Consensus (`blockchain.py`)**:
   - Manages an append-only linked-list architecture of Block objects.
   - Proof-of-Work mining requires hashing until a specified difficulty (number of leading zeros) is met.
   - Embeds a fully-recursive Merkle Tree algorithm to compute the `merkle_root` of all underlying transactions.

3. **P2P Network (`node.py`)**:
   - Implements asynchronous, non-blocking network socket servers using `asyncio.start_server`.
   - Nodes autonomously connect to peers, handle `BLOCK` JSON payloads, perform genesis alignment verification, check hash targets, and append to the valid longest chain.

4. **Demonstration Layer (`demo.py`)**:
   - A single-file script orchestrating three simultaneous `asyncio` nodes listening on respective local ports.
   - Constructs a transaction, broadcasts it to a node for mining, and outputs exact logging artifacts before shutting down the active event loops.

## Execution

Ensure you are inside the `Task-10` directory and run:

```bash
python demo.py
```

This will automatically spin up the nodes, begin the mining challenge, propagate the block across TCP sockets, and yield the ledger balances.
