from ast_nodes import *

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def current(self):
        return self.tokens[self.pos]

    def consume(self, expected_type=None):
        tok = self.current()
        if expected_type and tok.type != expected_type:
            raise RuntimeError(f"Expected token {expected_type}, got {tok.type}")
        self.pos += 1
        return tok

    def match(self, *types):
        if self.current().type in types:
            self.pos += 1
            return True
        return False

    def parse(self):
        statements = []
        while self.current().type != 'EOF':
            statements.append(self.parse_statement())
        return Program(statements)

    def parse_statement(self):
        if self.match('FN'):
            return self.parse_function_decl()
        elif self.match('LET'):
            return self.parse_let_decl()
        elif self.match('IF'):
            return self.parse_if_stmt()
        elif self.match('WHILE'):
            return self.parse_while_stmt()
        elif self.match('PRINT'):
            expr = self.parse_expression()
            return PrintStmt(expr)
        elif self.match('RETURN'):
            expr = self.parse_expression()
            return ReturnStmt(expr)
        else:
            expr = self.parse_expression()
            return ExprStmt(expr)

    def parse_block(self):
        self.consume('LBRACE')
        statements = []
        while self.current().type not in ('RBRACE', 'EOF'):
            statements.append(self.parse_statement())
        self.consume('RBRACE')
        return BlockStmt(statements)

    def parse_function_decl(self):
        name = self.consume('IDENT').value
        self.consume('LPAREN')
        params = []
        if self.current().type != 'RPAREN':
            params.append(self.consume('IDENT').value)
            while self.match('COMMA'):
                params.append(self.consume('IDENT').value)
        self.consume('RPAREN')
        body = self.parse_block()
        return FunctionDecl(name, params, body)

    def parse_let_decl(self):
        name = self.consume('IDENT').value
        self.consume('ASSIGN')
        value = self.parse_expression()
        return LetDecl(name, value)

    def parse_if_stmt(self):
        condition = self.parse_expression()
        then_branch = self.parse_block()
        else_branch = None
        if self.match('ELSE'):
            if self.match('IF'):
                # Handle else if as a block containing a single if
                else_branch = BlockStmt([self.parse_if_stmt()])
            else:
                else_branch = self.parse_block()
        return IfStatement(condition, then_branch, else_branch)

    def parse_while_stmt(self):
        condition = self.parse_expression()
        body = self.parse_block()
        return WhileStatement(condition, body)

    def parse_expression(self):
        return self.parse_equality()

    def parse_equality(self):
        expr = self.parse_comparison()
        while self.current().type in ('EQ', 'NEQ'):
            op = self.consume().type
            right = self.parse_comparison()
            expr = BinOp(op, expr, right)
        return expr

    def parse_comparison(self):
        expr = self.parse_term()
        while self.current().type in ('LT', 'LTE', 'GT', 'GTE'):
            op = self.consume().type
            right = self.parse_term()
            expr = BinOp(op, expr, right)
        return expr

    def parse_term(self):
        expr = self.parse_factor()
        while self.current().type in ('PLUS', 'MINUS'):
            op = self.consume().type
            right = self.parse_factor()
            expr = BinOp(op, expr, right)
        return expr

    def parse_factor(self):
        expr = self.parse_primary()
        while self.current().type in ('MUL', 'DIV'):
            op = self.consume().type
            right = self.parse_primary()
            expr = BinOp(op, expr, right)
        return expr

    def parse_primary(self):
        if self.match('INT'):
            return Literal(self.tokens[self.pos-1].value)
        elif self.match('STRING'):
            return Literal(self.tokens[self.pos-1].value)
        elif self.match('IDENT'):
            name = self.tokens[self.pos-1].value
            if self.match('LPAREN'):
                args = []
                if self.current().type != 'RPAREN':
                    args.append(self.parse_expression())
                    while self.match('COMMA'):
                        args.append(self.parse_expression())
                self.consume('RPAREN')
                return Call(name, args)
            return Ident(name)
        elif self.match('LPAREN'):
            expr = self.parse_expression()
            self.consume('RPAREN')
            return expr
        else:
            raise RuntimeError(f"Unexpected token in expression: {self.current()}")
