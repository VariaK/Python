# MiniLang Interpreter

A miniature programming language implementation in Python featuring a lexer, a recursive descent parser, and an AST-walking interpreter.

## Architecture

The project is broken into several modular components:
1. **`lexer.py`**: A regex-based lexer that breaks down a source string into a stream of tokens, distinguishing keywords, identifiers, strings, integers, and operators.
2. **`ast_nodes.py`**: Contains simple `dataclass` nodes representing our Abstract Syntax Tree.
3. **`miniparser.py`**: A hand-written recursive-descent parser that consumes tokens and assembles them into AST nodes according to standard operator precedence rules.
4. **`interpreter.py`**: Implements the Visitor pattern to traverse the AST. Uses a linked `Environment` chain to manage variable scope, variable assignments, and closures.
5. **`ast_printer.py`**: Formats the resulting AST in a user-friendly hierarchy that demonstrates abbreviation to prevent unbounded logging.
6. **`demo.py`**: Provides the end-to-end execution of a sample Fibonacci script.

## Core Language Features

* **Variables**: Local variables, closures, and assignments (`let result = ...`).
* **Arithmetic & Conditions**: Operators like `+`, `-`, `<`, `<=`, etc.
* **Control Flow**: Block-based `if` and `while` loop statements.
* **Functions & Recursion**: True local scopes via `Environment` chaining support recursive function resolution.
* **Interoperability**: Simple native bindings (like `str` and `print`).

## Running the Demo

Execute the demo script:
```bash
python demo.py
```
This will compile and execute the recursive `fibonacci` script and print out the token stream, the AST layout, and the final interpretation result.
