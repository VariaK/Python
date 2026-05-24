import asyncio
import json
from blockchain import Blockchain, Transaction, Block

class Node:
    def __init__(self, name, port, wallet, initial_balances):
        self.name = name
        self.port = port
        self.wallet = wallet
        self.blockchain = Blockchain(initial_balances)
        self.mempool = []
        self.peers = []
        self.server = None

    async def start(self):
        self.server = await asyncio.start_server(self.handle_client, '127.0.0.1', self.port)
        print(f"[{self.name}] Listening on port {self.port} | Wallet: {self.wallet.address}")
        asyncio.create_task(self.server.serve_forever())

    def connect_peer(self, port):
        self.peers.append(port)

    async def handle_client(self, reader, writer):
        data = await reader.read(4096)
        if not data:
            writer.close()
            return
        try:
            message = json.loads(data.decode())
            if message["type"] == "BLOCK":
                block = Block.from_dict(message["block"])
                if block.index == self.blockchain.get_latest_block().index + 1:
                    if block.hash.startswith("0" * self.blockchain.difficulty):
                        self.blockchain.add_block(block)
                        print(f"[{self.name}] Received block #{block.index} — validating... Accepted (chain height: {block.index})")
        except Exception as e:
            print(f"Exception in handle_client: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def broadcast_block(self, block):
        print(f"[{self.name}] Broadcasting block #{block.index} to peers...")
        for peer_port in self.peers:
            try:
                reader, writer = await asyncio.open_connection('127.0.0.1', peer_port)
                payload = json.dumps({"type": "BLOCK", "block": block.to_dict()})
                writer.write(payload.encode())
                await writer.drain()
                writer.close()
                await writer.wait_closed()
            except ConnectionRefusedError:
                pass
