import re

class Token:
    def __init__(self, type_, value=None):
        self.type = type_
        self.value = value
    
    def __repr__(self):
        if self.value is not None:
            if self.type == 'STRING':
                return f'{self.type}("{self.value}")'
            elif self.type == 'IDENT':
                return f'{self.type}("{self.value}")'
            elif self.type == 'INT':
                return f'{self.type}({self.value})'
            return f'{self.type}({self.value})'
        return self.type

TOKEN_SPEC = [
    ('NUMBER',   r'\d+'),
    ('STRING',   r'"[^"]*"'),
    ('ID',       r'[A-Za-z_][A-Za-z0-9_]*'),
    ('LTE',      r'<='),
    ('GTE',      r'>='),
    ('EQ',       r'=='),
    ('NEQ',      r'!='),
    ('LT',       r'<'),
    ('GT',       r'>'),
    ('ASSIGN',   r'='),
    ('PLUS',     r'\+'),
    ('MINUS',    r'-'),
    ('MUL',      r'\*'),
    ('DIV',      r'/'),
    ('LPAREN',   r'\('),
    ('RPAREN',   r'\)'),
    ('LBRACE',   r'\{'),
    ('RBRACE',   r'\}'),
    ('COMMA',    r','),
    ('WHITESPACE', r'\s+'),
    ('MISMATCH', r'.'),
]

KEYWORDS = {
    'let': 'LET',
    'if': 'IF',
    'else': 'ELSE',
    'while': 'WHILE',
    'fn': 'FN',
    'return': 'RETURN',
    'print': 'PRINT'
}

def tokenize(code):
    tok_regex = '|'.join('(?P<%s>%s)' % pair for pair in TOKEN_SPEC)
    tokens = []
    for mo in re.finditer(tok_regex, code):
        kind = mo.lastgroup
        value = mo.group()
        if kind == 'NUMBER':
            tokens.append(Token('INT', int(value)))
        elif kind == 'STRING':
            tokens.append(Token('STRING', value[1:-1])) # strip quotes
        elif kind == 'ID':
            kind = KEYWORDS.get(value, 'IDENT')
            if kind == 'IDENT':
                tokens.append(Token(kind, value))
            else:
                tokens.append(Token(kind))
        elif kind == 'WHITESPACE':
            continue
        elif kind == 'MISMATCH':
            raise RuntimeError(f'Unexpected character {value!r}')
        else:
            tokens.append(Token(kind))
    tokens.append(Token('EOF'))
    return tokens
