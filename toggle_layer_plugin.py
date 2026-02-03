
import json
from qgis.PyQt.QtCore import QSettings
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.PyQt.QtGui import QKeySequence
from qgis.core import QgsProject
from qgis.gui import QgsGui

SETTINGS_KEY = "toggle_layer/mappings"  # JSON list: [{"key": "...", "layer": "..."}]


class ToggleLayerPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.menu_name = "Toggle Layer"
        self.settings_action = None
        self.mapping_actions = []  # list[QAction]
        self._dlg = None

    def initGui(self):
        self.settings_action = QAction("Toggle Layer…", self.iface.mainWindow())
        self.settings_action.triggered.connect(self.open_settings_dialog)
        self.iface.addPluginToMenu(self.menu_name, self.settings_action)

        self.rebuild_mapping_actions()

    def unload(self):
        self.clear_mapping_actions()

        if self._dlg:
            try:
                self._dlg.close()
            except Exception:
                pass
            self._dlg = None

        if self.settings_action:
            self.iface.removePluginMenu(self.menu_name, self.settings_action)
            self.settings_action.deleteLater()
            self.settings_action = None

    def open_settings_dialog(self):
        from .toggle_layer_settings_dialog import ToggleLayerSettingsDialog

        # If already open, raise it
        if self._dlg and self._dlg.isVisible():
            self._dlg.raise_()
            self._dlg.activateWindow()
            return

        self._dlg = ToggleLayerSettingsDialog(self.iface.mainWindow(), self.load_mappings())
        self._dlg.setModal(False)

        def _apply_and_close():
            mappings = self._dlg.get_mappings()

            conflicts = self.find_conflicts(mappings)
            if conflicts:
                msg = "Atalhos em conflito (já usados no QGIS):\n\n" + "\n".join(conflicts)
                QMessageBox.warning(self.iface.mainWindow(), "Toggle Layer - Conflito de atalho", msg)
                return

            self.save_mappings(mappings)
            self.rebuild_mapping_actions()
            try:
                self._dlg.close()
            except Exception:
                pass

        def _close_only():
            try:
                self._dlg.close()
            except Exception:
                pass

        self._dlg.accepted.connect(_apply_and_close)
        self._dlg.rejected.connect(_close_only)
        self._dlg.destroyed.connect(lambda *_: setattr(self, "_dlg", None))

        self._dlg.show()
        self._dlg.raise_()
        self._dlg.activateWindow()

    def load_mappings(self):
        s = QSettings()
        raw = s.value(SETTINGS_KEY, "", type=str)
        if not raw:
            return []
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                out = []
                for row in data:
                    if isinstance(row, dict):
                        out.append(
                            {
                                "key": str(row.get("key", "")).strip(),
                                "layer": str(row.get("layer", "")).strip(),
                            }
                        )
                return out
        except Exception:
            return []
        return []

    def save_mappings(self, mappings):
        s = QSettings()
        s.setValue(SETTINGS_KEY, json.dumps(mappings, ensure_ascii=False))

    def clear_mapping_actions(self):
        for act in self.mapping_actions:
            try:
                self.iface.unregisterMainWindowAction(act)
            except Exception:
                pass
            try:
                self.iface.mainWindow().removeAction(act)
            except Exception:
                pass
            try:
                self.iface.removePluginMenu(self.menu_name, act)
            except Exception:
                pass
            act.deleteLater()
        self.mapping_actions = []

    def rebuild_mapping_actions(self):
        self.clear_mapping_actions()
        mappings = self.load_mappings()

        # group by key: key -> [layer_name, layer_name, ...]
        grouped = {}
        for m in mappings:
            key = (m.get("key") or "").strip()
            layer_name = (m.get("layer") or "").strip()
            if not key or not layer_name:
                continue
            grouped.setdefault(key, []).append(layer_name)

        for key, layer_names in grouped.items():
            # remove duplicates but keep order
            seen = set()
            uniq_layers = []
            for ln in layer_names:
                if ln not in seen:
                    seen.add(ln)
                    uniq_layers.append(ln)

            label = ", ".join(uniq_layers)
            act = QAction(f"Toggle layers: {label} ({key})", self.iface.mainWindow())
            act.triggered.connect(lambda checked=False, lst=uniq_layers: self.toggle_layers_group(lst))

            self.iface.registerMainWindowAction(act, key)
            self.iface.mainWindow().addAction(act)
            self.iface.addPluginToMenu(self.menu_name, act)
            self.mapping_actions.append(act)


    def toggle_layers_group(self, layer_names):
        proj = QgsProject.instance()
        root = proj.layerTreeRoot()

        nodes = []
        any_visible = False

        for name in layer_names:
            layers = proj.mapLayersByName(name)
            if not layers:
                continue
            layer = layers[0]
            node = root.findLayer(layer.id())
            if not node:
                continue
            nodes.append(node)
            if node.isVisible():
                any_visible = True

        if not nodes:
            return

        # group behavior: if ANY visible -> hide all; else show all
        target = False if any_visible else True
        for node in nodes:
            node.setItemVisibilityChecked(target)


    def toggle_layer_by_name(self, layer_name: str):
        proj = QgsProject.instance()
        layers = proj.mapLayersByName(layer_name)
        if not layers:
            return
        layer = layers[0]
        node = proj.layerTreeRoot().findLayer(layer.id())
        if not node:
            return
        node.setItemVisibilityChecked(not node.isVisible())

    def find_conflicts(self, mappings):
        mgr = QgsGui.shortcutsManager()
        lines = []

        # group unique keys only
        keys = []
        seen = set()
        for m in mappings:
            k = (m.get("key") or "").strip()
            if not k or k in seen:
                continue
            seen.add(k)
            keys.append(k)

        for seq_str in keys:
            obj = mgr.objectForSequence(QKeySequence(seq_str))
            if not obj:
                continue

            # ignore conflicts with our own actions
            if isinstance(obj, QAction) and obj in self.mapping_actions:
                continue

            owner = ""
            if isinstance(obj, QAction):
                owner = obj.text() or obj.objectName() or "QAction"
            else:
                owner = obj.objectName() or obj.__class__.__name__

            lines.append(f"{seq_str}   (usado por: {owner})")

        return lines