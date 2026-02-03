def classFactory(iface):
    from .toggle_layer_plugin import ToggleLayerPlugin
    return ToggleLayerPlugin(iface)