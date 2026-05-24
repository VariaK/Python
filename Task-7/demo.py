import sys
from lexer import tokenize
from miniparser import Parser
from interpreter import Interpreter
from ast_printer import print_ast

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    source_code = """
fn fibonacci(n) {
    if n <= 1 { return n }
    return fibonacci(n - 1) + fibonacci(n - 2)
}
let result = fibonacci(10)
print("Fibonacci(10) = " + str(result))
"""
    
    print("=== Source Code (MiniLang) ===")
    print(source_code.strip())
    print()

    tokens = tokenize(source_code)
    print("=== Lexer Output ===")
    print(tokens)
    print()

    parser = Parser(tokens)
    ast = parser.parse()
    
    print("=== AST (abbreviated) ===")
    print_ast(ast)
    print()

    print("=== Interpreter Output ===")
    interpreter = Interpreter()
    interpreter.interpret(ast.statements)

if __name__ == "__main__":
    main()
