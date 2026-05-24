from dataclasses import dataclass
from typing import List, Any

class Node: pass

@dataclass
class Program(Node):
    statements: List[Node]

@dataclass
class BlockStmt(Node):
    statements: List[Node]

@dataclass
class FunctionDecl(Node):
    name: str
    params: List[str]
    body: BlockStmt

@dataclass
class LetDecl(Node):
    name: str
    value: Node

@dataclass
class IfStatement(Node):
    condition: Node
    then_branch: BlockStmt
    else_branch: BlockStmt = None

@dataclass
class WhileStatement(Node):
    condition: Node
    body: BlockStmt

@dataclass
class PrintStmt(Node):
    expr: Node

@dataclass
class ReturnStmt(Node):
    expr: Node

@dataclass
class ExprStmt(Node):
    expr: Node

@dataclass
class BinOp(Node):
    op: str
    left: Node
    right: Node

@dataclass
class Call(Node):
    callee_name: str
    args: List[Node]

@dataclass
class Ident(Node):
    name: str

@dataclass
class Literal(Node):
    value: Any
