import ast
import linecache

class AssertionVisitor(ast.NodeVisitor):
    def __init__(self):
        self.left = None
        self.right = None
        self.op = None

    def visit_Compare(self, node):
        if len(node.ops) == 1 and len(node.comparators) == 1:
            self.left = node.left
            self.op = type(node.ops[0]).__name__
            self.right = node.comparators[0]
        self.generic_visit(node)

def format_assertion_error(exc_value, tb):
    """
    Introspect an AssertionError to generate a rich diff showing expected vs actual values.
    """
    # Find the deepest frame in the traceback
    while tb.tb_next is not None:
        tb = tb.tb_next
    
    frame = tb.tb_frame
    lineno = tb.tb_lineno
    filename = frame.f_code.co_filename
    
    # Get the source line of the assertion
    line = linecache.getline(filename, lineno).strip()
    
    if not line.startswith("assert "):
        msg = str(exc_value) or "Assertion failed"
        return f"AssertionError: {msg}\nat {filename}:{lineno}"
        
    try:
        # Parse the line into an AST
        tree = ast.parse(line)
        assert_node = tree.body[0]
        
        if not isinstance(assert_node, ast.Assert):
            raise ValueError("Not an assert statement")
            
        test_expr = assert_node.test
        if not isinstance(test_expr, ast.Compare):
            raise ValueError("Not a comparison")
            
        visitor = AssertionVisitor()
        visitor.visit(test_expr)
        
        if not visitor.left or not visitor.right:
            raise ValueError("Unsupported comparison")
            
        # Evaluate left and right sides
        left_val = eval(compile(ast.Expression(visitor.left), filename, 'eval'), frame.f_globals, frame.f_locals)
        right_val = eval(compile(ast.Expression(visitor.right), filename, 'eval'), frame.f_globals, frame.f_locals)
        
        left_col = visitor.left.col_offset
        right_col = visitor.right.col_offset
        
        msg = f"AssertionError: Expected {right_val}, got {left_val}\n"
        msg += f"|  {line}\n"
        
        # Build pointer line
        ptr_line = [" "] * (max(right_col, left_col) + 10)
        ptr_line[left_col] = "|"
        ptr_line[right_col] = "|"
        
        # Build value line
        val_line = [" "] * (max(right_col, left_col) + 50)
        left_str = repr(left_val)
        right_str = repr(right_val)
        
        for i, c in enumerate(left_str):
            if left_col + i < len(val_line):
                val_line[left_col + i] = c
                
        for i, c in enumerate(right_str):
            if right_col + i < len(val_line):
                # Don't overwrite if left value is long
                if val_line[right_col + i] == " ":
                    val_line[right_col + i] = c
                else:
                    # Append it if they overlap
                    val_line.append(c)
                
        msg += f"|  {''.join(ptr_line).rstrip()}\n"
        msg += f"|  {''.join(val_line).rstrip()}\n"
        msg += f"at {filename}:{lineno}"
        
        return msg
        
    except Exception as e:
        # Fallback if introspection fails
        msg = str(exc_value) or "Assertion failed"
        return f"AssertionError: {msg}\nat {filename}:{lineno}"
