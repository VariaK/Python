from core.plugin_base import PluginBase

class DarkModeThemePlugin(PluginBase):
    @property
    def name(self): return "dark-mode-theme"
    @property
    def version(self): return "1.3.2"
    def activate(self): return 'registered: theme "dark-mode"'
    def deactivate(self): pass
