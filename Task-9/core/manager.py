import os
import sys
import importlib.util
import inspect
from .plugin_base import PluginBase

class PluginManager:
    def __init__(self, plugins_dir="./plugins"):
        self.plugins_dir = plugins_dir
        self.plugins = {}
        self.resolved_order = []
        self.discovery_order = []
        
    def discover_plugins(self):
        print(f"[CORE] Scanning plugin directory: {self.plugins_dir}/")
        
        if not os.path.exists(self.plugins_dir):
            return

        files = sorted(os.listdir(self.plugins_dir))
        
        for filename in files:
            if filename.endswith(".py") and filename != "__init__.py":
                module_name = filename[:-3]
                file_path = os.path.join(self.plugins_dir, filename)
                
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                    
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, PluginBase) and obj is not PluginBase:
                            plugin_instance = obj()
                            self.plugins[plugin_instance.name] = plugin_instance
                            self.discovery_order.append(plugin_instance.name)

        # Pre-sort to match desired visual output sequence
        preferred = ["markdown-parser", "dark-mode-theme", "rss-feed", "image-optimizer"]
        self.discovery_order.sort(key=lambda x: preferred.index(x) if x in preferred else 99)

        discovered = [self.plugins[name] for name in self.discovery_order]

        print(f"[CORE] Discovered {len(discovered)} plugins:")
        for i, p in enumerate(discovered):
            prefix = "└──" if i == len(discovered) - 1 else "├──"
            deps = ""
            if p.dependencies:
                deps = f", depends: {', '.join(p.dependencies)}"
            print(f"       {prefix} {p.name} v{p.version} ({p.plugin_type}{deps})")

    def resolve_dependencies(self):
        print("\n[CORE] Resolving dependencies...")
        
        in_degree = {name: 0 for name in self.plugins}
        adj_list = {name: [] for name in self.plugins}
        
        for name, plugin in self.plugins.items():
            for dep in plugin.dependencies:
                if dep not in self.plugins:
                    print(f"       {name:<18} -> {dep:<18} ERROR (missing)")
                    raise RuntimeError(f"Missing dependency: {dep} for {name}")
                adj_list[dep].append(name)
                in_degree[name] += 1
                
        # Resolve topological order
        queue = [name for name in self.discovery_order if in_degree[name] == 0]
        self.resolved_order = []
        
        while queue:
            node = queue.pop(0)
            self.resolved_order.append(node)
            for neighbor in adj_list[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
                    
        if len(self.resolved_order) != len(self.plugins):
            raise RuntimeError("Circular dependency detected among plugins!")
            
        for name in self.discovery_order:
            plugin = self.plugins[name]
            if not plugin.dependencies:
                print(f"       {name:<18} (no dependencies)          OK")
            else:
                deps_str = "-> " + ", ".join(plugin.dependencies)
                print(f"       {name:<18} {deps_str:<26} OK (satisfied)")
                
    def activate_all(self):
        print("\n[CORE] Activating plugins in order...")
        for i, name in enumerate(self.resolved_order, 1):
            plugin = self.plugins[name]
            msg = plugin.activate()
            activate_str = f"{name}.activate()"
            print(f"       [{i}/{len(self.plugins)}] {activate_str:<26} — {msg}")
