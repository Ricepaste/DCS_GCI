import sys
import os
import math
import traceback

def log_global_exception(exc_type, exc_value, exc_tb):
    try:
        base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(__file__)
        log_path = os.path.join(base_dir, "app_crash.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n--- UNHANDLED CRASH [{os.path.basename(sys.executable)}] ---\n")
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    except Exception:
        pass

sys.excepthook = log_global_exception

from PyQt6.QtWidgets import QApplication, QMainWindow, QGraphicsScene, QGraphicsView, QGraphicsItem, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QLabel, QDialog, QFormLayout, QTextEdit, QButtonGroup, QLineEdit, QInputDialog, QListWidget, QMessageBox, QGraphicsTextItem, QTabWidget, QDialogButtonBox, QComboBox
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPolygonF, QPixmap, QImage, QTransform, QCursor, QIcon
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF, QLineF
from backend import GCIBackend
from geometry import calculate_braa, calculate_speed, to_dms, sync_ordered_selection
import geometry

def get_base_dir():
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        if os.path.exists(os.path.join(exe_dir, "map_data")):
            return exe_dir
        if hasattr(sys, '_MEIPASS') and os.path.exists(os.path.join(sys._MEIPASS, "map_data")):
            return sys._MEIPASS
        return exe_dir
    else:
        return os.path.dirname(os.path.abspath(__file__))

class AircraftStatusPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SYS TRACK")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.hide()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(320, 360)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.container = QWidget()
        self.container.setStyleSheet("""
            QWidget {
                background-color: rgba(15, 25, 20, 230);
                border: 1px solid #336666;
                border-radius: 5px;
                color: #55aaaa;
                font-family: Consolas;
            }
        """)
        layout = QVBoxLayout(self.container)
        
        header_layout = QHBoxLayout()
        self.lbl_title = QLabel("SYS TRACK")
        self.lbl_title.setStyleSheet("font-weight: bold; font-size: 16px; border: none; background: transparent;")
        
        self.btn_close = QPushButton("X")
        self.btn_close.setFixedSize(20, 20)
        self.btn_close.setStyleSheet("""
            QPushButton { background-color: transparent; border: none; color: #ff5555; font-weight: bold; }
            QPushButton:hover { background-color: #ff5555; color: white; }
        """)
        self.btn_close.clicked.connect(self.close)
        
        header_layout.addWidget(self.lbl_title)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_close)
        layout.addLayout(header_layout)
        
        # Classification buttons
        class_layout = QHBoxLayout()
        class_layout.setSpacing(5)
        self.btn_fnd = QPushButton("FND")
        self.btn_unk = QPushButton("UNK")
        self.btn_hst = QPushButton("HST")
        self.btn_bnd = QPushButton("BND")
        
        self.class_group = QButtonGroup(self)
        for i, btn in enumerate([self.btn_fnd, self.btn_unk, self.btn_bnd, self.btn_hst]):
            btn.setStyleSheet("""
                QPushButton { background-color: rgba(50,70,70,150); border: 1px solid #558888; color: #a0c0c0; border-radius: 3px; padding: 4px; font-weight: bold; }
                QPushButton:checked { background-color: #55aaaa; color: black; }
            """)
            btn.setCheckable(True)
            self.class_group.addButton(btn, i)
            class_layout.addWidget(btn)
            
        self.class_group.buttonClicked.connect(self.on_class_changed)
        layout.addLayout(class_layout)
        
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #336666; border-radius: 3px; top: -1px; background: transparent; }
            QTabBar::tab { background: rgba(50,70,70,150); color: #a0c0c0; border: 1px solid #336666; padding: 4px 8px; margin-right: 2px; border-top-left-radius: 3px; border-top-right-radius: 3px; font-weight: bold; }
            QTabBar::tab:selected { background: #55aaaa; color: black; }
        """)
        
        self.tab_general = QWidget()
        self.tab_datalink = QWidget()
        
        # --- GENERAL TAB ---
        grid = QFormLayout(self.tab_general)
        grid.setContentsMargins(10, 10, 10, 10)
        grid.setSpacing(8)
        
        self.lbl_callsign = QLabel()
        self.lbl_iff = QLabel()
        self.lbl_type = QLabel()
        self.lbl_alt = QLabel()
        self.lbl_spd = QLabel()
        self.lbl_hdg = QLabel()
        
        val_style = "color: #e0e0e0; font-size: 14px; font-weight: bold; border: none; background: transparent;"
        for lbl in [self.lbl_callsign, self.lbl_iff, self.lbl_type, self.lbl_alt, self.lbl_spd, self.lbl_hdg]:
            lbl.setStyleSheet(val_style)
            
        label_style = "color: #558888; font-size: 12px; border: none; background: transparent;"
        
        def add_row(parent_layout, title, widget):
            l = QLabel(title)
            l.setStyleSheet(label_style)
            parent_layout.addRow(l, widget)
            
        add_row(grid, "CALLSIGN", self.lbl_callsign)
        add_row(grid, "IFF", self.lbl_iff)
        add_row(grid, "TYPE", self.lbl_type)
        add_row(grid, "ALTITUDE", self.lbl_alt)
        add_row(grid, "SPEED", self.lbl_spd)
        add_row(grid, "HEADING", self.lbl_hdg)
        
        # --- DATALINK TAB ---
        dl_layout = QVBoxLayout(self.tab_datalink)
        dl_layout.setContentsMargins(10, 10, 10, 10)
        
        self.lbl_fuel = QLabel("FUEL: N/A")
        self.lbl_fuel.setStyleSheet(val_style)
        dl_layout.addWidget(QLabel("INTERNAL FUEL:", styleSheet=label_style))
        dl_layout.addWidget(self.lbl_fuel)
        
        dl_layout.addSpacing(10)
        dl_layout.addWidget(QLabel("WEAPON STORES:", styleSheet=label_style))
        
        self.list_weapons = QListWidget()
        self.list_weapons.setStyleSheet("""
            QListWidget {
                background: rgba(0,0,0,100); color: #e0e0e0; border: 1px solid #336666; border-radius: 3px; padding: 2px;
                font-size: 13px; font-weight: bold; font-family: Consolas;
            }
        """)
        dl_layout.addWidget(self.list_weapons)
        
        self.tabs.addTab(self.tab_general, "GENERAL")
        self.tabs.addTab(self.tab_datalink, "DATALINK")
        
        layout.addWidget(self.tabs)
        
        notes_lbl = QLabel("REMARKS / NOTES")
        notes_lbl.setStyleSheet(label_style)
        layout.addWidget(notes_lbl)
        
        self.notes_edit = QTextEdit()
        self.notes_edit.setStyleSheet("""
            QTextEdit {
                background-color: rgba(0, 0, 0, 100);
                border: 1px solid #336666;
                border-radius: 5px;
                color: #a0c0c0;
                font-family: Consolas;
                font-size: 13px;
                padding: 5px;
            }
        """)
        layout.addWidget(self.notes_edit)
        
        main_layout.addWidget(self.container)
        
        self.current_unit = None
        self.global_data = {}
        self._is_dragging = False
        self._drag_pos = None

    
    def finalize_airspace_naming(self, name):
        original_name = name
        counter = 1
        while name in self.airspaces:
            name = f"{original_name} ({counter})"
            counter += 1
            
        text_item = self.scene.addText(name)
        text_item.setDefaultTextColor(QColor(255, 200, 200))
        text_item.setZValue(-4)
        from PyQt6.QtGui import QFont
        font = QFont("Consolas", 14, QFont.Weight.Bold)
        text_item.setFont(font)
        
        center = self._temp_airspace_poly.boundingRect().center()
        text_item.setPos(center.x() - text_item.boundingRect().width()/2, center.y() - text_item.boundingRect().height()/2)
        text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        
        self.airspaces[name] = {"poly": self._temp_airspace_item, "text": text_item}
        self._temp_airspace_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        text_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        
        self._is_drawing_airspace = False
        self._current_airspace_pts = []
        self._current_airspace_line = None
        self._temp_airspace_item = None
        self._temp_airspace_poly = None
        self.unsetCursor()
        if hasattr(self, 'main_window'):
            self.main_window.statusBar().showMessage("Airspace saved.")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._drag_pos = event.position().toPoint()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._is_dragging:
            if self.parent():
                self.move(self.mapToParent(event.position().toPoint()) - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._is_dragging = False

    def on_class_changed(self, button):
        if self.current_unit and self.parent():
            cls_str = button.text()
            cls = "FRIENDLY"
            if cls_str == "UNK": cls = "UNKNOWN"
            elif cls_str == "HST": cls = "HOSTILE"
            elif cls_str == "BND": cls = "BANDIT"
            
            if hasattr(self, 'radar') and self.radar:
                self.radar.set_track_classification(self.current_unit, cls)
            elif hasattr(self.parent(), 'set_track_classification'):
                self.parent().set_track_classification(self.current_unit, cls)
            self.refresh_ui_colors(cls)
            
    def refresh_ui_colors(self, cls):
        if cls == "FRIENDLY": color = "#55ffff"
        elif cls == "UNKNOWN": color = "#ffff55"
        elif cls in ["HOSTILE", "BANDIT"]: color = "#ff5555"
        else: color = "#ffffff"
        
        self.lbl_title.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 16px; border: none; background: transparent;")
        self.lbl_callsign.setStyleSheet(f"color: {color}; font-size: 14px; font-weight: bold; border: none; background: transparent;")

    def update_data(self, data, unit_type_str, is_hostile, current_cls):
        name = data['unit_name']
        
        if self.current_unit and self.current_unit != name:
            self.global_data[self.current_unit] = {
                'notes': self.notes_edit.toPlainText()
            }
            
        saved = self.global_data.get(name, {'notes': ''})
        
        if self.current_unit != name:
            self.notes_edit.setPlainText(saved.get('notes', ''))
            
        self.current_unit = name
        
        title = f"TRK {name[-4:]}" if len(name) > 4 else "TRK"
        self.lbl_title.setText(title)
        
        self.lbl_callsign.setText(name)
        
        if is_hostile:
            self.lbl_iff.setText("NO RESPONSE")
            self.lbl_iff.setStyleSheet("color: #ffaa00; font-size: 14px; font-weight: bold; border: none; background: transparent;")
        else:
            self.lbl_iff.setText("M4/5 VALID")
            self.lbl_iff.setStyleSheet("color: #55ff55; font-size: 14px; font-weight: bold; border: none; background: transparent;")
            
        self.class_group.blockSignals(True)
        if current_cls == "FRIENDLY": self.btn_fnd.setChecked(True)
        elif current_cls == "UNKNOWN": self.btn_unk.setChecked(True)
        elif current_cls == "HOSTILE": self.btn_hst.setChecked(True)
        elif current_cls == "BANDIT": self.btn_bnd.setChecked(True)
        self.class_group.blockSignals(False)
        
        self.refresh_ui_colors(current_cls)
            
        self.lbl_type.setText(unit_type_str)
        
        alt_kft = int((data['y'] * 3.28084) / 1000)
        self.lbl_alt.setText(f"FL{alt_kft * 10:03d}")
        
        speed_kts = calculate_speed(data['vx'], data['vz'])
        self.lbl_spd.setText(f"{speed_kts} GS")
        
        hdg_deg = int(math.degrees(data['heading']))
        if hdg_deg < 0: hdg_deg += 360
        self.lbl_hdg.setText(f"{hdg_deg:03d}°")
        
        # Datalink Updates
        is_ground = data.get("category") in [2, 3]
        if is_hostile or is_ground:
            self.lbl_fuel.setText("N/A")
            self.lbl_fuel.setStyleSheet("color: #777777; font-size: 14px; font-weight: bold; border: none; background: transparent;")
            self.list_weapons.clear()
            self.list_weapons.addItem("DATALINK UNAVAILABLE")
        else:
            fuel_frac = data.get("fuel_frac", 0)
            fuel_max_kg = data.get("fuel_mass_max_kg", 0)
            if fuel_frac > 0:
                fuel_pct = int(fuel_frac * 100)
                color = "#55ff55" if fuel_pct >= 50 else ("#ffff55" if fuel_pct >= 30 else "#ff5555")
                
                if fuel_max_kg > 0:
                    current_kg = int(fuel_frac * fuel_max_kg)
                    current_lbs = int(current_kg * 2.20462)
                    self.lbl_fuel.setText(f"{fuel_pct}% ({current_lbs} lbs / {current_kg} kg)")
                else:
                    self.lbl_fuel.setText(f"{fuel_pct}%")
                    
                self.lbl_fuel.setStyleSheet(f"color: {color}; font-size: 14px; font-weight: bold; border: none; background: transparent;")
            else:
                self.lbl_fuel.setText("N/A")
                self.lbl_fuel.setStyleSheet("color: #777777; font-size: 14px; font-weight: bold; border: none; background: transparent;")
                
            weapons = data.get("weapons", [])
            self.list_weapons.clear()
            if weapons:
                for w in weapons:
                    count = w.get("count", 0)
                    name = w.get("name", "Unknown")
                    self.list_weapons.addItem(f"{count:2d} x {name}")
            else:
                self.list_weapons.addItem("CLEAN (NO STORES)")
        
    def closeEvent(self, event):
        if self.current_unit:
            self.global_data[self.current_unit] = {
                'notes': self.notes_edit.toPlainText()
            }
        self.current_unit = None
        super().closeEvent(event)





class AirspaceNameInput(QWidget):
    def __init__(self, radar_view, parent=None):
        super().__init__(parent)
        self.radar_view = radar_view
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(250, 100)
        
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(15, 25, 20, 230);
                border: 1px solid #336666;
                border-radius: 5px;
                color: #55aaaa;
                font-family: Consolas;
            }
            QLineEdit {
                background-color: #0d1a15;
                border: 1px solid #55aaaa;
                color: white;
                padding: 4px;
            }
            QPushButton {
                background-color: #162420;
                border: 1px solid #2a4035;
                color: #b4ffb4;
                padding: 4px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #2a4035;
                border: 1px solid #b4ffb4;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        title = QLabel("Enter Airspace Name:")
        title.setStyleSheet("font-weight: bold; border: none; background: transparent;")
        layout.addWidget(title)
        
        self.input = QLineEdit()
        self.input.returnPressed.connect(self.accept)
        layout.addWidget(self.input)
        
        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton("OK")
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)
        
        self._drag_pos = None
        self._is_dragging = False
        
    
    def finalize_airspace_naming(self, name):
        original_name = name
        counter = 1
        while name in self.airspaces:
            name = f"{original_name} ({counter})"
            counter += 1
            
        text_item = self.scene.addText(name)
        text_item.setDefaultTextColor(QColor(255, 200, 200))
        text_item.setZValue(-4)
        from PyQt6.QtGui import QFont
        font = QFont("Consolas", 14, QFont.Weight.Bold)
        text_item.setFont(font)
        
        center = self._temp_airspace_poly.boundingRect().center()
        text_item.setPos(center.x() - text_item.boundingRect().width()/2, center.y() - text_item.boundingRect().height()/2)
        text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        
        self.airspaces[name] = {"poly": self._temp_airspace_item, "text": text_item}
        self._temp_airspace_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        text_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        
        self._is_drawing_airspace = False
        self._current_airspace_pts = []
        self._current_airspace_line = None
        self._temp_airspace_item = None
        self._temp_airspace_poly = None
        self.unsetCursor()
        if hasattr(self, 'main_window'):
            self.main_window.statusBar().showMessage("Airspace saved.")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._drag_pos = event.position().toPoint()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._is_dragging and self.parent():
            self.move(self.mapToParent(event.position().toPoint()) - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._is_dragging = False
        
    def accept(self):
        name = self.input.text().strip()
        if not name:
            name = f"Airspace {len(self.radar_view.airspaces) + 1}"
        self.radar_view.finalize_airspace_naming(name)
        self.close()
        
    def reject(self):
        if hasattr(self.radar_view, '_temp_airspace_item') and self.radar_view._temp_airspace_item:
            try:
                self.radar_view.scene.removeItem(self.radar_view._temp_airspace_item)
            except:
                pass
        self.radar_view._is_drawing_airspace = False
        self.radar_view._current_airspace_pts = []
        self.radar_view._current_airspace_line = None
        self.radar_view._temp_airspace_item = None
        self.radar_view._temp_airspace_poly = None
        self.radar_view.unsetCursor()
        self.close()

    def showEvent(self, event):
        self.input.setFocus()
        super().showEvent(event)

class AirspaceManagerPanel(QWidget):
    def __init__(self, radar_view, parent=None):
        super().__init__(parent)
        self.radar_view = radar_view
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(300, 400)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.container = QWidget()
        self.container.setStyleSheet("""
            QWidget {
                background-color: rgba(15, 25, 20, 230);
                border: 1px solid #336666;
                border-radius: 5px;
                color: #b4ffb4;
                font-family: Consolas;
            }
            QListWidget {
                background-color: #162420;
                color: #b4ffb4;
                border: 1px solid #2a4035;
            }
            QListWidget::item:selected {
                background-color: #2a4035;
            }
        """)
        
        layout = QVBoxLayout(self.container)
        
        header_layout = QHBoxLayout()
        self.lbl_title = QLabel("Airspace Manager")
        self.lbl_title.setStyleSheet("font-weight: bold; font-size: 14px; border: none; background: transparent;")
        
        self.btn_close = QPushButton("X")
        self.btn_close.setFixedSize(20, 20)
        self.btn_close.setStyleSheet("""
            QPushButton { background-color: transparent; border: none; color: #ff5555; font-weight: bold; }
            QPushButton:hover { background-color: #ff5555; color: white; }
        """)
        self.btn_close.clicked.connect(self.close)
        
        header_layout.addWidget(self.lbl_title)
        header_layout.addStretch()
        header_layout.addWidget(self.btn_close)
        layout.addLayout(header_layout)
        
        self.list_widget = QListWidget()
        self.list_widget.addItems(self.radar_view.airspaces.keys())
        layout.addWidget(self.list_widget)
        
        self.btn_delete = QPushButton("Delete Selected")
        self.btn_delete.setStyleSheet("""
            QPushButton {
                background-color: #aa3333; 
                color: white; 
                border: 1px solid #ff5555;
                padding: 5px; 
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #ff5555;
            }
        """)
        self.btn_delete.clicked.connect(self.delete_selected)
        layout.addWidget(self.btn_delete)
        
        main_layout.addWidget(self.container)
        
        self._drag_pos = None
        self._is_dragging = False
        
    
    def finalize_airspace_naming(self, name):
        original_name = name
        counter = 1
        while name in self.airspaces:
            name = f"{original_name} ({counter})"
            counter += 1
            
        text_item = self.scene.addText(name)
        text_item.setDefaultTextColor(QColor(255, 200, 200))
        text_item.setZValue(-4)
        from PyQt6.QtGui import QFont
        font = QFont("Consolas", 14, QFont.Weight.Bold)
        text_item.setFont(font)
        
        center = self._temp_airspace_poly.boundingRect().center()
        text_item.setPos(center.x() - text_item.boundingRect().width()/2, center.y() - text_item.boundingRect().height()/2)
        text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        
        self.airspaces[name] = {"poly": self._temp_airspace_item, "text": text_item}
        self._temp_airspace_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        text_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        
        self._is_drawing_airspace = False
        self._current_airspace_pts = []
        self._current_airspace_line = None
        self._temp_airspace_item = None
        self._temp_airspace_poly = None
        self.unsetCursor()
        if hasattr(self, 'main_window'):
            self.main_window.statusBar().showMessage("Airspace saved.")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._drag_pos = event.position().toPoint()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._is_dragging and self.parent():
            self.move(self.mapToParent(event.position().toPoint()) - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._is_dragging = False
        
    def delete_selected(self):
        selected = self.list_widget.currentItem()
        if not selected:
            return
        
        name = selected.text()
        if name in self.radar_view.airspaces:
            data = self.radar_view.airspaces[name]
            self.radar_view.scene.removeItem(data['poly'])
            if 'text' in data and data['text']:
                self.radar_view.scene.removeItem(data['text'])
            del self.radar_view.airspaces[name]
            
        self.list_widget.takeItem(self.list_widget.row(selected))


class RadarView(QGraphicsView):
    def __init__(self, backend):
        super().__init__()
        self.backend = backend
        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(-2000000, -2000000, 4000000, 4000000) # 4000km x 4000km
        self.setScene(self.scene)
        
        self.setBackgroundBrush(QBrush(QColor(10, 20, 15)))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 停用內建拖曳，改為手動拖曳
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        
        # 隱藏滾動條，保持畫面潔淨
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        
        self.track_items = {}
        self.checked_in_tracks = set()
        self.ordered_selection = []
        self.track_classifications = {}
        
        self.expanded_labels = set()
        self.global_labels_expanded = False
        
        self.show_airbases = True
        self.airbase_items = []
        self.airbases = {}
        
        self.show_threat_rings = True
        self.threat_ring_items = {}
        self.threat_text_items = {}
        
        # 決定當前要讀取的地圖資料目錄
        base_dir = get_base_dir()
        current_map_path = os.path.join(base_dir, "map_data", "current_map.txt")
        self.current_theatre = "Caucasus"
        if os.path.exists(current_map_path):
            with open(current_map_path, "r", encoding="utf-8") as f:
                self.current_theatre = f.read().strip()
                
        map_data_dir = os.path.join(base_dir, "map_data", self.current_theatre)
        
        # 嘗試讀取匯出的 airbases.csv (覆蓋內建名單)
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
        
        # 建立全局投影基準點 (Global Reference Point)
        # 選擇離所有機場幾何中心最近的機場作為固定投影中心，
        # 最小化橫麥卡托投影在地圖邊緣的失真。
        self.global_ref_point = None
        valid_airbases = [ab for ab in self.airbases.values()
                          if ab.get('lat') is not None and ab.get('lon') is not None]
        if valid_airbases:
            # 計算所有機場 DCS 座標的幾何中心
            avg_x = sum(ab['x'] for ab in valid_airbases) / len(valid_airbases)
            avg_z = sum(ab['z'] for ab in valid_airbases) / len(valid_airbases)
            # 選擇離幾何中心最近的機場
            best = None
            best_dist = float('inf')
            for ab in valid_airbases:
                d = (ab['x'] - avg_x)**2 + (ab['z'] - avg_z)**2
                if d < best_dist:
                    best_dist = d
                    best = ab
            self.global_ref_point = best
                        
        self.draw_airbases()
        
        # --- 繪製海岸線 ---
        coastline_path = os.path.join(map_data_dir, "coastline.csv")
        
        coast_pts = []
        if os.path.exists(coastline_path):
            with open(coastline_path, "r") as f:
                for line in f:
                    if line.strip():
                        parts = line.split(',')
                        if len(parts) == 2:
                            coast_pts.append((float(parts[0]), float(parts[1])))
                            
        # 已移除海洋種子點與洪泛填充邏輯，保留純淨的深色背景與銳利海岸線
                            
        if coast_pts:
            # 獨立繪製海岸線以維持無視窗縮放比例的銳利度
            coast_brush = QBrush(QColor(80, 150, 150)) # 提高亮度的青藍色
            for cx, cz in coast_pts:
                sx, sy = self.dcs_to_scene(cx, cz)
                pt = self.scene.addRect(-1, -1, 2, 2, QPen(Qt.PenStyle.NoPen), coast_brush)
                pt.setPos(sx, sy)
                pt.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
                pt.setZValue(-20)
            
        self.scene.selectionChanged.connect(self.on_selection_changed)
        
        # 攔截線與文字
        self.intercept_line = self.scene.addLine(0, 0, 0, 0, QPen(QColor(255, 255, 0), 0, Qt.PenStyle.DashLine))
        self.intercept_line.setZValue(20)
        self.intercept_line.hide()
        
        # 測距尺 (Ruler)
        self.ruler_line = self.scene.addLine(0, 0, 0, 0, QPen(QColor(180, 255, 180), 0, Qt.PenStyle.DashLine))
        self.ruler_line.setZValue(30)
        self.ruler_line.hide()
        
        self.ruler_text = self.scene.addText("")
        self.ruler_text.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
        self.ruler_text.setDefaultTextColor(QColor(180, 255, 180))
        self.ruler_text.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        self.ruler_text.setZValue(30)
        self.ruler_text.hide()
        
        # OSD: BRAA 面板 (固定於畫面角落)
        self.osd_braa = QLabel(self)
        self.osd_braa.setStyleSheet("color: yellow; font-family: Consolas; font-size: 14px; background-color: rgba(0, 0, 0, 150); padding: 5px; border-radius: 5px;")
        self.osd_braa.setText("")
        self.osd_braa.hide()
        
        # 碰撞預測點 (Impact Point)
        self.impact_point = self.scene.addEllipse(-4, -4, 8, 8, QPen(QColor(255, 150, 50)), QBrush(Qt.BrushStyle.NoBrush))
        self.impact_point.setZValue(25)
        self.impact_point.hide()
        
        # OSD: Intercept 面板
        self.osd_intercept = QLabel(self)
        self.osd_intercept.setStyleSheet("color: #FFAA33; font-family: Consolas; font-size: 14px; background-color: rgba(0, 0, 0, 150); padding: 5px; border-radius: 5px;")
        self.osd_intercept.setText("")
        self.osd_intercept.hide()
        
        self.scale(0.01, 0.01)
        
        # 靶眼標記 (Bullseye)
        self.bullseye_item = self.scene.addEllipse(-10, -10, 20, 20, QPen(QColor(0, 150, 255), 2), QBrush(Qt.BrushStyle.NoBrush))
        self.bullseye_center = self.scene.addEllipse(-2, -2, 4, 4, QPen(Qt.PenStyle.NoPen), QBrush(QColor(0, 150, 255)))
        self.bullseye_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        self.bullseye_center.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        self.bullseye_item.setZValue(5)
        self.bullseye_center.setZValue(5)
        self.bullseye_item.hide()
        self.bullseye_center.hide()
        self.bullseye_pos = None

        # 空域多邊形
        self.airspaces = {}
        self._current_airspace_pts = []
        self._current_airspace_line = None
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_tracks)
        self.timer.start(100)
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 固定在左下角，留出 20px 邊距
        self.osd_braa.move(20, self.viewport().height() - self.osd_braa.height() - 20)
        self.osd_intercept.move(self.viewport().width() - self.osd_intercept.width() - 20, self.viewport().height() - self.osd_intercept.height() - 20)

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
        
        # 繪製動態比例尺 (Scale Bar)
        painter.save()
        painter.setTransform(QTransform()) # 切換回 Viewport 螢幕座標系
        
        pixels_per_meter = self.transform().m11()
        if pixels_per_meter > 0:
            nm_in_meters = 1852.0
            # 常見比例尺級距 (NM)
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

    def draw_airbases(self):
        for name, pos in self.airbases.items():
            sx, sy = self.dcs_to_scene(pos['x'], pos['z'])
            
            # 機場標誌：代表跑道的長條示意圖
            runway_item = self.scene.addRect(-3, -10, 6, 20, QPen(Qt.PenStyle.NoPen), QBrush(QColor(180, 180, 180))) # 淺灰色
            runway_item.setPos(sx, sy)
            # 依據機場跑道真實方位旋轉 (DCS course 為標準數學角度，需加上負號轉為 Qt 螢幕的順時針角度)
            course_deg = pos.get('course', 0)
            runway_item.setRotation(-course_deg)
            runway_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            runway_item.setZValue(-1)
            
            # 機場文字
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
        if hasattr(self, 'main_window'):
            self.main_window.statusBar().showMessage("Click on map to set Bullseye...")

    def toggle_draw_airspace(self):
        self._is_drawing_airspace = True
        self._is_setting_bullseye = False
        self._current_airspace_pts = []
        self.setCursor(Qt.CursorShape.CrossCursor)
        if hasattr(self, 'main_window'):
            self.main_window.statusBar().showMessage("Left click to add points, Right click to finish airspace.")
            
    def toggle_all_labels(self):
        self.global_labels_expanded = not self.global_labels_expanded
        if not self.global_labels_expanded:
            self.expanded_labels.clear() # 關閉全局時，順便重置個別展開狀態
        self.setScene(self.scene)

    def toggle_threat_rings(self):
        self.show_threat_rings = not self.show_threat_rings
        for ellipse in self.threat_ring_items.values():
            ellipse.setVisible(self.show_threat_rings)
        if hasattr(self, 'threat_text_items'):
            for text_item in self.threat_text_items.values():
                text_item.setVisible(self.show_threat_rings)
        if hasattr(self, 'main_window'):
            status = "Threat Rings ON" if self.show_threat_rings else "Threat Rings OFF"
            self.main_window.statusBar().showMessage(status)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_T:
            self.toggle_threat_rings()
        elif event.key() == Qt.Key.Key_B:
            self.toggle_set_bullseye()
        else:
            super().keyPressEvent(event)
        
    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
            
    
    def finalize_airspace_naming(self, name):
        original_name = name
        counter = 1
        while name in self.airspaces:
            name = f"{original_name} ({counter})"
            counter += 1
            
        text_item = self.scene.addText(name)
        text_item.setDefaultTextColor(QColor(255, 200, 200))
        text_item.setZValue(-4)
        from PyQt6.QtGui import QFont
        font = QFont("Consolas", 14, QFont.Weight.Bold)
        text_item.setFont(font)
        
        center = self._temp_airspace_poly.boundingRect().center()
        text_item.setPos(center.x() - text_item.boundingRect().width()/2, center.y() - text_item.boundingRect().height()/2)
        text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        
        self.airspaces[name] = {"poly": self._temp_airspace_item, "text": text_item}
        self._temp_airspace_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        text_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        
        self._is_drawing_airspace = False
        self._current_airspace_pts = []
        self._current_airspace_line = None
        self._temp_airspace_item = None
        self._temp_airspace_poly = None
        self.unsetCursor()
        if hasattr(self, 'main_window'):
            self.main_window.statusBar().showMessage("Airspace saved.")

    def mousePressEvent(self, event):
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
            return
            
        if getattr(self, '_is_drawing_airspace', False):
            if event.button() == Qt.MouseButton.LeftButton:
                pos = self.mapToScene(event.position().toPoint())
                self._current_airspace_pts.append(pos)
                if len(self._current_airspace_pts) > 1:
                    # Draw a temporary line for preview
                    if self._current_airspace_line:
                        self.scene.removeItem(self._current_airspace_line)
                    poly = QPolygonF(self._current_airspace_pts)
                    pen = QPen(QColor(255, 100, 100), 2, Qt.PenStyle.DashLine)
                    pen.setCosmetic(True)
                    self._current_airspace_line = self.scene.addPolygon(poly, pen, QBrush(Qt.BrushStyle.NoBrush))
                    self._current_airspace_line.setZValue(-5)
            elif event.button() == Qt.MouseButton.RightButton:
                if len(self._current_airspace_pts) > 2:
                    if self._current_airspace_line:
                        try:
                            self.scene.removeItem(self._current_airspace_line)
                        except:
                            pass
                        self._current_airspace_line = None
                    
                    self._is_drawing_airspace = False
                    
                    poly = QPolygonF(self._current_airspace_pts)
                    pen = QPen(QColor(255, 100, 100), 2)
                    pen.setCosmetic(True)
                    item = self.scene.addPolygon(poly, pen, QBrush(QColor(255, 100, 100, 50)))
                    item.setZValue(-5)
                    
                    self._temp_airspace_poly = poly
                    self._temp_airspace_item = item
                    
                    if not hasattr(self, 'name_input') or not self.name_input:
                        parent_widget = self.main_window.centralWidget() if hasattr(self, 'main_window') else self
                        self.name_input = AirspaceNameInput(self, parent_widget)
                        
                    self.name_input.input.clear()
                    self.name_input.show()
                    self.name_input.raise_()
                    # Center the input dialog in the view
                    vp_rect = self.viewport().rect()
                    self.name_input.move(vp_rect.center().x() - 125, vp_rect.center().y() - 50)
                return

        if event.button() == Qt.MouseButton.RightButton:
            self._is_ruler = True
            self._ruler_start = self.mapToScene(event.position().toPoint())
            self.ruler_line.setLine(self._ruler_start.x(), self._ruler_start.y(), self._ruler_start.x(), self._ruler_start.y())
            self.ruler_line.show()
            self.ruler_text.setPlainText("")
            self.ruler_text.setPos(self._ruler_start)
            self.ruler_text.show()
            return

            
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.position().toPoint())
            is_track_click = False
            if item:
                for name, items in self.track_items.items():
                    if item == items['icon'] or item == items['text'] or item == items.get('class_text'):
                        if name in self.expanded_labels:
                            self.expanded_labels.remove(name)
                        else:
                            self.expanded_labels.add(name)
                        is_track_click = True
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
            # 使用全局固定基準點進行座標投影 (消除動態切換導致的座標偏差)
            ref = getattr(self, 'global_ref_point', None)
            
            if ref:
                lat, lon = geometry.dcs_to_latlon(dcs_dx, dcs_dz, ref['x'], ref['z'], ref['lat'], ref['lon'])
                latlon_str = geometry.to_dms(lat, True) + " " + geometry.to_dms(lon, False)
                mgrs_str = geometry.latlon_to_mgrs(lat, lon)
                
                be_str = ""
                if hasattr(self, 'bullseye_pos') and self.bullseye_pos:
                    # 使用測地線 (Geodesic) 計算真實方位與距離
                    bx = -self.bullseye_pos.y()
                    bz = self.bullseye_pos.x()
                    # DCS 網格方位 (Grid Bearing) — 與 DCS F10 地圖一致
                    dx = dcs_dx - bx  # 北向差 (DCS X)
                    dz = dcs_dz - bz  # 東向差 (DCS Z)
                    brg = (math.degrees(math.atan2(dz, dx)) + 360) % 360
                    rng = math.hypot(dx, dz) / 1852.0
                    be_str = f" | B/E: {int(brg):03d}° / {rng:.1f} NM"
                
                self.main_window.statusBar().showMessage(f"Cursor: {latlon_str} | MGRS: {mgrs_str}{be_str}")
            else:
                self.main_window.statusBar().showMessage("Cursor: No Reference Data")

        if getattr(self, '_is_drawing_airspace', False) and len(self._current_airspace_pts) > 0:
            preview_pts = self._current_airspace_pts + [current_pos]
            if self._current_airspace_line:
                self.scene.removeItem(self._current_airspace_line)
            poly = QPolygonF(preview_pts)
            pen = QPen(QColor(255, 100, 100), 2, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            self._current_airspace_line = self.scene.addPolygon(poly, pen, QBrush(Qt.BrushStyle.NoBrush))
            self._current_airspace_line.setZValue(-5)

        if getattr(self, '_is_panning', False):
            delta = event.position().toPoint() - self._pan_start
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            self._pan_start = event.position().toPoint()
            return
        elif getattr(self, '_is_ruler', False):
            self.ruler_line.setLine(self._ruler_start.x(), self._ruler_start.y(), current_pos.x(), current_pos.y())
            
            # 起點與終點的 DCS 座標 (DCS X=北, Z=東, 單位=公尺)
            start_dcs_dz = self._ruler_start.x()
            start_dcs_dx = -self._ruler_start.y()
            end_dcs_dz = current_pos.x()
            end_dcs_dx = -current_pos.y()
            
            # DCS 網格航向 (Grid Bearing) — 與 DCS F10 地圖尺規一致
            # DCS 的座標網格本身就是其地圖投影，F10 尺規直接用 atan2 計算
            r_dx = end_dcs_dx - start_dcs_dx  # 北向差 (DCS X)
            r_dz = end_dcs_dz - start_dcs_dz  # 東向差 (DCS Z)
            hdg = (math.degrees(math.atan2(r_dz, r_dx)) + 360) % 360
            dist_nm = math.hypot(r_dx, r_dz) / 1852.0
            
            # 磁偏角表 (近似值，適用於各戰區)
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
        elif event.button() == Qt.MouseButton.RightButton and getattr(self, '_is_ruler', False):
            self._is_ruler = False
            self.ruler_line.hide()
            self.ruler_text.hide()
            return
        super().mouseReleaseEvent(event)
        
    def mouseDoubleClickEvent(self, event):
        item = self.itemAt(event.position().toPoint())
        if item:
            for name, items in self.track_items.items():
                if item == items['icon'] or item == items['text'] or item == items.get('class_text'):
                    self.open_status_panel(name)
                    break
        super().mouseDoubleClickEvent(event)
        
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete or event.key() == Qt.Key.Key_Backspace:
            for item in self.scene.selectedItems():
                self.scene.removeItem(item)
        super().keyPressEvent(event)

    def set_track_classification(self, name, cls):
        self.track_classifications[name] = cls
        self.update_tracks()

    def get_track_classification(self, name, default_is_hostile):
        # DCS Hostiles default to UNKNOWN, Friendlies default to FRIENDLY
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
        if not hasattr(self, 'status_panel'):
            self.status_panel = AircraftStatusPanel(self.main_window.centralWidget() if hasattr(self, "main_window") else self)
            self.status_panel.setParent(self.main_window.centralWidget() if hasattr(self, "main_window") else self)
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
        self.status_panel.show()
        self.status_panel.raise_()
        # self.status_panel.activateWindow()
            
    def on_selection_changed(self):
        current_selected = self.scene.selectedItems()
        current_names = []
        for name, items in self.track_items.items():
            if items['icon'] in current_selected:
                current_names.append(name)
                
        self.ordered_selection = sync_ordered_selection(self.ordered_selection, current_names)

    def toggle_selected_friendly(self):
        # 透過按鈕來切換選中友軍的標記狀態
        for name, items in self.track_items.items():
            if items['icon'].isSelected() and not items['is_hostile']:
                if name in self.checked_in_tracks:
                    self.checked_in_tracks.remove(name)
                else:
                    self.checked_in_tracks.add(name)
        # 立即更新畫面顏色
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

        # 自動置中於第一個可用的單位或機場 (僅執行一次)
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
            elif tracks.get('airbases'):
                ab = tracks['airbases'][0]
                absx, absy = self.dcs_to_scene(ab['x'], ab['z'])
                self.centerOn(absx, absy)
                self.has_centered = True

        # 處理點擊選取與 BRAA 引導線
        # 我們只過濾目前確實還處於 selected 狀態的項目，避免不同步
        valid_selected = []
        for name in self.ordered_selection:
            if name in self.track_items and self.track_items[name]['icon'].isSelected():
                if name in friendly_data:
                    valid_selected.append(friendly_data[name])
                elif name in hostile_data:
                    valid_selected.append(hostile_data[name])
                    
        # 更新 ordered_selection 確保只保留有效的
        self.ordered_selection = [f['unit_name'] for f in valid_selected]
                    
        # 如果恰好選中任意兩個目標，畫出連線與 BRAA
        if len(valid_selected) == 2:
            # 絕對遵循點擊順序：第一點擊為基準 (起點)，第二點擊為目標 (終點)
            f, h = valid_selected[0], valid_selected[1]
            
            fsx, fsy = self.dcs_to_scene(f['x'], f['z'])
            hsx, hsy = self.dcs_to_scene(h['x'], h['z'])
            
            self.intercept_line.setLine(fsx, fsy, hsx, hsy)
            self.intercept_line.show()
            
            # 計算 BRAA
            braa = calculate_braa(f, h)
            info = f"BRAA:\nBRG: {braa['bearing']:03d}°\nRNG: {braa['range']} NM\nALT: FL{braa['altitude']//100:03d}\nASP: {braa['aspect']}"
            
            # 顯示在 OSD 面板上
            self.osd_braa.setText(info)
            self.osd_braa.adjustSize()
            self.osd_braa.move(20, self.viewport().height() - self.osd_braa.height() - 20)
            self.osd_braa.show()
            
            # 攔截碰撞計算
            f_v = math.hypot(f['vx'], f['vz'])
            intercept = geometry.calculate_intercept_heading(f['x'], f['z'], f_v, h['x'], h['z'], h['vx'], h['vz'])
            if intercept:
                cut_hdg, tti_sec, ix, iz = intercept
                isx, isy = self.dcs_to_scene(ix, iz)
                self.impact_point.setPos(isx, isy)
                self.impact_point.show()
                
                int_info = f"INTERCEPT:\nCUT: {int(cut_hdg):03d}°\nTTI: {int(tti_sec//60):02d}:{int(tti_sec%60):02d}"
                self.osd_intercept.setText(int_info)
                self.osd_intercept.adjustSize()
                self.osd_intercept.move(self.viewport().width() - self.osd_intercept.width() - 20, self.viewport().height() - self.osd_intercept.height() - 20)
                self.osd_intercept.show()
            else:
                self.impact_point.hide()
                self.osd_intercept.hide()
                
        else:
            self.intercept_line.hide()
            self.impact_point.hide()
            self.osd_braa.hide()
            self.osd_intercept.hide()
            
        self.refresh_status_panel()

    def _create_icon_for_prefix(self, prefix, color):
        size = 6
        pen = QPen(color)
        pen.setWidth(0) 
        
        if prefix in ['H', 'B']: # Hostile/Bandit -> Diamond
            poly = QPolygonF([
                QPointF(0, -size), QPointF(size, 0),
                QPointF(0, size), QPointF(-size, 0)
            ])
            icon = self.scene.addPolygon(poly, pen, QBrush(Qt.BrushStyle.NoBrush))
        elif prefix == 'U': # Unknown -> Square
            icon = self.scene.addRect(-size, -size, size*2, size*2, pen, QBrush(Qt.BrushStyle.NoBrush))
        else: # Friendly -> Circle
            icon = self.scene.addEllipse(-size, -size, size*2, size*2, pen, QBrush(Qt.BrushStyle.NoBrush))
            
        icon.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        icon.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable) # 允許選取
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
                'history_dots': [], 'is_hostile': is_hostile,
                'last_html': '', 'last_prefix': ''
            }
        items = self.track_items[name]
        
        if 'class_text' not in items:
            class_text = self.scene.addText("")
            class_text.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            class_text.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            class_text.setZValue(15)
            items['class_text'] = class_text
            
        items['icon'].setPos(sx, sy)
        
        # 繪製歷史殘影 (Track Trails)
        history_points = data.get('history', [])
        # 確保殘影數量正確，多餘的刪除，不足的補上
        while len(items['history_dots']) > len(history_points):
            dot = items['history_dots'].pop()
            self.scene.removeItem(dot)
            
        while len(items['history_dots']) < len(history_points):
            dot = self.scene.addEllipse(-2, -2, 4, 4, QPen(Qt.PenStyle.NoPen), QBrush(color))
            dot.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            dot.setZValue(4)
            items['history_dots'].append(dot)
            
        # 繪製 SAM 導彈威脅圈 (Threat Rings)
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
                
                # Create text label for the SAM
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
            
            # Position text near the center
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
                
        # ECM Jamming Logic & 地面單位過濾
        is_jammed = data.get('is_jammed', False)
        
        # 處理 Jam lines 初始化
        if 'jam_lines' not in items:
            items['jam_lines'] = []
            
        if is_jammed or is_ground:
            items['icon'].hide()
            items['line'].hide()
            items['text'].hide()
            if 'class_text' in items:
                items['class_text'].hide()
            for dot in items.get('history_dots', []):
                dot.hide()
            
            # 針對 ECM 開啟的干擾目標，畫出從預警機出發的干擾射線
            if is_jammed and not is_ground:
                jammed_by = data.get('jammed_by', [])
                # 確保線條數量
                while len(items['jam_lines']) > len(jammed_by):
                    l = items['jam_lines'].pop()
                    self.scene.removeItem(l)
                while len(items['jam_lines']) < len(jammed_by):
                    pen = QPen(QColor(255, 255, 0, 200), 2, Qt.PenStyle.DashLine)
                    l = self.scene.addLine(0, 0, 0, 0, pen)
                    l.setZValue(2)
                    items['jam_lines'].append(l)
                    
                # 更新干擾線的位置
                all_tracks = self.backend.get_tracks()
                friendlies = all_tracks.get('friendlies', [])
                for i, friendly_name in enumerate(jammed_by):
                    friendly_data = next((f for f in friendlies if f['unit_name'] == friendly_name), None)
                    if friendly_data:
                        f_sx, f_sy = self.dcs_to_scene(friendly_data['x'], friendly_data['z'])
                        # 射線延伸到很遠的地方 (模擬無限遠)
                        # 從友軍座標往敵軍座標的方向拉長 20000 像素
                        angle = math.atan2(sy - f_sy, sx - f_sx)
                        end_x = f_sx + math.cos(angle) * 20000
                        end_y = f_sy + math.sin(angle) * 20000
                        items['jam_lines'][i].setLine(f_sx, f_sy, end_x, end_y)
                        items['jam_lines'][i].show()
            else:
                for l in items['jam_lines']: l.hide()
            return
            
        # 如果不是被干擾也不是地面單位，清除干擾射線並顯示圖示
        for l in items.get('jam_lines', []): l.hide()
            
        items['icon'].show()
        items['line'].show()

        # 更新殘影位置與透明度
        for i, (hx, hz) in enumerate(history_points):
            hsx, hsy = self.dcs_to_scene(hx, hz)
            dot = items['history_dots'][i]
            dot.setPos(hsx, hsy)
            dot.show()
            # 越舊的點越透明
            alpha = int(255 * (i + 1) / len(history_points)) * 0.7
            dot_color = QColor(color)
            dot_color.setAlpha(int(alpha))
            dot.setBrush(QBrush(dot_color))
            
        # 動態更新文字與連線顏色 (可能因為右鍵報到或 ROE 宣告而改變)
        items['text'].setDefaultTextColor(color)
        if 'class_text' in items:
            items['class_text'].setDefaultTextColor(color)
        
        if items.get('last_prefix') != prefix:
            if 'class_text' in items:
                items['class_text'].setPlainText(prefix)
            # 重新建立對應形狀的圖示 (Hostile/Bandit -> 菱形, Unknown -> 正方形, Friendly -> 圓形)
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
        
        # 判斷是否展開字卡 (全域開啟 或 個別被點擊展開 或 處於接管狀態)
        is_expanded = self.global_labels_expanded or (name in self.expanded_labels) or (name in self.checked_in_tracks)
        
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
        
        if is_expanded:
            if player_name:
                label_html = f"{player_name}<br>{track_id}<br>FL{alt_kft * 10:03d}<br>{speed_kts} GS"
            else:
                label_html = f"{track_id}<br>FL{alt_kft * 10:03d}<br>{speed_kts} GS"
        else:
            if player_name:
                label_html = f"{player_name}<br>{track_id}"
            else:
                label_html = f"{track_id}"
            
        # 繪製選取狀態
        normal_pen = QPen(color)
        normal_pen.setWidth(0)
        
        if items['icon'].isSelected():
            selected_pen = QPen(color)
            selected_pen.setWidth(2)
            items['icon'].setPen(selected_pen)
            items['line'].setPen(normal_pen) # 保持速度向量粗細正常，避免被隱藏或過粗
        else:
            items['icon'].setPen(normal_pen)
            items['line'].setPen(normal_pen)
            
        items['line'].setLine(sx, sy, fsx, fsy)
        items['text'].setPos(sx, sy)
        items['text'].setTransform(QTransform().translate(15, -10))
        
        if items.get('last_html') != label_html:
            items['text'].setHtml(label_html)
            items['last_html'] = label_html

def create_sidebar_icon(shape_type):
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(180, 255, 180, 255))
    pen.setWidth(2)
    painter.setPen(pen)
    
    if shape_type == "mark":
        painter.drawEllipse(6, 6, 20, 20)
        painter.drawLine(16, 2, 16, 10)
        painter.drawLine(16, 22, 16, 30)
        painter.drawLine(2, 16, 10, 16)
        painter.drawLine(22, 16, 30, 16)
    elif shape_type == "airbase":
        painter.drawLine(8, 28, 24, 4)
        painter.drawLine(14, 28, 30, 4)
    elif shape_type == "label":
        painter.drawRect(4, 10, 24, 12)
        painter.drawLine(8, 16, 20, 16)
    elif shape_type == "grid":
        painter.drawRect(4, 4, 24, 24)
        painter.drawLine(16, 4, 16, 28)
        painter.drawLine(4, 16, 28, 16)
    elif shape_type == "bullseye":
        painter.drawEllipse(6, 6, 20, 20)
        painter.drawEllipse(14, 14, 4, 4)
    elif shape_type == "airspace":
        painter.drawLine(4, 28, 16, 4)
        painter.drawLine(16, 4, 28, 28)
        painter.drawLine(28, 28, 4, 28)
    elif shape_type == "manager":
        painter.drawRect(4, 4, 24, 24)
        painter.drawLine(8, 10, 24, 10)
        painter.drawLine(8, 16, 24, 16)
        painter.drawLine(8, 22, 24, 22)
    elif shape_type == "threat":
        painter.drawEllipse(4, 4, 24, 24)
        painter.drawEllipse(10, 10, 12, 12)
        painter.drawEllipse(14, 14, 4, 4)
    elif shape_type == "coalition":
        # Draw a two-shield or two-flag icon
        painter.drawRect(4, 6, 10, 20)
        painter.drawRect(18, 6, 10, 20)
    
    painter.end()
    return QIcon(pixmap)

class GCIMainWindow(QMainWindow):
    def __init__(self, backend):
        super().__init__()
        self.backend = backend
        c_name = getattr(self.backend, 'coalition', 'blue').upper()
        self.setWindowTitle(f"DCS External GCI (LotATC Lite) - [{c_name} COALITION]")
        self.resize(1200, 800)
        
        main_widget = QWidget()
        layout = QHBoxLayout(main_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 雷達主畫面
        self.radar = RadarView(backend)
        self.radar.main_window = self
        self.setWindowTitle(f"DCS External GCI (LotATC Lite) - {self.radar.current_theatre} [{c_name}]")
        
        layout.addWidget(self.radar, stretch=1)
        
        # 控制面板 (窄邊條)
        sidebar = QVBoxLayout()
        sidebar.setContentsMargins(8, 8, 8, 8)
        sidebar.setSpacing(12)
        
        button_style = """
            QPushButton {
                background-color: #162420;
                border: 1px solid #2a4035;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #2a4035;
                border: 1px solid #b4ffb4;
            }
            QPushButton:pressed {
                background-color: #b4ffb4;
            }
        """
        
        self.btn_mark = QPushButton()
        self.btn_mark.setIcon(create_sidebar_icon("mark"))
        self.btn_mark.setToolTip("標記友軍 (Toggle Control) - 點擊友軍後按此按鈕以標記接管狀態")
        self.btn_mark.setFixedSize(45, 45)
        self.btn_mark.setStyleSheet(button_style)
        self.btn_mark.clicked.connect(self.radar.toggle_selected_friendly)
        
        self.btn_toggle_airbases = QPushButton()
        self.btn_toggle_airbases.setIcon(create_sidebar_icon("airbase"))
        self.btn_toggle_airbases.setToolTip("顯示/隱藏機場與跑道 (Declutter)")
        self.btn_toggle_airbases.setFixedSize(45, 45)
        self.btn_toggle_airbases.setStyleSheet(button_style)
        self.btn_toggle_airbases.clicked.connect(self.radar.toggle_airbases)
        
        self.btn_toggle_threats = QPushButton()
        self.btn_toggle_threats.setIcon(create_sidebar_icon("threat"))
        self.btn_toggle_threats.setToolTip("顯示/隱藏 SAM 導彈威脅圈 (Threat Rings) [快捷鍵 T]")
        self.btn_toggle_threats.setFixedSize(45, 45)
        self.btn_toggle_threats.setStyleSheet(button_style)
        self.btn_toggle_threats.clicked.connect(self.radar.toggle_threat_rings)
        
        self.btn_toggle_coalition = QPushButton()
        self.btn_toggle_coalition.setIcon(create_sidebar_icon("coalition"))
        self.btn_toggle_coalition.setToolTip("切換 GCI 觀看陣營 (BLUE / RED)")
        self.btn_toggle_coalition.setFixedSize(45, 45)
        self.btn_toggle_coalition.setStyleSheet(button_style)
        self.btn_toggle_coalition.clicked.connect(self.toggle_gci_coalition)
        
        self.btn_toggle_labels = QPushButton()
        self.btn_toggle_labels.setIcon(create_sidebar_icon("label"))
        self.btn_toggle_labels.setToolTip("顯示/隱藏所有航跡詳細字卡")
        self.btn_toggle_labels.setFixedSize(45, 45)
        self.btn_toggle_labels.setStyleSheet(button_style)
        self.btn_toggle_labels.clicked.connect(self.radar.toggle_all_labels)
        
        self.btn_set_bullseye = QPushButton()
        self.btn_set_bullseye.setIcon(create_sidebar_icon("bullseye"))
        self.btn_set_bullseye.setToolTip("自定義靶眼位置 (Bullseye)")
        self.btn_set_bullseye.setFixedSize(45, 45)
        self.btn_set_bullseye.setStyleSheet(button_style)
        self.btn_set_bullseye.clicked.connect(self.toggle_set_bullseye)
        
        self.btn_draw_airspace = QPushButton()
        self.btn_draw_airspace.setIcon(create_sidebar_icon("airspace"))
        self.btn_draw_airspace.setToolTip("手繪空域 (ROZ/CAP)")
        self.btn_draw_airspace.setFixedSize(45, 45)
        self.btn_draw_airspace.setStyleSheet(button_style)
        self.btn_draw_airspace.clicked.connect(self.toggle_draw_airspace)
        
        self.btn_manage_airspace = QPushButton()
        self.btn_manage_airspace.setIcon(create_sidebar_icon("manager"))
        self.btn_manage_airspace.setToolTip("管理與刪除空域")
        self.btn_manage_airspace.setFixedSize(45, 45)
        self.btn_manage_airspace.setStyleSheet(button_style)
        self.btn_manage_airspace.clicked.connect(self.open_airspace_manager)
        
        sidebar.addWidget(self.btn_mark)
        sidebar.addWidget(self.btn_toggle_airbases)
        sidebar.addWidget(self.btn_toggle_threats)
        sidebar.addWidget(self.btn_toggle_coalition)
        sidebar.addWidget(self.btn_toggle_labels)
        sidebar.addWidget(self.btn_set_bullseye)
        sidebar.addWidget(self.btn_draw_airspace)
        sidebar.addWidget(self.btn_manage_airspace)
        sidebar.addStretch()
        
        layout.addLayout(sidebar)
        self.setCentralWidget(main_widget)

    def toggle_gci_coalition(self):
        new_c = "red" if getattr(self.backend, 'coalition', 'blue') == "blue" else "blue"
        self.backend.set_coalition(new_c)
        c_upper = new_c.upper()
        self.statusBar().showMessage(f"GCI Coalition switched to: {c_upper}")
        self.setWindowTitle(f"DCS External GCI (LotATC Lite) - {self.radar.current_theatre} [{c_upper}]")

    def toggle_set_bullseye(self):
        self.radar._is_setting_bullseye = True
        self.radar._is_drawing_airspace = False
        self.radar.setCursor(Qt.CursorShape.CrossCursor)
        self.statusBar().showMessage("Click on map to set Bullseye...")

    def toggle_draw_airspace(self):
        self.radar._is_drawing_airspace = True
        self.radar._is_setting_bullseye = False
        self.radar._current_airspace_pts = []
        self.radar.setCursor(Qt.CursorShape.CrossCursor)
        self.statusBar().showMessage("Left click to add points, Right click to finish airspace.")

    def open_airspace_manager(self):
        if not hasattr(self, "manager_panel") or not self.manager_panel:
            self.manager_panel = AirspaceManagerPanel(self.radar, self.centralWidget())
        else:
            self.manager_panel.list_widget.clear()
            self.manager_panel.list_widget.addItems(self.radar.airspaces.keys())
        self.manager_panel.show()
        self.manager_panel.raise_()
        self.manager_panel.move(50, 50)
        # dialog.exec()

def create_gci_cursor():
    cursor_size = 20
    pixmap = QPixmap(cursor_size, cursor_size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # 純圓形白亮綠色游標
    pen = QPen(QColor(180, 255, 180, 255))
    pen.setWidth(2)
    painter.setPen(pen)
    
    c = cursor_size / 2
    painter.drawEllipse(QPointF(c, c), 7, 7)
    painter.end()
    
    return QCursor(pixmap, hotX=int(c), hotY=int(c))

class NetworkDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GCI Network Setup")
        self.setFixedSize(400, 250)
        self.mode = "standalone"
        self.coalition = "blue"
        
        layout = QVBoxLayout(self)
        
        self.lbl_info = QLabel("Select Mode & Coalition:")
        layout.addWidget(self.lbl_info)
        
        mode_layout = QHBoxLayout()
        self.btn_standalone = QPushButton("Standalone (Local)")
        self.btn_client = QPushButton("Client (Connect)")
        self.btn_host = QPushButton("Host (Server)")
        
        self.btn_standalone.setCheckable(True)
        self.btn_client.setCheckable(True)
        self.btn_host.setCheckable(True)
        self.btn_standalone.setChecked(True)
        
        self.btn_standalone.clicked.connect(self.set_standalone_mode)
        self.btn_client.clicked.connect(self.set_client_mode)
        self.btn_host.clicked.connect(self.set_host_mode)
        
        mode_layout.addWidget(self.btn_standalone)
        mode_layout.addWidget(self.btn_client)
        mode_layout.addWidget(self.btn_host)
        layout.addLayout(mode_layout)
        
        form_layout = QFormLayout()
        self.ip_input = QLineEdit("127.0.0.1 (Direct UDP)")
        self.ip_input.setEnabled(False)
        self.port_input = QLineEdit("10088")
        
        self.coalition_combo = QComboBox()
        self.coalition_combo.addItem("BLUE (NATO)", "blue")
        self.coalition_combo.addItem("RED (Warsaw)", "red")
        
        form_layout.addRow("Host IP (Hamachi):", self.ip_input)
        form_layout.addRow("Port (UDP/TCP):", self.port_input)
        form_layout.addRow("GCI Coalition:", self.coalition_combo)
        layout.addLayout(form_layout)
        
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)
        
    def accept(self):
        self.coalition = self.coalition_combo.currentData()
        super().accept()
        
    def set_standalone_mode(self):
        self.mode = "standalone"
        self.btn_standalone.setChecked(True)
        self.btn_client.setChecked(False)
        self.btn_host.setChecked(False)
        self.ip_input.setEnabled(False)
        self.ip_input.setText("127.0.0.1 (Direct UDP)")
        
    def set_client_mode(self):
        self.mode = "client"
        self.btn_standalone.setChecked(False)
        self.btn_client.setChecked(True)
        self.btn_host.setChecked(False)
        self.ip_input.setEnabled(True)
        self.ip_input.setText("127.0.0.1")
        
    def set_host_mode(self):
        self.mode = "host"
        self.btn_standalone.setChecked(False)
        self.btn_client.setChecked(False)
        self.btn_host.setChecked(True)
        self.ip_input.setEnabled(False)
        self.ip_input.setText("0.0.0.0 (Local Server)")

def run_app():
    try:
        app = QApplication(sys.argv)
        app.setOverrideCursor(create_gci_cursor())
        
        dialog = NetworkDialog()
        if dialog.exec() != QDialog.DialogCode.Accepted:
            sys.exit(0)
            
        mode = dialog.mode
        port = int(dialog.port_input.text())
        coalition = dialog.coalition
        
        if mode == "standalone":
            backend = GCIBackend(host="127.0.0.1", port=port, coalition=coalition, protocol="udp")
        elif mode == "host":
            from backend import GCIServer
            server = GCIServer(tcp_host="0.0.0.0", tcp_port=port, udp_port=port)
            server.start()
            backend = GCIBackend(host="127.0.0.1", port=port, coalition=coalition, protocol="tcp")
        else:
            ip = dialog.ip_input.text()
            backend = GCIBackend(host=ip, port=port, coalition=coalition, protocol="tcp")
            
        backend.start()
        
        window = GCIMainWindow(backend)
        window.show()
        
        sys.exit(app.exec())
    except Exception as e:
        log_global_exception(*sys.exc_info())
        raise e

if __name__ == "__main__":
    run_app()
