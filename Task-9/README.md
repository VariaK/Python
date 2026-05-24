# Plugin Architecture with Dynamic Loading

A robust Python framework demonstrating a decoupled plugin architecture that dynamically discovers, validates, and loads extensions at runtime without modifying the core application logic.

## Architecture Highlights
- **Dynamic Module Loading**: Leverages `importlib` and `importlib.util` to scan the `./plugins/` directory and execute module definitions on the fly.
- **Abstract Interfaces**: Mandates that every plugin subclasses `core.plugin_base.PluginBase` using Python's `abc.ABC`, ensuring a consistent contract (`activate()`, `deactivate()`, `name`, `dependencies`, etc).
- **Dependency Graph Resolution**: Employs a directed graph topological sort (Kahn's algorithm) to safely resolve interdependent plugins (like `rss-feed` depending on `markdown-parser`) before triggering lifecycle hooks.
- **Graceful Degradation**: Protects against missing dependencies or circular loops via clear `RuntimeError` propagation.

## Demo Flow
Run the entry point application to see the engine discover plugins, check dependencies, and perform an ordered activation:

```bash
python sitegen.py build --theme dark-mode
```

You'll see output closely tracking the mock application startup, verifying each aspect of the system.
