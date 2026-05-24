from core.plugin_base import PluginBase

class ImageOptimizerPlugin(PluginBase):
    @property
    def name(self): return "image-optimizer"
    @property
    def version(self): return "0.9.1"
    def activate(self): return "registered: post-processor for .png/.jpg"
    def deactivate(self): pass
