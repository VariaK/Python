import re
import json

class ParseError(Exception):
    pass

class Parser:
    def parse(self, query):
        query = query.strip()
        if not query:
            return None
            
        if query.upper() == "STATS":
            return {"type": "STATS"}
            
        if query.upper().startswith("CREATE NODE"):
            return self._parse_create_node(query)
            
        if query.upper().startswith("CREATE EDGE"):
            return self._parse_create_edge(query)
            
        if query.upper().startswith("MATCH"):
            return self._parse_match(query)
            
        if query.upper().startswith("SHORTEST_PATH"):
            return self._parse_shortest_path(query)
            
        raise ParseError(f"Unknown command: {query}")
        
    def _parse_create_node(self, query):
        m = re.match(r'(?i)CREATE\s+NODE\s*\((.*?)\)', query)
        if not m:
            raise ParseError("Invalid CREATE NODE syntax")
            
        content = m.group(1).strip()
        
        alias, label, props_str = None, None, "{}"
        
        if '{' in content:
            idx = content.index('{')
            props_str = content[idx:].strip()
            content = content[:idx].strip()
            
        if ':' in content:
            alias, label = [x.strip() for x in content.split(':')]
        else:
            raise ParseError("Node must have alias and label in CREATE NODE, e.g. alias:Label")
            
        props = self._parse_props(props_str)
        
        return {
            "type": "CREATE_NODE",
            "alias": alias,
            "label": label,
            "props": props
        }
        
    def _parse_props(self, props_str):
        if props_str == "{}":
            return {}
        # Convert unquoted keys to valid JSON
        props_str = re.sub(r'([{,]\s*)([a-zA-Z_]\w*)(\s*:)', r'\1"\2"\3', props_str)
        try:
            return json.loads(props_str)
        except json.JSONDecodeError as e:
            raise ParseError(f"Invalid properties format: {e}")
            
    def _parse_create_edge(self, query):
        m = re.match(r'(?i)CREATE\s+EDGE\s*\((.*?)\)\s*-\[\s*:(.*?)\s*\]->\s*\((.*?)\)', query)
        if not m:
            raise ParseError("Invalid CREATE EDGE syntax")
            
        from_alias = m.group(1).strip()
        edge_content = m.group(2).strip()
        to_alias = m.group(3).strip()
        
        type_ = edge_content
        props_str = "{}"
        if '{' in edge_content:
            idx = edge_content.index('{')
            props_str = edge_content[idx:].strip()
            type_ = edge_content[:idx].strip()
            
        props = self._parse_props(props_str)
        
        return {
            "type": "CREATE_EDGE",
            "from_alias": from_alias,
            "to_alias": to_alias,
            "edge_type": type_,
            "props": props
        }
        
    def _parse_shortest_path(self, query):
        m = re.match(r'(?i)SHORTEST_PATH\s*\((.*?)\)\s*-\[\s*\*(.*?)\s*\]->\s*\((.*?)\)', query)
        if not m:
            raise ParseError("Invalid SHORTEST_PATH syntax")
            
        from_alias = m.group(1).strip()
        range_str = m.group(2).strip()
        to_alias = m.group(3).strip()
        
        min_hops, max_hops = 1, 4
        if '..' in range_str:
            parts = range_str.split('..')
            if parts[0]: min_hops = int(parts[0])
            if parts[1]: max_hops = int(parts[1])
            
        return {
            "type": "SHORTEST_PATH",
            "from_alias": from_alias,
            "to_alias": to_alias,
            "min_hops": min_hops,
            "max_hops": max_hops
        }
        
    def _parse_match(self, query):
        query = re.sub(r'\s+', ' ', query)
        
        match_pattern = r'(?i)MATCH\s+(.*?)(?:\s+WHERE\s+(.*?))?(?:\s+RETURN\s+(.*))?$'
        m = re.match(match_pattern, query)
        if not m:
            raise ParseError("Invalid MATCH syntax")
            
        path_str = m.group(1).strip()
        where_str = m.group(2)
        return_str = m.group(3)
        
        tokens = re.findall(r'\(.*?\)|-\[.*?\]->|->', path_str)
        
        parsed_path = []
        for t in tokens:
            if t.startswith('('):
                content = t[1:-1].strip()
                alias, label = None, None
                if ':' in content:
                    alias, label = [x.strip() for x in content.split(':')]
                else:
                    alias = content if content else None
                parsed_path.append({"kind": "node", "alias": alias, "label": label})
            elif t.startswith('-['):
                content = t[2:-3].strip()
                type_ = None
                if content.startswith(':'):
                    type_ = content[1:].strip()
                parsed_path.append({"kind": "edge", "type": type_})
            elif t == '->':
                parsed_path.append({"kind": "edge", "type": None})
                
        filters = []
        if where_str:
            conds = re.split(r'(?i)\s+AND\s+', where_str.strip())
            for cond in conds:
                fm = re.match(r'(.*?)\.(.*?)\s*=\s*(.*)', cond.strip())
                if fm:
                    alias = fm.group(1).strip()
                    prop = fm.group(2).strip()
                    val_str = fm.group(3).strip()
                    try:
                        val = json.loads(val_str)
                    except:
                        val = val_str
                    filters.append({"alias": alias, "prop": prop, "val": val})
                    
        returns = []
        if return_str:
            ret_parts = return_str.split(',')
            for p in ret_parts:
                p = p.strip()
                if '.' in p:
                    alias, prop = p.split('.')
                    returns.append({"alias": alias, "prop": prop})
                else:
                    returns.append({"alias": p, "prop": None})
                    
        return {
            "type": "MATCH",
            "path": parsed_path,
            "filters": filters,
            "returns": returns
        }
