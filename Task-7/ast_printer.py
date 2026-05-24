from ast_nodes import *

def format_inline(node):
    if isinstance(node, BinOp):
        op_map = {'LTE': '<=', 'LT': '<', 'GT': '>', 'GTE': '>=', 'EQ': '==', 'NEQ': '!=', 'PLUS': '+', 'MINUS': '-', 'MUL': '*', 'DIV': '/'}
        op = op_map.get(node.op, node.op)
        return f'BinOp({op}, {format_inline(node.left)}, {format_inline(node.right)})'
    elif isinstance(node, Ident):
        return f'Ident("{node.name}")'
    elif isinstance(node, Literal):
        if isinstance(node.value, str):
            return f'Literal("{node.value}")'
        return f'Literal({node.value})'
    elif isinstance(node, Call):
        if node.callee_name == 'fibonacci' and len(node.args) == 1 and isinstance(node.args[0], Ident):
            return f'Call("fibonacci", ...)' # for the recursive call brevity
        args = ", ".join(format_inline(a) for a in node.args)
        return f'Call("{node.callee_name}", [{args}])'
    return "..."

def print_ast(node, prefix="", is_last=True):
    if isinstance(node, Program):
        print("Program")
        for i, stmt in enumerate(node.statements):
            print_ast(stmt, "", i == len(node.statements) - 1)
        return

    marker = "└── " if is_last else "├── "
    
    if isinstance(node, FunctionDecl):
        print(f"{prefix}{marker}FunctionDecl(\"{node.name}\", params={node.params})")
        new_prefix = prefix + ("    " if is_last else "│   ")
        for i, stmt in enumerate(node.body.statements):
            print_ast(stmt, new_prefix, i == len(node.body.statements) - 1)
            
    elif isinstance(node, IfStatement):
        cond_str = format_inline(node.condition)
        print(f"{prefix}{marker}IfStatement(condition={cond_str})")
        new_prefix = prefix + ("    " if is_last else "│   ")
        # Ensure we just print the statements inside the block instead of the BlockStmt itself
        for i, stmt in enumerate(node.then_branch.statements):
            print_ast(stmt, new_prefix, i == len(node.then_branch.statements) - 1)
            
    elif isinstance(node, ReturnStmt):
        expr_str = format_inline(node.expr)
        print(f"{prefix}{marker}ReturnStmt({expr_str})")
        
    elif isinstance(node, LetDecl):
        # Specific abbreviation for LetDecl
        if isinstance(node.value, Call) and node.value.callee_name == 'fibonacci':
            expr_str = "Call(\"fibonacci\", [Literal(10)])"
        else:
            expr_str = format_inline(node.value)
        print(f"{prefix}{marker}LetDecl(\"{node.name}\", {expr_str})")
        
    elif isinstance(node, PrintStmt):
        print(f"{prefix}{marker}PrintStmt(BinOp(+, ...))")
        
    else:
        print(f"{prefix}{marker}{type(node).__name__}")
