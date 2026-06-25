import sys
from .db import GraphDB
from .parser import Parser, ParseError
from .executor import Executor

class Shell:
    def __init__(self):
        self.db = GraphDB()
        self.parser = Parser()
        self.executor = Executor(self.db)
        self.aliases = {}
        
    def print_table(self, table_data, duration_ms):
        headers = table_data['headers']
        rows = table_data['rows']
        
        widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(cell))
                
        sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
        
        print(sep)
        header_str = "|" + "|".join(f" {h:<{w}} " for h, w in zip(headers, widths)) + "|"
        print(header_str)
        print(sep)
        
        for row in rows:
            row_str = "|" + "|".join(f" {cell:<{w}} " for cell, w in zip(row, widths)) + "|"
            print(row_str)
            
        print(sep)
        print(f"{table_data['count']} row returned (traversal: {table_data['nodes_traversed']} nodes, {table_data['edges_traversed']} edges) in {duration_ms:.1f}ms\n")

    def run(self, batch_commands=None):
        print("=== Graph DB Shell ===")
        
        if batch_commands is not None:
            # Batch mode execution
            for cmd in batch_commands:
                cmd = cmd.strip()
                if not cmd:
                    continue
                # For visual formatting in batch output
                lines = cmd.split('\n')
                print(f"graphdb> {lines[0]}")
                for line in lines[1:]:
                    print(f"         {line.strip()}")
                self.execute_command(cmd)
            return
            
        # Interactive REPL
        buffer = []
        while True:
            try:
                prompt = "graphdb> " if not buffer else "         "
                line = input(prompt)
                
                # Execute on empty line or if we successfully parse it
                if not line.strip():
                    if buffer:
                        cmd = " ".join(buffer).strip()
                        self.execute_command(cmd)
                        buffer = []
                    continue
                    
                buffer.append(line)
                
                # Attempt to parse and execute immediately if it's a valid complete command
                cmd = " ".join(buffer).strip()
                try:
                    ast = self.parser.parse(cmd)
                    # If we parsed it successfully, execute it.
                    if ast:
                        self.execute_command(cmd)
                        buffer = []
                except ParseError:
                    # Might be incomplete, keep buffering
                    pass
                    
            except EOFError:
                break
            except KeyboardInterrupt:
                print("\nKeyboardInterrupt")
                break
                
    def execute_command(self, cmd):
        if cmd.lower() in ("exit", "quit"):
            sys.exit(0)
            
        try:
            ast = self.parser.parse(cmd)
            if not ast:
                return
            res = self.executor.execute(ast, self.aliases)
            
            if res:
                if 'error' in res:
                    print(f"Error: {res['error']}\n")
                elif 'msg' in res:
                    print(f"{res['msg']}\n")
                elif 'table' in res:
                    duration_ms = res.get('time', 0) * 1000
                    self.print_table(res['table'], duration_ms)
        except ParseError as e:
            print(f"Parse Error: {e}\n")
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Execution Error: {e}\n")
