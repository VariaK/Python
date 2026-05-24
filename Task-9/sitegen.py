import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from core.manager import PluginManager

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=== Application Startup ===")
    args = sys.argv[1:]
    if not args:
        args = ["build", "--theme", "dark-mode"]
    cmd = "sitegen " + " ".join(args)
    print(f"$ {cmd}\n")
    
    manager = PluginManager(plugins_dir="./plugins")
    manager.discover_plugins()
    manager.resolve_dependencies()
    manager.activate_all()
    
    print("\n[CORE] Building site...")
    print("       Processed 24 pages | Theme: dark-mode | RSS: feed.xml generated")
    print("       Images optimized: 18 files, saved 4.2 MB")
    print("[CORE] Build complete -> ./dist/ (0.87s)")

if __name__ == "__main__":
    main()
