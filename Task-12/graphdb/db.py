from collections import defaultdict, deque
from .models import Node, Edge
from .wal import WAL

class GraphDB:
    def __init__(self, wal_path="graph.wal"):
        self.wal = WAL(wal_path)
        self.nodes = {}
        self.edges = {}
        self.out_edges = defaultdict(list)
        self.in_edges = defaultdict(list)
        
        # indexes[label][prop_name][prop_val] -> set(node_ids)
        self.indexes = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
        
        self._next_node_id = 1
        self._next_edge_id = 1
        
        self.recover_from_wal()
        
    def recover_from_wal(self):
        """Replay the write-ahead log to reconstruct state."""
        entries = self.wal.read_all()
        for entry in entries:
            op = entry['op']
            data = entry['data']
            if op == 'create_node':
                self._apply_create_node(data['id'], data['label'], data['props'])
                self._next_node_id = max(self._next_node_id, data['id'] + 1)
            elif op == 'create_edge':
                self._apply_create_edge(data['id'], data['from_id'], data['to_id'], data['type'], data['props'])
                self._next_edge_id = max(self._next_edge_id, data['id'] + 1)

    def _apply_create_node(self, node_id, label, props):
        node = Node(id=node_id, label=label, props=props)
        self.nodes[node_id] = node
        
        # Update indexes
        for k, v in props.items():
            self.indexes[label][k][v].add(node_id)
            
    def _apply_create_edge(self, edge_id, from_id, to_id, type_, props):
        edge = Edge(id=edge_id, from_id=from_id, to_id=to_id, type=type_, props=props)
        self.edges[edge_id] = edge
        self.out_edges[from_id].append(edge)
        self.in_edges[to_id].append(edge)

    def create_node(self, label, props):
        node_id = self._next_node_id
        self._next_node_id += 1
        
        self.wal.log("create_node", {
            "id": node_id,
            "label": label,
            "props": props
        })
        
        self._apply_create_node(node_id, label, props)
        return self.nodes[node_id]

    def create_edge(self, from_id, to_id, type_, props=None):
        if props is None:
            props = {}
            
        if from_id not in self.nodes or to_id not in self.nodes:
            raise ValueError("Both from_id and to_id must exist")
            
        edge_id = self._next_edge_id
        self._next_edge_id += 1
        
        self.wal.log("create_edge", {
            "id": edge_id,
            "from_id": from_id,
            "to_id": to_id,
            "type": type_,
            "props": props
        })
        
        self._apply_create_edge(edge_id, from_id, to_id, type_, props)
        return self.edges[edge_id]

    def shortest_path(self, start_id, end_id, max_hops=4):
        """Find the shortest path using BFS."""
        if start_id not in self.nodes or end_id not in self.nodes:
            return None
            
        if start_id == end_id:
            return []
            
        queue = deque([(start_id, [])])
        visited = {start_id}
        
        while queue:
            curr_id, path = queue.popleft()
            
            if len(path) >= max_hops:
                continue
                
            for edge in self.out_edges[curr_id]:
                next_id = edge.to_id
                if next_id == end_id:
                    return path + [edge]
                    
                if next_id not in visited:
                    visited.add(next_id)
                    queue.append((next_id, path + [edge]))
                    
        return None
