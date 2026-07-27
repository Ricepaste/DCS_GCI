import os
import math
from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPolygonF, QTransform
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF

from ui.panels import (
    BraaInfoPanel, InterceptInfoPanel, AircraftStatusPanel,
    AirspaceNameInput, get_styled_input_text, get_styled_input_double
)
from ui.context_menu import handle_radar_context_menu
import geometry
from geometry import calculate_braa, calculate_speed, sync_ordered_selection

def get_base_dir():
    import sys
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        if os.path.exists(os.path.join(exe_dir, "map_data")):
            return exe_dir
        if hasattr(sys, '_MEIPASS') and os.path.exists(os.path.join(sys._MEIPASS, "map_data")):
            return sys._MEIPASS
        return exe_dir
    else:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class RadarView(QGraphicsView):
    def __init__(self, backend):
        super().__init__()
        self.backend = backend
        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(-2000000, -2000000, 4000000, 4000000) # 4000km x 4000km
        self.setScene(self.scene)
        
        self.setBackgroundBrush(QBrush(QColor(10, 20, 15)))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        
        self.track_items = {}
        self.checked_in_tracks = set()
        self.ordered_selection = []
        self.track_classifications = {}
        
        self.expanded_labels = set()
        self.label_mode = 'minimal'  # 'minimal' -> 'full' -> 'none'
        
        self.font_scale = 1.0
        self.show_airbases = True
        self.airbase_items = []
        self.airbases = {}
        self.airspace_color = QColor(255, 100, 100, 50)
        self.airspace_color_hex = "#ff6464"
        self.airspaces = {}
        self.custom_threat_rings = {}
        self.custom_markers = {}
        
        self.show_threat_rings = True
        self.threat_ring_items = {}
        self.threat_text_items = {}
        self.show_conflict_alerts = True
        self.conflict_items = {}
        
        base_dir = get_base_dir()
        current_map_path = os.path.join(base_dir, "map_data", "current_map.txt")
        self.current_theatre = "Caucasus"
        if os.path.exists(current_map_path):
            with open(current_map_path, "r", encoding="utf-8") as f:
                self.current_theatre = f.read().strip()
                
        map_data_dir = os.path.join(base_dir, "map_data", self.current_theatre)
        
        airbases_path = os.path.join(map_data_dir, "airbases.csv")
        if os.path.exists(airbases_path):
            self.airbases = {}
            with open(airbases_path, "r", encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split(',')
                    if len(parts) >= 3:
                        name, bx, bz = parts[0], float(parts[1]), float(parts[2])
                        course = float(parts[3]) if len(parts) >= 4 else 0
                        lat = float(parts[4]) if len(parts) >= 6 else None
                        lon = float(parts[5]) if len(parts) >= 6 else None
                        self.airbases[name] = {"x": bx, "z": bz, "course": course, "lat": lat, "lon": lon}
        
        self.global_ref_point = None
        valid_airbases = [ab for ab in self.airbases.values()
                          if ab.get('lat') is not None and ab.get('lon') is not None]
        if valid_airbases:
            avg_x = sum(ab['x'] for ab in valid_airbases) / len(valid_airbases)
            avg_z = sum(ab['z'] for ab in valid_airbases) / len(valid_airbases)
            best = None
            best_dist = float('inf')
            for ab in valid_airbases:
                d = (ab['x'] - avg_x)**2 + (ab['z'] - avg_z)**2
                if d < best_dist:
                    best_dist = d
                    best = ab
            self.global_ref_point = best
                        
        self.draw_airbases()
        
        coastline_path = os.path.join(map_data_dir, "coastline.csv")
        coast_pts = []
        if os.path.exists(coastline_path):
            with open(coastline_path, "r") as f:
                for line in f:
                    if line.strip():
                        parts = line.split(',')
                        if len(parts) == 2:
                            coast_pts.append((float(parts[0]), float(parts[1])))
                            
        if coast_pts:
            coast_brush = QBrush(QColor(80, 150, 150))
            for cx, cz in coast_pts:
                sx, sy = self.dcs_to_scene(cx, cz)
                pt = self.scene.addRect(-1, -1, 2, 2, QPen(Qt.PenStyle.NoPen), coast_brush)
                pt.setPos(sx, sy)
                pt.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
                pt.setZValue(-20)
            
        self.scene.selectionChanged.connect(self.on_selection_changed)
        
        self.intercept_line = self.scene.addLine(0, 0, 0, 0, QPen(QColor(255, 255, 0), 0, Qt.PenStyle.DashLine))
        self.intercept_line.setZValue(20)
        self.intercept_line.hide()
        
        self.ruler_line = self.scene.addLine(0, 0, 0, 0, QPen(QColor(180, 255, 180), 0, Qt.PenStyle.DashLine))
        self.ruler_line.setZValue(30)
        self.ruler_line.hide()
        
        self.ruler_text = self.scene.addText("")
        self.ruler_text.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
        self.ruler_text.setDefaultTextColor(QColor(180, 255, 180))
        self.ruler_text.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        self.ruler_text.setZValue(30)
        self.ruler_text.hide()

        pen_vec = QPen(QColor(0, 255, 255), 2, Qt.PenStyle.DashDotLine)
        pen_vec.setCosmetic(True)
        self.vector_line = self.scene.addLine(0, 0, 0, 0, pen_vec)
        self.vector_line.setZValue(32)
        self.vector_line.hide()
        
        self.vector_text = self.scene.addText("")
        self.vector_text.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        self.vector_text.setDefaultTextColor(QColor(0, 255, 255))
        self.vector_text.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        self.vector_text.setZValue(32)
        self.vector_text.hide()

        pen_atk = QPen(QColor(255, 50, 50), 2, Qt.PenStyle.DashLine)
        pen_atk.setCosmetic(True)
        self.attack_line = self.scene.addLine(0, 0, 0, 0, pen_atk)
        self.attack_line.setZValue(33)
        self.attack_line.hide()
        
        self.attack_text = self.scene.addText("")
        self.attack_text.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        self.attack_text.setDefaultTextColor(QColor(255, 50, 50))
        self.attack_text.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        self.attack_text.setZValue(33)
        self.attack_text.hide()
        
        self.impact_point = self.scene.addEllipse(-4, -4, 8, 8, QPen(QColor(255, 150, 50)), QBrush(Qt.BrushStyle.NoBrush))
        self.impact_point.setZValue(25)
        self.impact_point.hide()
        
        self.scale(0.01, 0.01)
        
        self.bullseye_item = self.scene.addEllipse(-10, -10, 20, 20, QPen(QColor(0, 150, 255), 2), QBrush(Qt.BrushStyle.NoBrush))
        self.bullseye_center = self.scene.addEllipse(-2, -2, 4, 4, QPen(Qt.PenStyle.NoPen), QBrush(QColor(0, 150, 255)))
        self.bullseye_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        self.bullseye_center.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        self.bullseye_item.setZValue(5)
        self.bullseye_center.setZValue(5)
        self.bullseye_item.hide()
        self.bullseye_center.hide()

        self._current_airspace_pts = []
        self._current_airspace_line = None
        self._temp_airspace_item = None
        self._temp_airspace_poly = None
        self._is_drawing_airspace = False
        self._is_setting_bullseye = False
        self._is_drawing_custom_threat = False
        self._is_adding_marker = False

        if self.airbases:
            first_ab = next(iter(self.airbases.values()))
            absx, absy = self.dcs_to_scene(first_ab['x'], first_ab['z'])
            self.centerOn(absx, absy)
            self.has_centered = True
            
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_tracks)
        self.timer.start(100)

        self.load_default_airspaces()

    def load_default_airspaces(self):
        base_dir = get_base_dir()
        default_json_path = os.path.join(base_dir, "airspaces_config.json")
        if os.path.exists(default_json_path):
            import json
            try:
                with open(default_json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for name, info in data.items():
                    pts = [QPointF(p['x'], p['y']) for p in info.get('points', [])]
                    c_hex = info.get('color', '#ff6464')
                    if len(pts) >= 3:
                        self.create_airspace_from_points(name, pts, QColor(c_hex))
            except Exception as e:
                print(f"[Airspace] Failed to auto-load default airspaces: {e}")

    def get_braa_panel(self):
        parent_widget = self.main_window.centralWidget() if hasattr(self, "main_window") else self
        if not hasattr(self, 'braa_panel') or not self.braa_panel:
            self.braa_panel = BraaInfoPanel(parent_widget)
            self.braa_panel.setParent(parent_widget)
        return self.braa_panel

    def get_intercept_panel(self):
        parent_widget = self.main_window.centralWidget() if hasattr(self, "main_window") else self
        if not hasattr(self, 'intercept_panel') or not self.intercept_panel:
            self.intercept_panel = InterceptInfoPanel(parent_widget)
            self.intercept_panel.setParent(parent_widget)
        return self.intercept_panel
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'braa_panel') and self.braa_panel and not getattr(self.braa_panel, 'custom_pos', None):
            self.braa_panel.move(20, self.height() - self.braa_panel.height() - 20)
        if hasattr(self, 'intercept_panel') and self.intercept_panel and not getattr(self.intercept_panel, 'custom_pos', None):
            self.intercept_panel.move(self.width() - self.intercept_panel.width() - 20, self.height() - self.intercept_panel.height() - 20)

    def wheelEvent(self, event):
        zoomInFactor = 1.15
        zoomOutFactor = 1 / zoomInFactor
        if event.angleDelta().y() > 0:
            zoomFactor = zoomInFactor
        else:
            zoomFactor = zoomOutFactor
        self.scale(zoomFactor, zoomFactor)

    def drawForeground(self, painter, rect):
        super().drawForeground(painter, rect)
        painter.save()
        painter.setTransform(QTransform())
        
        pixels_per_meter = self.transform().m11()
        if pixels_per_meter > 0:
            nm_in_meters = 1852.0
            steps = [1, 2, 5, 10, 20, 50, 100, 200, 500]
            best_step = 10
            for step in steps:
                if step * nm_in_meters * pixels_per_meter >= 60:
                    best_step = step
                    break
            
            bar_length_px = best_step * nm_in_meters * pixels_per_meter
            
            vp_rect = self.viewport().rect()
            x = vp_rect.width() - bar_length_px - 30
            y = vp_rect.height() - 30
            
            pen = QPen(QColor(180, 255, 180, 200))
            pen.setWidth(2)
            painter.setPen(pen)
            
            painter.drawLine(QPointF(x, y), QPointF(x + bar_length_px, y))
            painter.drawLine(QPointF(x, y - 6), QPointF(x, y + 6))
            painter.drawLine(QPointF(x + bar_length_px, y - 6), QPointF(x + bar_length_px, y + 6))
            
            painter.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            painter.drawText(QRectF(x, y - 25, bar_length_px, 20), Qt.AlignmentFlag.AlignCenter, f"{best_step} NM")
            
        painter.restore()

    def dcs_to_scene(self, x, z):
        return z, -x

    def scene_to_dcs(self, sx, sy):
        return -sy, sx

    def draw_airbases(self):
        for name, pos in self.airbases.items():
            sx, sy = self.dcs_to_scene(pos['x'], pos['z'])
            runway_item = self.scene.addRect(-3, -10, 6, 20, QPen(Qt.PenStyle.NoPen), QBrush(QColor(180, 180, 180)))
            runway_item.setPos(sx, sy)
            course_deg = pos.get('course', 0)
            runway_item.setRotation(-course_deg)
            runway_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            runway_item.setZValue(-1)
            
            text_item = self.scene.addText(name, QFont("Consolas", 8))
            text_item.setDefaultTextColor(QColor(150, 150, 150))
            text_item.setPos(sx + 8, sy - 10)
            text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            text_item.setZValue(-1)
            
            self.airbase_items.extend([runway_item, text_item])
            
    def toggle_airbases(self):
        self.show_airbases = not self.show_airbases
        for item in self.airbase_items:
            item.setVisible(self.show_airbases)
            
    def toggle_set_bullseye(self):
        self._is_setting_bullseye = True
        self._is_drawing_airspace = False
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.viewport().setCursor(Qt.CursorShape.CrossCursor)
        if hasattr(self, 'main_window'):
            self.main_window.statusBar().showMessage("Click on map to set Bullseye...")

    def toggle_draw_airspace(self):
        self._is_drawing_airspace = True
        self._is_setting_bullseye = False
        self._current_airspace_pts = []
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.viewport().setCursor(Qt.CursorShape.CrossCursor)
        if hasattr(self, 'main_window'):
            self.main_window.statusBar().showMessage("Left click to add points, Right click to finish airspace.")
            
    def toggle_all_labels(self):
        cycle = ['minimal', 'full', 'none']
        idx = cycle.index(self.label_mode)
        self.label_mode = cycle[(idx + 1) % 3]
        if self.label_mode != 'minimal':
            self.expanded_labels.clear()
        for items in self.track_items.values():
            items.pop('last_html', None)
            if 'text' in items:
                items['text'].setVisible(self.label_mode != 'none')
        mode_labels = {'minimal': 'MINIMAL', 'full': 'FULL', 'none': 'NONE'}
        if hasattr(self, 'main_window'):
            self.main_window.statusBar().showMessage(
                f"Label Mode: {mode_labels[self.label_mode]}", 2000)
        self.update_tracks()

    def toggle_threat_rings(self):
        self.show_threat_rings = not self.show_threat_rings
        for ellipse in self.threat_ring_items.values():
            ellipse.setVisible(self.show_threat_rings)
        if hasattr(self, 'threat_text_items'):
            for text_item in self.threat_text_items.values():
                text_item.setVisible(self.show_threat_rings)
        if hasattr(self, 'custom_threat_rings'):
            for data in self.custom_threat_rings.values():
                if 'ring' in data and data['ring']: data['ring'].setVisible(self.show_threat_rings)
                if 'text' in data and data['text']: data['text'].setVisible(self.show_threat_rings)
        if hasattr(self, 'main_window'):
            status = "Threat Rings ON" if self.show_threat_rings else "Threat Rings OFF"
            self.main_window.statusBar().showMessage(status)

    def set_font_scale(self, scale):
        self.font_scale = float(scale)
        for items in self.track_items.values():
            items.pop('last_html', None)
        for data in self.airspaces.values():
            if 'text' in data and data['text']:
                data['text'].setFont(QFont("Consolas", int(14 * self.font_scale), QFont.Weight.Bold))
        for data in self.custom_threat_rings.values():
            if 'text' in data and data['text']:
                data['text'].setFont(QFont("Consolas", int(10 * self.font_scale), QFont.Weight.Bold))
        for m in self.custom_markers.values():
            if 'text' in m and m['text']:
                m['text'].setFont(QFont("Consolas", int(9 * self.font_scale), QFont.Weight.Bold))
        if hasattr(self, 'braa_panel') and self.braa_panel:
            self.braa_panel.update_font_scale(self.font_scale)
        if hasattr(self, 'intercept_panel') and self.intercept_panel:
            self.intercept_panel.update_font_scale(self.font_scale)
        self.update_tracks()

    def create_airspace_from_points(self, name, pts, color=None):
        if not color:
            color = self.airspace_color
        poly = QPolygonF(pts)
        pen = QPen(color, 2)
        pen.setCosmetic(True)
        fill_color = QColor(color.red(), color.green(), color.blue(), 50)
        item = self.scene.addPolygon(poly, pen, QBrush(fill_color))
        item.setZValue(-5)
        
        text_item = self.scene.addText(name)
        text_item.setDefaultTextColor(color)
        text_item.setZValue(-4)
        font = QFont("Consolas", int(14 * self.font_scale), QFont.Weight.Bold)
        text_item.setFont(font)
        
        center = poly.boundingRect().center()
        text_item.setPos(center.x() - text_item.boundingRect().width()/2, center.y() - text_item.boundingRect().height()/2)
        text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        
        item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        text_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.airspaces[name] = {"poly": item, "text": text_item, "color_hex": color.name()}

    def finalize_airspace_naming(self, name, color=None):
        # Guard: _temp_airspace_poly must exist; if None, a previous finalize already cleaned up
        if not self._temp_airspace_poly:
            import logging
            logging.error("[AIRSPACE] finalize_airspace_naming called but _temp_airspace_poly is None ??skipped.")
            return

        original_name = name
        counter = 1
        while name in self.airspaces:
            name = f"{original_name} ({counter})"
            counter += 1
            
        if not color:
            color = self.airspace_color
        fill_color = QColor(color.red(), color.green(), color.blue(), 50)
        if self._temp_airspace_item:
            pen = QPen(color, 2)
            pen.setCosmetic(True)
            self._temp_airspace_item.setPen(pen)
            self._temp_airspace_item.setBrush(QBrush(fill_color))
        
        text_item = self.scene.addText(name)
        text_item.setDefaultTextColor(color)
        text_item.setZValue(-4)
        font = QFont("Consolas", int(14 * self.font_scale), QFont.Weight.Bold)
        text_item.setFont(font)
        
        center = self._temp_airspace_poly.boundingRect().center()
        text_item.setPos(center.x() - text_item.boundingRect().width()/2, center.y() - text_item.boundingRect().height()/2)
        text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        
        self.airspaces[name] = {"poly": self._temp_airspace_item, "text": text_item, "color_hex": color.name()}
        self._temp_airspace_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        text_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        
        self._is_drawing_airspace = False
        self._current_airspace_pts = []
        self._current_airspace_line = None
        self._temp_airspace_item = None
        self._temp_airspace_poly = None
        self.unsetCursor()
        self.viewport().unsetCursor()
        
        if hasattr(self, 'main_window') and hasattr(self.main_window, 'manager_panel') and self.main_window.manager_panel:
            self.main_window.manager_panel.list_widget.clear()
            self.main_window.manager_panel.list_widget.addItems(self.airspaces.keys())

        if hasattr(self, 'main_window'):
            self.main_window.statusBar().showMessage("Airspace saved.")

    def toggle_draw_custom_threat_circle(self):
        self._is_drawing_threat_circle = True
        self._is_adding_marker = False
        self._is_drawing_airspace = False
        self._is_setting_bullseye = False
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.viewport().setCursor(Qt.CursorShape.CrossCursor)
        if hasattr(self, 'main_window'):
            self.main_window.statusBar().showMessage("Click on map to place Custom Threat Circle...")

    def add_custom_threat_ring(self, pos, radius_nm, label_name):
        radius_m = radius_nm * 1852.0
        pen = QPen(QColor(255, 120, 120), 1.5, Qt.PenStyle.DashLine)
        brush = QBrush(QColor(255, 60, 60, 25))
        ring = self.scene.addEllipse(pos.x() - radius_m, pos.y() - radius_m, radius_m * 2, radius_m * 2, pen, brush)
        ring.setZValue(-3)
        
        text = self.scene.addText(f"{label_name} ({radius_nm:g}NM)")
        text.setDefaultTextColor(QColor(255, 120, 120))
        text.setFont(QFont("Consolas", int(10 * self.font_scale), QFont.Weight.Bold))
        text.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        text.setPos(pos.x(), pos.y() - 15)
        text.setZValue(-2)
        
        show = getattr(self, 'show_threat_rings', True)
        ring.setVisible(show)
        text.setVisible(show)
        
        tag = f"CUSTOM_{len(self.custom_threat_rings)+1}_{label_name}"
        self.custom_threat_rings[tag] = {'ring': ring, 'text': text}

    def toggle_add_tactical_marker(self):
        self._is_adding_marker = True
        self._is_drawing_threat_circle = False
        self._is_drawing_airspace = False
        self._is_setting_bullseye = False
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.viewport().setCursor(Qt.CursorShape.CrossCursor)
        if hasattr(self, 'main_window'):
            self.main_window.statusBar().showMessage("Click on map to place Tactical Marker Pin...")

    def add_tactical_marker(self, pos, marker_type="MARKER", label="POINT ALPHA"):
        pen = QPen(QColor(0, 230, 255), 1.5)
        cross1 = self.scene.addLine(pos.x() - 4, pos.y(), pos.x() + 4, pos.y(), pen)
        cross2 = self.scene.addLine(pos.x(), pos.y() - 4, pos.x(), pos.y() + 4, pen)
        cross1.setZValue(12)
        cross2.setZValue(12)
        cross1.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        cross2.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        
        font_pt = int(9 * self.font_scale)
        text = self.scene.addText(f"+ {label}")
        text.setDefaultTextColor(QColor(0, 230, 255))
        text.setFont(QFont("Consolas", font_pt, QFont.Weight.Bold))
        text.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        text.setPos(pos.x() + 6, pos.y() - 10)
        text.setZValue(12)
        
        m_id = f"MARKER_{len(self.custom_markers)+1}"
        self.custom_markers[m_id] = {'cross1': cross1, 'cross2': cross2, 'text': text, 'label': label, 'pos': pos}

    def delete_tactical_marker(self, m_id):
        if m_id in self.custom_markers:
            m = self.custom_markers.pop(m_id)
            if 'cross1' in m and m['cross1']: self.scene.removeItem(m['cross1'])
            if 'cross2' in m and m['cross2']: self.scene.removeItem(m['cross2'])
            if 'icon' in m and m['icon']: self.scene.removeItem(m['icon'])
            if 'text' in m and m['text']: self.scene.removeItem(m['text'])
            if hasattr(self, 'main_window'):
                self.main_window.statusBar().showMessage(f"Marker '{m.get('label','')}' deleted.")

    def delete_custom_threat_ring(self, r_id):
        if r_id in self.custom_threat_rings:
            r = self.custom_threat_rings.pop(r_id)
            if 'ring' in r and r['ring']: self.scene.removeItem(r['ring'])
            if 'text' in r and r['text']: self.scene.removeItem(r['text'])
            if hasattr(self, 'main_window'):
                self.main_window.statusBar().showMessage("Custom threat ring deleted.")

    def clear_all_tactical_markers(self):
        for m_id in list(self.custom_markers.keys()):
            self.delete_tactical_marker(m_id)

    def mousePressEvent(self, event):
        if getattr(self, '_is_vectoring_ai', False):
            if event.button() == Qt.MouseButton.LeftButton:
                pos = self.mapToScene(event.position().toPoint())
                dcs_x, dcs_z = self.scene_to_dcs(pos.x(), pos.y())
                target_grp = getattr(self, '_vector_target_group', None)
                alt_m = getattr(self, '_vector_target_alt_m', None)
                speed_mps = getattr(self, '_vector_target_speed_mps', None)
                
                self._is_vectoring_ai = False
                self._vector_target_group = None
                self.vector_line.hide()
                self.vector_text.hide()
                self.unsetCursor()
                self.viewport().unsetCursor()
                
                if target_grp:
                    cmd = {
                        "action": "vector",
                        "group_name": target_grp,
                        "x": dcs_x,
                        "z": dcs_z
                    }
                    if alt_m is not None: cmd["alt"] = alt_m
                    if speed_mps is not None: cmd["speed"] = speed_mps
                    
                    if self.backend.send_command(cmd):
                        if hasattr(self, 'main_window'):
                            self.main_window.statusBar().showMessage(f"Vectored '{target_grp}' to destination.")
            elif event.button() == Qt.MouseButton.RightButton:
                self._is_vectoring_ai = False
                self._vector_target_group = None
                self.vector_line.hide()
                self.vector_text.hide()
                self.unsetCursor()
                self.viewport().unsetCursor()
                if hasattr(self, 'main_window'):
                    self.main_window.statusBar().showMessage("Vectoring cancelled.")
            return

        if getattr(self, '_is_selecting_attack_target', False):
            if event.button() == Qt.MouseButton.LeftButton:
                pos = event.position().toPoint()
                clicked_items = self.items(pos)
                target_name = None
                for name, items in self.track_items.items():
                    icon = items.get('icon')
                    text = items.get('text')
                    class_text = items.get('class_text')
                    for item in clicked_items:
                        if item in (icon, text, class_text) or (item and item.parentItem() in (icon, text, class_text)):
                            target_name = name
                            break
                    if target_name: break
                    
                attacker_grp = getattr(self, '_attack_attacker_group', None)
                self._is_selecting_attack_target = False
                self._attack_attacker_group = None
                self.attack_line.hide()
                self.attack_text.hide()
                self.unsetCursor()
                self.viewport().unsetCursor()
                
                if attacker_grp and target_name:
                    cmd = {
                        "action": "attack_target",
                        "group_name": attacker_grp,
                        "target_name": target_name
                    }
                    if self.backend.send_command(cmd):
                        if hasattr(self, 'main_window'):
                            atk_tn = geometry.generate_link16_tn(attacker_grp)
                            tgt_tn = geometry.generate_link16_tn(target_name)
                            self.main_window.statusBar().showMessage(f"ATTACK ORDER: Group TN #{atk_tn} ordered to engage Target TN #{tgt_tn}.")
                else:
                    if hasattr(self, 'main_window'):
                        self.main_window.statusBar().showMessage("Attack order cancelled (No valid target clicked).")
            elif event.button() == Qt.MouseButton.RightButton:
                self._is_selecting_attack_target = False
                self._attack_attacker_group = None
                self.attack_line.hide()
                self.attack_text.hide()
                self.unsetCursor()
                self.viewport().unsetCursor()
                if hasattr(self, 'main_window'):
                    self.main_window.statusBar().showMessage("Attack order cancelled.")
            return

        if getattr(self, '_is_setting_bullseye', False):
            if event.button() == Qt.MouseButton.LeftButton:
                pos = self.mapToScene(event.position().toPoint())
                self.bullseye_pos = pos
                self.bullseye_item.setPos(pos)
                self.bullseye_center.setPos(pos)
                self.bullseye_item.show()
                self.bullseye_center.show()
                self._is_setting_bullseye = False
                if hasattr(self, 'main_window'):
                    self.main_window.statusBar().showMessage("Bullseye set.")
                self.unsetCursor()
                self.viewport().unsetCursor()
            return
            
        if getattr(self, '_is_drawing_threat_circle', False):
            if event.button() == Qt.MouseButton.LeftButton:
                pos = self.mapToScene(event.position().toPoint())
                self._is_drawing_threat_circle = False
                self.unsetCursor()
                self.viewport().unsetCursor()
                
                from ui.panels import _show_canvas_dialog
                label, radius_nm, ok = _show_canvas_dialog(
                    self,
                    title="CUSTOM THREAT RING",
                    prompt="Enter Threat Label:",
                    default_text="SAM THREAT",
                    show_number=True,
                    number_label="Radius (NM):",
                    number_value=30.0,
                    number_min=1.0, number_max=500.0, number_decimals=1,
                )
                if ok and label:
                    self.add_custom_threat_ring(pos, radius_nm, label)
                    if hasattr(self, 'main_window'):
                        self.main_window.statusBar().showMessage("Custom threat circle added.")
            return

        if getattr(self, '_is_adding_marker', False):
            if event.button() == Qt.MouseButton.LeftButton:
                pos = self.mapToScene(event.position().toPoint())
                self._is_adding_marker = False
                self.unsetCursor()
                self.viewport().unsetCursor()
                
                from ui.panels import _show_canvas_dialog
                m_label, _, ok = _show_canvas_dialog(
                    self,
                    title="TACTICAL MARKER",
                    prompt="Enter Marker Label:",
                    default_text="MARKER ALPHA",
                )
                if ok and m_label:
                    self.add_tactical_marker(pos, label=m_label)
                    if hasattr(self, 'main_window'):
                        self.main_window.statusBar().showMessage("Tactical marker added.")
            return
            
        if getattr(self, '_is_drawing_airspace', False):
            if event.button() == Qt.MouseButton.LeftButton:
                pos = self.mapToScene(event.position().toPoint())
                self._current_airspace_pts.append(pos)
                if len(self._current_airspace_pts) > 1:
                    if self._current_airspace_line:
                        self.scene.removeItem(self._current_airspace_line)
                    poly = QPolygonF(self._current_airspace_pts)
                    pen = QPen(QColor(255, 100, 100), 2, Qt.PenStyle.DashLine)
                    pen.setCosmetic(True)
                    self._current_airspace_line = self.scene.addPolygon(poly, pen, QBrush(Qt.BrushStyle.NoBrush))
                    self._current_airspace_line.setZValue(-5)
            elif event.button() == Qt.MouseButton.RightButton:
                if self._current_airspace_line:
                    try:
                        self.scene.removeItem(self._current_airspace_line)
                    except:
                        pass
                    self._current_airspace_line = None

                if len(self._current_airspace_pts) > 2:
                    self._is_drawing_airspace = False
                    self.unsetCursor()
                    self.viewport().unsetCursor()
                    
                    poly = QPolygonF(self._current_airspace_pts)
                    pen = QPen(QColor(255, 100, 100), 2)
                    pen.setCosmetic(True)
                    item = self.scene.addPolygon(poly, pen, QBrush(QColor(255, 100, 100, 50)))
                    item.setZValue(-5)
                    
                    self._temp_airspace_poly = poly
                    self._temp_airspace_item = item
                    
                    from ui.panels import AirspaceNameInput
                    import traceback, logging
                    # Dismiss any still-open dialog with close() NOT reject().
                    # reject() would clear _temp_airspace_poly which belongs to the NEW draw.
                    if hasattr(self, 'name_input') and self.name_input:
                        try:
                            self.name_input.close()
                        except Exception:
                            pass
                    self.name_input = None
                    try:
                        # Parent to main_window so it's not a separate taskbar window
                        main_win = self.window()
                        logging.basicConfig(filename='app_crash.log', level=logging.DEBUG)
                        logging.debug(f"[AIRSPACE] Creating AirspaceNameInput, main_win={main_win}")
                        self.name_input = AirspaceNameInput(self, parent=main_win)
                        self.name_input.input.setText(f"Airspace {len(self.airspaces) + 1}")
                        
                        # QDialog.move() uses global screen coordinates
                        center_global = self.mapToGlobal(self.rect().center())
                        logging.debug(f"[AIRSPACE] center_global={center_global}, size={self.name_input.size()}")
                        self.name_input.move(
                            center_global.x() - self.name_input.width() // 2,
                            center_global.y() - self.name_input.height() // 2,
                        )
                        logging.debug(f"[AIRSPACE] Calling show(), isVisible before={self.name_input.isVisible()}")
                        self.name_input.show()
                        self.name_input.raise_()
                        self.name_input.activateWindow()
                        logging.debug(f"[AIRSPACE] After show(), isVisible={self.name_input.isVisible()}, pos={self.name_input.pos()}")
                    except Exception:
                        logging.error(f"[AIRSPACE] Exception showing dialog:\n{traceback.format_exc()}")
                else:
                    self._is_drawing_airspace = False
                    self._current_airspace_pts = []
                    self.unsetCursor()
                    self.viewport().unsetCursor()
                    if hasattr(self, 'main_window'):
                        self.main_window.statusBar().showMessage("Airspace drawing cancelled (Less than 3 points).")
                return

        if event.button() == Qt.MouseButton.RightButton:
            self._ruler_press_pos = event.position().toPoint()
            self._ruler_start = self.mapToScene(event.position().toPoint())
            return

        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            clicked_items = self.items(pos)
            is_track_click = False
            for name, items in self.track_items.items():
                icon = items.get('icon')
                text = items.get('text')
                class_text = items.get('class_text')
                for item in clicked_items:
                    if item in (icon, text, class_text) or (item and item.parentItem() in (icon, text, class_text)):
                        if name in self.expanded_labels:
                            self.expanded_labels.remove(name)
                        else:
                            self.expanded_labels.add(name)
                        is_track_click = True
                        break
                if is_track_click:
                    break
            if not is_track_click:
                self._is_panning = True
                self._pan_start = event.position().toPoint()
                return
            
        super().mousePressEvent(event)
        
    def mouseMoveEvent(self, event):
        current_pos = self.mapToScene(event.position().toPoint())
        
        dcs_dz = current_pos.x()
        dcs_dx = -current_pos.y()
        
        if hasattr(self, 'main_window'):
            ref = getattr(self, 'global_ref_point', None)
            
            if ref:
                lat, lon = geometry.dcs_to_latlon(dcs_dx, dcs_dz, ref['x'], ref['z'], ref['lat'], ref['lon'])
                latlon_str = geometry.to_dms(lat, True) + " " + geometry.to_dms(lon, False)
                mgrs_str = geometry.latlon_to_mgrs(lat, lon)
                
                be_str = ""
                if hasattr(self, 'bullseye_pos') and self.bullseye_pos:
                    bx = -self.bullseye_pos.y()
                    bz = self.bullseye_pos.x()
                    dx = dcs_dx - bx
                    dz = dcs_dz - bz
                    brg = (math.degrees(math.atan2(dz, dx)) + 360) % 360
                    rng = math.hypot(dx, dz) / 1852.0
                    be_str = f" | B/E: {int(brg):03d}° / {rng:.1f} NM"
                
                self.main_window.statusBar().showMessage(f"Cursor: {latlon_str} | MGRS: {mgrs_str}{be_str}")
            else:
                self.main_window.statusBar().showMessage("Cursor: No Reference Data")

        if getattr(self, '_is_vectoring_ai', False):
            grp_name = getattr(self, '_vector_target_group', 'AI')
            start_pos = None
            for name, items in self.track_items.items():
                if name == grp_name or items.get('group_name') == grp_name:
                    if 'icon' in items:
                        start_pos = items['icon'].pos()
                        break
            if not start_pos:
                start_pos = current_pos
                
            self.vector_line.setLine(start_pos.x(), start_pos.y(), current_pos.x(), current_pos.y())
            self.vector_line.show()
            
            s_dx = -start_pos.y()
            s_dz = start_pos.x()
            e_dx = -current_pos.y()
            e_dz = current_pos.x()
            
            v_dx = e_dx - s_dx
            v_dz = e_dz - s_dz
            v_hdg = (math.degrees(math.atan2(v_dz, v_dx)) + 360) % 360
            v_dist = math.hypot(v_dx, v_dz) / 1852.0
            
            self.vector_text.setPlainText(f"VECTOR '{grp_name}' -> {int(v_hdg):03d}° / {v_dist:.1f} NM")
            self.vector_text.setPos(current_pos.x() + 15, current_pos.y() - 15)
            self.vector_text.show()

        if getattr(self, '_is_selecting_attack_target', False):
            grp_name = getattr(self, '_attack_attacker_group', 'AI')
            start_pos = None
            for name, items in self.track_items.items():
                if name == grp_name or items.get('group_name') == grp_name:
                    if 'icon' in items:
                        start_pos = items['icon'].pos()
                        break
            if not start_pos: start_pos = current_pos
            
            self.attack_line.setLine(start_pos.x(), start_pos.y(), current_pos.x(), current_pos.y())
            self.attack_line.show()
            
            s_dx = -start_pos.y()
            s_dz = start_pos.x()
            e_dx = -current_pos.y()
            e_dz = current_pos.x()
            v_dx = e_dx - s_dx
            v_dz = e_dz - s_dz
            v_hdg = (math.degrees(math.atan2(v_dz, v_dx)) + 360) % 360
            v_dist = math.hypot(v_dx, v_dz) / 1852.0
            
            atk_tn = geometry.generate_link16_tn(grp_name)
            self.attack_text.setPlainText(f"ATTACK TARGET [TN #{atk_tn}] -> {int(v_hdg):03d}° / {v_dist:.1f} NM")
            self.attack_text.setPos(current_pos.x() + 15, current_pos.y() - 15)
            self.attack_text.show()

        if getattr(self, '_is_drawing_airspace', False) and len(self._current_airspace_pts) > 0:
            preview_pts = self._current_airspace_pts + [current_pos]
            if self._current_airspace_line:
                self.scene.removeItem(self._current_airspace_line)
            poly = QPolygonF(preview_pts)
            pen = QPen(QColor(255, 100, 100), 2, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            self._current_airspace_line = self.scene.addPolygon(poly, pen, QBrush(Qt.BrushStyle.NoBrush))
            self._current_airspace_line.setZValue(-5)

        if getattr(self, '_ruler_press_pos', None) and not getattr(self, '_is_ruler', False):
            move_dist = (event.position().toPoint() - self._ruler_press_pos).manhattanLength()
            if move_dist > 5:
                self._is_ruler = True
                self.ruler_line.setLine(self._ruler_start.x(), self._ruler_start.y(), current_pos.x(), current_pos.y())
                self.ruler_line.show()
                self.ruler_text.setPos(self._ruler_start)
                self.ruler_text.show()

        if getattr(self, '_is_panning', False):
            delta = event.position().toPoint() - self._pan_start
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            self._pan_start = event.position().toPoint()
            return
        elif getattr(self, '_is_ruler', False):
            self.ruler_line.setLine(self._ruler_start.x(), self._ruler_start.y(), current_pos.x(), current_pos.y())
            
            start_dcs_dz = self._ruler_start.x()
            start_dcs_dx = -self._ruler_start.y()
            end_dcs_dz = current_pos.x()
            end_dcs_dx = -current_pos.y()
            
            r_dx = end_dcs_dx - start_dcs_dx
            r_dz = end_dcs_dz - start_dcs_dz
            hdg = (math.degrees(math.atan2(r_dz, r_dx)) + 360) % 360
            dist_nm = math.hypot(r_dx, r_dz) / 1852.0
            
            declinations = {
                "Caucasus": 6.0,
                "Syria": 5.0,
                "PersianGulf": 2.0,
                "Nevada": 11.5,
                "Marianas": 2.0,
                "Normandy": -1.0,
                "TheChannel": -1.0,
                "Sinai": 4.0,
            }
            decl = declinations.get(self.current_theatre, 6.0)
            mag_hdg = (hdg - decl) % 360
            
            self.ruler_text.setPlainText(f"{int(hdg):03d}° ({int(mag_hdg):03d}°M) / {dist_nm:.1f} NM")
            self.ruler_text.setPos(current_pos.x() + 15, current_pos.y() - 15)
            return
        super().mouseMoveEvent(event)
        
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and getattr(self, '_is_panning', False):
            self._is_panning = False
            return
        elif event.button() == Qt.MouseButton.RightButton:
            self._ruler_press_pos = None
            if getattr(self, '_is_ruler', False):
                self._is_ruler = False
                self.ruler_line.hide()
                self.ruler_text.hide()
                return
        super().mouseReleaseEvent(event)
        
    def mouseDoubleClickEvent(self, event):
        pos = event.position().toPoint()
        clicked_items = self.items(pos)
        found_name = None
        for name, items in self.track_items.items():
            icon = items.get('icon')
            text = items.get('text')
            class_text = items.get('class_text')
            for item in clicked_items:
                if item in (icon, text, class_text) or (item and item.parentItem() in (icon, text, class_text)):
                    found_name = name
                    break
            if found_name:
                break
        if found_name:
            self.open_status_panel(found_name)
        super().mouseDoubleClickEvent(event)
        
    def contextMenuEvent(self, event):
        pos = event.pos()
        clicked_items = self.items(pos)
        
        target_marker_id = None
        for m_id, m_data in list(self.custom_markers.items()):
            icon = m_data.get('icon')
            text = m_data.get('text')
            group = m_data.get('group')
            for item in clicked_items:
                if item in (icon, text, group) or (group and item and item.parentItem() == group):
                    target_marker_id = m_id
                    break
            if target_marker_id:
                break

        if target_marker_id:
            m_label = self.custom_markers[target_marker_id].get('label', 'MARKER')
            from PyQt6.QtWidgets import QMenu
            menu = QMenu(self)
            menu.setStyleSheet("""
                QMenu { background-color: #162420; color: #b4ffb4; border: 1px solid #2a4035; font-family: Consolas; font-weight: bold; }
                QMenu::item:selected { background-color: #2a4035; color: #ff5555; }
            """)
            act_del = menu.addAction(f"Delete Marker: [{m_label}]")
            act_clear_all = menu.addAction("Clear All Tactical Markers")
            action = menu.exec(event.globalPos())
            if action == act_del:
                self.delete_tactical_marker(target_marker_id)
            elif action == act_clear_all:
                self.clear_all_tactical_markers()
            return

        target_ring_id = None
        for r_id, r_data in list(self.custom_threat_rings.items()):
            ring = r_data.get('ring')
            text = r_data.get('text')
            for item in clicked_items:
                if item in (ring, text):
                    target_ring_id = r_id
                    break
            if target_ring_id:
                break

        if target_ring_id:
            from PyQt6.QtWidgets import QMenu
            menu = QMenu(self)
            menu.setStyleSheet("""
                QMenu { background-color: #162420; color: #b4ffb4; border: 1px solid #2a4035; font-family: Consolas; font-weight: bold; }
                QMenu::item:selected { background-color: #2a4035; color: #ff5555; }
            """)
            act_del = menu.addAction("Delete Custom Threat Ring")
            action = menu.exec(event.globalPos())
            if action == act_del:
                self.delete_custom_threat_ring(target_ring_id)
            return

        target_name = None
        for name, items in self.track_items.items():
            icon = items.get('icon')
            text = items.get('text')
            class_text = items.get('class_text')
            for item in clicked_items:
                if item in (icon, text, class_text) or (item and item.parentItem() in (icon, text, class_text)):
                    target_name = name
                    break
            if target_name:
                break
                
        if target_name:
            handle_radar_context_menu(self, event, target_name, clicked_items)

    def toggle_conflict_alerts(self):
        self.show_conflict_alerts = not self.show_conflict_alerts
        if not self.show_conflict_alerts:
            for pair_key, items in list(self.conflict_items.items()):
                self.scene.removeItem(items['line'])
                self.scene.removeItem(items['text'])
            self.conflict_items.clear()
        if hasattr(self, 'main_window'):
            status = "Conflict Alerts ON" if self.show_conflict_alerts else "Conflict Alerts OFF"
            self.main_window.statusBar().showMessage(status, 2000)
        self.update_tracks()

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            for item in self.scene.selectedItems():
                self.scene.removeItem(item)
        elif key in (Qt.Key.Key_F, Qt.Key.Key_U, Qt.Key.Key_B, Qt.Key.Key_H):
            cls_map = {
                Qt.Key.Key_F: "FRIENDLY",
                Qt.Key.Key_U: "UNKNOWN",
                Qt.Key.Key_B: "BANDIT",
                Qt.Key.Key_H: "HOSTILE"
            }
            target_cls = cls_map[key]
            for name in self.ordered_selection:
                self.set_track_classification(name, target_cls)
            if hasattr(self, 'status_panel') and self.status_panel.isVisible():
                self.refresh_status_panel()
        elif key == Qt.Key.Key_T:
            self.toggle_threat_rings()
        else:
            super().keyPressEvent(event)

    def set_track_classification(self, name, cls):
        self.track_classifications[name] = cls
        self.update_tracks()

    def get_track_classification(self, name, default_is_hostile):
        default_cls = "UNKNOWN" if default_is_hostile else "FRIENDLY"
        return self.track_classifications.get(name, default_cls)
        
    def get_unit_type(self, target_data, is_hostile, tracks):
        unit_type_str = target_data.get('type') or 'UNKNOWN'
        if is_hostile:
            awacs_keywords = ['E-2', 'E-3', 'A-50', 'KJ', '1L13', '55G6']
            nctr_success = False
            for f in tracks['friendlies']:
                f_type = f.get('type') or ''
                is_awacs = any(k in f_type for k in awacs_keywords)
                braa = calculate_braa(f, target_data)
                
                if is_awacs and braa['range'] <= 60.0 and braa['aspect'] in ['HOT', 'COLD']:
                    nctr_success = True
                    break
            if not nctr_success:
                unit_type_str = "UNKNOWN"
        return unit_type_str
        
    def refresh_status_panel(self):
        if hasattr(self, 'status_panel') and self.status_panel.isVisible() and self.status_panel.current_unit:
            name = self.status_panel.current_unit
            tracks = self.backend.get_tracks()
            target_data = None
            is_hostile = False
            for f in tracks['friendlies']:
                if f['unit_name'] == name:
                    target_data = f
                    break
            if not target_data:
                for h in tracks['hostiles']:
                    if h['unit_name'] == name:
                        target_data = h
                        is_hostile = True
                        break
            if target_data:
                unit_type_str = self.get_unit_type(target_data, is_hostile, tracks)
                current_cls = self.get_track_classification(name, is_hostile)
                self.status_panel.update_data(target_data, unit_type_str, is_hostile, current_cls)

    def open_status_panel(self, name):
        parent_widget = self.main_window.centralWidget() if hasattr(self, "main_window") else self
        if not hasattr(self, 'status_panel') or not self.status_panel:
            self.status_panel = AircraftStatusPanel(parent_widget)
            self.status_panel.setParent(parent_widget)
            self.status_panel.radar = self
            
        tracks = self.backend.get_tracks()
        target_data = None
        is_hostile = False
        
        for f in tracks['friendlies']:
            if f['unit_name'] == name:
                target_data = f
                break
        
        if not target_data:
            for h in tracks['hostiles']:
                if h['unit_name'] == name:
                    target_data = h
                    is_hostile = True
                    break
                    
        if not target_data:
            return
            
        unit_type_str = self.get_unit_type(target_data, is_hostile, tracks)
        current_cls = self.get_track_classification(target_data['unit_name'], is_hostile)
        self.status_panel.update_data(target_data, unit_type_str, is_hostile, current_cls)
        
        if getattr(self.status_panel, 'custom_pos', None):
            self.status_panel.move(self.status_panel.custom_pos)
        elif not self.status_panel.isVisible():
            pw = parent_widget.width()
            sw = self.status_panel.width()
            self.status_panel.move(max(10, pw - sw - 20), 20)
        self.status_panel.show()
        self.status_panel.raise_()
            
    def on_selection_changed(self):
        current_selected = self.scene.selectedItems()
        current_names = []
        for name, items in self.track_items.items():
            if items['icon'] in current_selected:
                current_names.append(name)
                
        self.ordered_selection = sync_ordered_selection(self.ordered_selection, current_names)

    def toggle_selected_friendly(self):
        for name, items in self.track_items.items():
            if items['icon'].isSelected() and not items['is_hostile']:
                if name in self.checked_in_tracks:
                    self.checked_in_tracks.remove(name)
                else:
                    self.checked_in_tracks.add(name)
        self.update_tracks()

    def get_render_color(self, name, default_is_hostile, is_checked_in=False):
        cls = self.get_track_classification(name, default_is_hostile)
        if cls == "FRIENDLY":
            return QColor(50, 200, 255) if is_checked_in else QColor(50, 255, 50)
        if cls == "UNKNOWN": return QColor(255, 255, 50)
        if cls in ["HOSTILE", "BANDIT"]: return QColor(255, 50, 50)
        return QColor(255, 255, 255)

    def update_tracks(self):
        try:
            self._do_update_tracks()
        except Exception as e:
            import traceback
            with open("app_crash.log", "w") as f:
                f.write(traceback.format_exc())

    def _do_update_tracks(self):
        tracks = self.backend.get_tracks()
        current_names = set()
        friendly_data = {}
        hostile_data = {}
        
        for f in tracks['friendlies']:
            name = f['unit_name']
            cls = self.get_track_classification(name, False)
            color = self.get_render_color(name, False, name in self.checked_in_tracks)
            
            prefix = 'F'
            if any(k in (f.get('type') or '') for k in ['E-2', 'E-3', 'A-50', 'KJ', '1L13', '55G6']):
                prefix = 'A'
            elif cls == "UNKNOWN": prefix = 'U'
            elif cls == "HOSTILE": prefix = 'H'
            elif cls == "BANDIT": prefix = 'B'
            
            self._update_single_track(f, color, is_hostile=False, prefix=prefix)
            current_names.add(name)
            friendly_data[name] = f
            
        for h in tracks['hostiles']:
            name = h['unit_name']
            cls = self.get_track_classification(name, True)
            color = self.get_render_color(name, True, False)
            
            prefix = 'U'
            if cls == "FRIENDLY": prefix = 'F'
            elif cls == "HOSTILE": prefix = 'H'
            elif cls == "BANDIT": prefix = 'B'
            
            self._update_single_track(h, color, is_hostile=True, prefix=prefix)
            current_names.add(name)
            hostile_data[name] = h
            
        for name in list(self.track_items.keys()):
            if name not in current_names:
                items = self.track_items.pop(name)
                self.scene.removeItem(items['icon'])
                self.scene.removeItem(items['line'])
                self.scene.removeItem(items['text'])
                if 'class_text' in items:
                    self.scene.removeItem(items['class_text'])
                if 'threat_ring' in items:
                    self.scene.removeItem(items['threat_ring'])
                    self.threat_ring_items.pop(name, None)
                if 'threat_text' in items:
                    self.scene.removeItem(items['threat_text'])
                    if hasattr(self, 'threat_text_items'):
                        self.threat_text_items.pop(name, None)
                for dot in items.get('history_dots', []):
                    self.scene.removeItem(dot)
                for line in items.get('jam_lines', []):
                    self.scene.removeItem(line)

        if not hasattr(self, 'has_centered'):
            if tracks.get('friendlies'):
                f = tracks['friendlies'][0]
                fsx, fsy = self.dcs_to_scene(f['x'], f['z'])
                self.centerOn(fsx, fsy)
                self.has_centered = True
            elif tracks.get('hostiles'):
                h = tracks['hostiles'][0]
                hsx, hsy = self.dcs_to_scene(h['x'], h['z'])
                self.centerOn(hsx, hsy)
                self.has_centered = True
            elif self.airbases:
                ab = next(iter(self.airbases.values()))
                absx, absy = self.dcs_to_scene(ab['x'], ab['z'])
                self.centerOn(absx, absy)
                self.has_centered = True

        valid_selected = []
        for name in self.ordered_selection:
            if name in self.track_items and self.track_items[name]['icon'].isSelected():
                if name in friendly_data:
                    valid_selected.append(friendly_data[name])
                elif name in hostile_data:
                    valid_selected.append(hostile_data[name])
                    
        self.ordered_selection = [f['unit_name'] for f in valid_selected]
                    
        if len(valid_selected) == 2:
            f, h = valid_selected[0], valid_selected[1]
            fsx, fsy = self.dcs_to_scene(f['x'], f['z'])
            hsx, hsy = self.dcs_to_scene(h['x'], h['z'])
            
            self.intercept_line.setLine(fsx, fsy, hsx, hsy)
            self.intercept_line.show()
            
            braa = calculate_braa(f, h)
            bp = self.get_braa_panel()
            bp.update_braa(braa)
            if getattr(bp, 'custom_pos', None):
                bp.move(bp.custom_pos)
            elif not bp.isVisible():
                bp.move(20, self.viewport().height() - bp.height() - 20)
            bp.show()
            bp.raise_()
            
            f_v = math.hypot(f['vx'], f['vz'])
            intercept = geometry.calculate_intercept_heading(f['x'], f['z'], f_v, h['x'], h['z'], h['vx'], h['vz'])
            if intercept:
                cut_hdg, tti_sec, ix, iz = intercept
                isx, isy = self.dcs_to_scene(ix, iz)
                self.impact_point.setPos(isx, isy)
                self.impact_point.show()
                
                ip = self.get_intercept_panel()
                ip.update_intercept(cut_hdg, tti_sec)
                if getattr(ip, 'custom_pos', None):
                    ip.move(ip.custom_pos)
                elif not ip.isVisible():
                    ip.move(self.viewport().width() - ip.width() - 20, self.viewport().height() - ip.height() - 20)
                ip.show()
                ip.raise_()
            else:
                self.impact_point.hide()
                if hasattr(self, 'intercept_panel') and self.intercept_panel:
                    self.intercept_panel.hide()
                
        else:
            self.intercept_line.hide()
            self.impact_point.hide()
            if hasattr(self, 'braa_panel') and self.braa_panel:
                self.braa_panel.hide()
            if hasattr(self, 'intercept_panel') and self.intercept_panel:
                self.intercept_panel.hide()
            
        self._update_conflict_alerts(friendly_data, hostile_data)
        self.refresh_status_panel()

    def _update_conflict_alerts(self, friendly_data, hostile_data):
        if not getattr(self, 'show_conflict_alerts', True):
            return

        active_conflicts = set()
        for f_name, f in friendly_data.items():
            if f.get('category') in [2, 3]:
                continue
            f_sx, f_sy = self.dcs_to_scene(f['x'], f['z'])
            
            best_hostile_name = None
            best_dist = 999999.0
            best_vc = 0
            best_h_data = None
            
            for h_name, h in hostile_data.items():
                if h.get('category') in [2, 3]:
                    continue
                
                vc_kts, dist_nm = geometry.calculate_closure_rate(f, h)
                if dist_nm <= 50.0 and vc_kts >= 300:
                    if dist_nm < best_dist:
                        best_dist = dist_nm
                        best_vc = vc_kts
                        best_hostile_name = h_name
                        best_h_data = h
                        
            if best_hostile_name and best_h_data:
                pair_key = (f_name, best_hostile_name)
                active_conflicts.add(pair_key)
                
                h_sx, h_sy = self.dcs_to_scene(best_h_data['x'], best_h_data['z'])
                
                if best_dist <= 20.0:
                    line_color = QColor(255, 140, 0, 240)
                    pen_width = 2.5
                else:
                    line_color = QColor(240, 220, 60, 200)
                    pen_width = 2.0
                    
                pen = QPen(line_color, pen_width, Qt.PenStyle.DashLine)
                pen.setCosmetic(True)
                
                if pair_key not in self.conflict_items:
                    line_item = self.scene.addLine(0, 0, 0, 0, pen)
                    line_item.setZValue(12)
                    
                    text_item = self.scene.addText("")
                    text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
                    text_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
                    text_item.setZValue(13)
                    
                    self.conflict_items[pair_key] = {
                        'line': line_item,
                        'text': text_item,
                        'last_vc': -1
                    }
                
                c_data = self.conflict_items[pair_key]
                c_data['line'].setPen(pen)
                c_data['line'].setLine(f_sx, f_sy, h_sx, h_sy)
                c_data['line'].show()
                
                mid_x = (f_sx + h_sx) / 2.0
                mid_y = (f_sy + h_sy) / 2.0
                c_data['text'].setPos(mid_x, mid_y)
                c_data['text'].setTransform(QTransform().translate(-15, -10))
                
                if c_data['last_vc'] != best_vc:
                    fs = int(9 * self.font_scale)
                    c_hex = line_color.name()
                    html = f'<span style="font-family:Consolas;font-size:{fs}pt;color:{c_hex};font-weight:bold;">Vc {best_vc}K</span>'
                    c_data['text'].setHtml(html)
                    c_data['last_vc'] = best_vc
                c_data['text'].show()

        to_remove = []
        for pair_key, items in self.conflict_items.items():
            if pair_key not in active_conflicts:
                self.scene.removeItem(items['line'])
                self.scene.removeItem(items['text'])
                to_remove.append(pair_key)
                
        for pair_key in to_remove:
            del self.conflict_items[pair_key]

    def _create_icon_for_prefix(self, prefix, color):
        size = 6
        pen = QPen(color)
        pen.setWidth(0) 
        
        if prefix in ['H', 'B']:
            poly = QPolygonF([
                QPointF(0, -size), QPointF(size, 0),
                QPointF(0, size), QPointF(-size, 0)
            ])
            icon = self.scene.addPolygon(poly, pen, QBrush(Qt.BrushStyle.NoBrush))
        elif prefix == 'U':
            icon = self.scene.addRect(-size, -size, size*2, size*2, pen, QBrush(Qt.BrushStyle.NoBrush))
        else:
            icon = self.scene.addEllipse(-size, -size, size*2, size*2, pen, QBrush(Qt.BrushStyle.NoBrush))
            
        icon.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        icon.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        icon.setZValue(10)
        return icon

    def _update_single_track(self, data, color, is_hostile, prefix='U'):
        name = data['unit_name']
        is_ground = data.get('category') in [2, 3]
        
        sx, sy = self.dcs_to_scene(data['x'], data['z'])
        
        future_x = data['x'] + data['vx'] * 30
        future_z = data['z'] + data['vz'] * 30
        fsx, fsy = self.dcs_to_scene(future_x, future_z)
        
        speed_kts = calculate_speed(data['vx'], data['vz'])
        alt_kft = int((data['y'] * 3.28084) / 1000)
        
        if name not in self.track_items:
            pen = QPen(color)
            pen.setWidth(0)
            icon = self._create_icon_for_prefix(prefix, color)
            
            line = self.scene.addLine(0, 0, 0, 0, pen)
            line.setZValue(5)
            
            text = self.scene.addText("")
            text.setDefaultTextColor(color)
            text.setFont(QFont("Consolas", 10))
            text.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            text.setZValue(15)
            
            class_text = self.scene.addText("")
            class_text.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            class_text.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            class_text.setZValue(15)
            
            self.track_items[name] = {
                'icon': icon, 'line': line, 'text': text, 'class_text': class_text, 
                'history_dots': [], 'is_hostile': is_hostile, 'group_name': data.get('group_name') or name,
                'last_html': '', 'last_prefix': ''
            }
        items = self.track_items[name]
        items['group_name'] = data.get('group_name') or name
        
        if 'class_text' not in items:
            class_text = self.scene.addText("")
            class_text.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            class_text.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            class_text.setZValue(15)
            items['class_text'] = class_text
            
        items['icon'].setPos(sx, sy)
        
        history_points = data.get('history', [])
        while len(items['history_dots']) > len(history_points):
            dot = items['history_dots'].pop()
            self.scene.removeItem(dot)
            
        while len(items['history_dots']) < len(history_points):
            dot = self.scene.addEllipse(-2, -2, 4, 4, QPen(Qt.PenStyle.NoPen), QBrush(color))
            dot.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            dot.setZValue(4)
            items['history_dots'].append(dot)
            
        unit_type = data.get('type') or ''
        threat_nm = geometry.get_sam_threat_range_nm(unit_type)
        if threat_nm:
            radius_m = threat_nm * 1852.0
            if 'threat_ring' not in items:
                ring_pen = QPen(color, 1.5, Qt.PenStyle.DashLine)
                fill_color = QColor(255, 60, 60, 20) if is_hostile else QColor(60, 160, 255, 20)
                ring_brush = QBrush(fill_color)
                ring = self.scene.addEllipse(-radius_m, -radius_m, radius_m * 2, radius_m * 2, ring_pen, ring_brush)
                ring.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
                ring.setZValue(-3)
                items['threat_ring'] = ring
                
                threat_text = self.scene.addText(geometry.get_sam_display_name(unit_type))
                threat_text.setDefaultTextColor(color)
                threat_text.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
                threat_text.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
                threat_text.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
                threat_text.setZValue(-2)
                items['threat_text'] = threat_text
                
            items['threat_ring'].setPos(sx, sy)
            items['threat_ring'].setVisible(self.show_threat_rings)
            self.threat_ring_items[name] = items['threat_ring']
            
            items['threat_text'].setPos(sx, sy)
            items['threat_text'].setTransform(QTransform().translate(5, -15))
            items['threat_text'].setVisible(self.show_threat_rings)
            self.threat_text_items = getattr(self, 'threat_text_items', {})
            self.threat_text_items[name] = items['threat_text']
        else:
            if 'threat_ring' in items:
                self.scene.removeItem(items['threat_ring'])
                del items['threat_ring']
                self.threat_ring_items.pop(name, None)
            if 'threat_text' in items:
                self.scene.removeItem(items['threat_text'])
                del items['threat_text']
                if hasattr(self, 'threat_text_items'):
                    self.threat_text_items.pop(name, None)
                
        is_jammed = data.get('is_jammed', False)
        
        if 'jam_lines' not in items:
            items['jam_lines'] = []
            
        if is_ground:
            items['icon'].hide()
            items['line'].hide()
            items['text'].hide()
            if 'class_text' in items:
                items['class_text'].hide()
            for dot in items.get('history_dots', []):
                dot.hide()
            for l in items['jam_lines']: l.hide()
            return

        if is_jammed:
            jammed_by = data.get('jammed_by', [])
            while len(items['jam_lines']) > len(jammed_by):
                l = items['jam_lines'].pop()
                self.scene.removeItem(l)
            while len(items['jam_lines']) < len(jammed_by):
                pen = QPen(QColor(255, 255, 0, 200), 2, Qt.PenStyle.DashLine)
                l = self.scene.addLine(0, 0, 0, 0, pen)
                l.setZValue(2)
                items['jam_lines'].append(l)
                
            all_tracks = self.backend.get_tracks()
            friendlies = all_tracks.get('friendlies', [])
            for i, friendly_name in enumerate(jammed_by):
                friendly_data = next((f for f in friendlies if f['unit_name'] == friendly_name), None)
                if friendly_data:
                    f_sx, f_sy = self.dcs_to_scene(friendly_data['x'], friendly_data['z'])
                    angle = math.atan2(sy - f_sy, sx - f_sx)
                    end_x = f_sx + math.cos(angle) * 20000
                    end_y = f_sy + math.sin(angle) * 20000
                    items['jam_lines'][i].setLine(f_sx, f_sy, end_x, end_y)
                    items['jam_lines'][i].show()
        else:
            for l in items.get('jam_lines', []):
                l.hide()
            
        items['icon'].show()
        items['line'].show()

        for i, (hx, hz) in enumerate(history_points):
            hsx, hsy = self.dcs_to_scene(hx, hz)
            dot = items['history_dots'][i]
            dot.setPos(hsx, hsy)
            dot.show()
            alpha = int(255 * (i + 1) / len(history_points)) * 0.7
            dot_color = QColor(color)
            dot_color.setAlpha(int(alpha))
            dot.setBrush(QBrush(dot_color))
            
        items['text'].setDefaultTextColor(color)
        if 'class_text' in items:
            items['class_text'].setDefaultTextColor(color)
        
        if items.get('last_prefix') != prefix:
            if 'class_text' in items:
                items['class_text'].setPlainText(prefix)
            was_selected = items['icon'].isSelected() if 'icon' in items else False
            if 'icon' in items and items['icon']:
                self.scene.removeItem(items['icon'])
            items['icon'] = self._create_icon_for_prefix(prefix, color)
            items['icon'].setPos(sx, sy)
            if was_selected:
                items['icon'].setSelected(True)
            items['last_prefix'] = prefix
            
        if 'class_text' in items:
            items['class_text'].setPos(sx, sy)
            items['class_text'].setTransform(QTransform().translate(-4, -18))
        
        items['icon'].setPos(sx, sy)
        items['line'].setLine(sx, sy, fsx, fsy)
        items['text'].setPos(sx, sy)
        items['text'].setTransform(QTransform().translate(15, -10))

        normal_pen = QPen(color)
        normal_pen.setWidth(0)
        if items['icon'].isSelected():
            selected_pen = QPen(color)
            selected_pen.setWidth(2)
            items['icon'].setPen(selected_pen)
            items['line'].setPen(normal_pen)
        else:
            items['icon'].setPen(normal_pen)
            items['line'].setPen(normal_pen)

        label_mode = getattr(self, 'label_mode', 'minimal')
        is_selected = items['icon'].isSelected()

        if label_mode == 'none':
            if is_selected:
                items['text'].setVisible(True)
            else:
                items['text'].setVisible(False)
                return
            is_expanded = True
        else:
            items['text'].setVisible(True)
            is_expanded = (label_mode == 'full') or is_selected or (name in self.expanded_labels) or (name in self.checked_in_tracks)

        tn = geometry.generate_link16_tn(name)
        player_name = data.get('player_name') or ''
        
        if not is_hostile:
            unit_type = data.get('type') or ''
            track_id = f"{tn} / {unit_type}" if unit_type else f"{tn}"
        else:
            tracks = self.backend.get_tracks()
            unit_type_str = self.get_unit_type(data, is_hostile, tracks)
            if unit_type_str and unit_type_str != "UNKNOWN":
                track_id = f"{tn} / {unit_type_str}"
            else:
                track_id = f"{tn}"
        
        fs = int(10 * self.font_scale)
        c_hex = color.name()
        if is_expanded:
            if player_name:
                raw = f"{player_name}<br>{track_id}<br>FL{alt_kft * 10:03d}<br>{speed_kts} GS"
            else:
                raw = f"{track_id}<br>FL{alt_kft * 10:03d}<br>{speed_kts} GS"
        else:
            raw = tn
        label_html = f'<span style="font-family:Consolas;font-size:{fs}pt;color:{c_hex};">{raw}</span>'
        
        if items.get('last_html') != label_html:
            items['text'].setHtml(label_html)
            items['last_html'] = label_html
