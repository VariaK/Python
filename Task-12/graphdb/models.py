from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class Node:
    id: int
    label: str
    props: Dict[str, Any] = field(default_factory=dict)
    
    def __str__(self):
        return f"{self.label}#{self.id}"

@dataclass
class Edge:
    id: int
    from_id: int
    to_id: int
    type: str
    props: Dict[str, Any] = field(default_factory=dict)
    
    def __str__(self):
        return f"{self.type}#{self.id} ({self.from_id}->{self.to_id})"
