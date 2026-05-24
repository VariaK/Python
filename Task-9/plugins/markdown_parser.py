from core.plugin_base import PluginBase

class MarkdownParserPlugin(PluginBase):
    @property
    def name(self): return "markdown-parser"
    @property
    def version(self): return "2.1.0"
    @property
    def plugin_type(self): return "built-in"
    def activate(self): return "registered: .md -> HTML converter"
    def deactivate(self): pass
