from ast_nodes import *

class ReturnException(Exception):
    def __init__(self, value):
        self.value = value

class Environment:
    def __init__(self, enclosing=None):
        self.values = {}
        self.enclosing = enclosing

    def define(self, name, value):
        self.values[name] = value

    def get(self, name):
        if name in self.values:
            return self.values[name]
        if self.enclosing is not None:
            return self.enclosing.get(name)
        raise RuntimeError(f"Undefined variable '{name}'.")

    def assign(self, name, value):
        if name in self.values:
            self.values[name] = value
            return
        if self.enclosing is not None:
            self.enclosing.assign(name, value)
            return
        raise RuntimeError(f"Undefined variable '{name}'.")

class Interpreter:
    def __init__(self):
        self.globals = Environment()
        # Add basic str() function
        self.globals.define("str", lambda args: str(args[0]))
        self.environment = self.globals

    def interpret(self, statements):
        try:
            for stmt in statements:
                self.execute(stmt)
        except RuntimeError as e:
            print(f"Runtime Error: {e}")

    def execute(self, stmt):
        method_name = 'visit_' + type(stmt).__name__
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(stmt)

    def evaluate(self, expr):
        method_name = 'visit_' + type(expr).__name__
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(expr)

    def generic_visit(self, node):
        raise Exception(f'No visit_{type(node).__name__} method for node {node}')

    def visit_Program(self, node):
        for stmt in node.statements:
            self.execute(stmt)

    def visit_BlockStmt(self, node):
        prev_env = self.environment
        self.environment = Environment(enclosing=prev_env)
        try:
            for stmt in node.statements:
                self.execute(stmt)
        finally:
            self.environment = prev_env

    def visit_FunctionDecl(self, node):
        self.environment.define(node.name, node)

    def visit_LetDecl(self, node):
        val = self.evaluate(node.value)
        self.environment.define(node.name, val)

    def visit_IfStatement(self, node):
        cond = self.evaluate(node.condition)
        if cond:
            self.execute(node.then_branch)
        elif node.else_branch:
            self.execute(node.else_branch)

    def visit_WhileStatement(self, node):
        while self.evaluate(node.condition):
            self.execute(node.body)

    def visit_PrintStmt(self, node):
        val = self.evaluate(node.expr)
        print(val)

    def visit_ReturnStmt(self, node):
        val = None
        if node.expr:
            val = self.evaluate(node.expr)
        raise ReturnException(val)

    def visit_ExprStmt(self, node):
        self.evaluate(node.expr)

    def visit_BinOp(self, node):
        left = self.evaluate(node.left)
        right = self.evaluate(node.right)
        
        if node.op == 'PLUS': return left + right
        if node.op == 'MINUS': return left - right
        if node.op == 'MUL': return left * right
        if node.op == 'DIV': return left / right
        if node.op == 'LT': return left < right
        if node.op == 'LTE': return left <= right
        if node.op == 'GT': return left > right
        if node.op == 'GTE': return left >= right
        if node.op == 'EQ': return left == right
        if node.op == 'NEQ': return left != right
        raise RuntimeError(f"Unknown operator {node.op}")

    def visit_Call(self, node):
        callee = self.environment.get(node.callee_name)
        args = [self.evaluate(arg) for arg in node.args]

        if callable(callee):
            # Native Python function like 'str'
            return callee(args)

        if not isinstance(callee, FunctionDecl):
            raise RuntimeError(f"{node.callee_name} is not callable.")

        if len(args) != len(callee.params):
            raise RuntimeError(f"Expected {len(callee.params)} arguments but got {len(args)}.")

        # Create function scope
        func_env = Environment(enclosing=self.globals)
        for i in range(len(callee.params)):
            func_env.define(callee.params[i], args[i])

        prev_env = self.environment
        self.environment = func_env
        try:
            for stmt in callee.body.statements:
                self.execute(stmt)
        except ReturnException as r:
            return r.value
        finally:
            self.environment = prev_env

    def visit_Ident(self, node):
        return self.environment.get(node.name)

    def visit_Literal(self, node):
        return node.value
