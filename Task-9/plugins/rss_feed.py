from core.plugin_base import PluginBase

class RssFeedPlugin(PluginBase):
    @property
    def name(self): return "rss-feed"
    @property
    def version(self): return "1.0.0"
    @property
    def dependencies(self): return ["markdown-parser"]
    def activate(self): return 'registered: command "generate-rss"'
    def deactivate(self): pass
