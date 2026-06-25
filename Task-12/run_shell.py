import os
import sys

# Ensure we can import graphdb
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from graphdb.shell import Shell

def main():
    shell = Shell()
    
    # We can pass batch_commands for automated verification
    if len(sys.argv) > 1 and sys.argv[1] == '--verify':
        commands = [
            'CREATE NODE (alice:Person {name: "Alice", age: 30, city: "Austin"})',
            'CREATE NODE (bob:Person {name: "Bob", age: 28, city: "Dallas"})',
            'CREATE NODE (acme:Company {name: "Acme Corp", industry: "Tech"})',
            'CREATE EDGE (alice)-[:FRIENDS_WITH {since: 2021}]->(bob)',
            'CREATE EDGE (bob)-[:WORKS_AT {role: "Engineer"}]->(acme)',
            'MATCH (p:Person)-[:FRIENDS_WITH]->()-[:WORKS_AT]->(c:Company) WHERE c.name = "Acme Corp" RETURN p.name, c.name',
            'SHORTEST_PATH (alice)-[*1..4]->(acme)',
            'STATS'
        ]
        
        # Clean the graph DB if it exists for the test
        if os.path.exists("graph.wal"):
            os.remove("graph.wal")
            
        shell.db.wal.close()
        shell = Shell() # re-init empty
        
        shell.run(batch_commands=commands)
    else:
        shell.run()

if __name__ == "__main__":
    main()
