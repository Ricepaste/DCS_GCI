import math
import os
import json
from PyQt6.QtWidgets import (
    QWidget, QDialog, QSpinBox, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QTextEdit, QTabWidget, QFormLayout, QButtonGroup,
    QInputDialog, QMessageBox, QFileDialog, QLineEdit
)
from PyQt6.QtGui import QColor, QPen, QBrush, QFont
from PyQt6.QtCore import Qt, QPointF
import geometry
from geometry import calculate_speed

class DraggableInfoCard(QLabel):
    def __init__(self, key_name="", parent=None):
        super().__init__(parent)
        self.key_name = key_name
        self._drag_pos = None
        self._is_dragging = False
        self.custom_pos = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._drag_pos = event.position().toPoint()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._is_dragging:
            if self.parent():
                new_pos = self.mapToParent(event.position().toPoint()) - self._drag_pos
                self.move(new_pos)
                self.custom_pos = new_pos
            event.accept()

    def mouseReleaseEvent(self, event):
        self._is_dragging = False

class BraaInfoPanel(QWidget):
    BASE_W, BASE_H = 210, 130

    def __init__(self, parent=None):
        super().__init__(parent)
        self.font_scale = 1.0
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(self.BASE_W, self.BASE_H)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.container = QWidget()
        self._apply_container_style(11)
        
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)
        
        self.header = QLabel("BRAA READOUT")
        self.header.setStyleSheet("color: #00e6ff; font-weight: bold; border-bottom: 1px solid #2a4035; padding-bottom: 2px;")
        layout.addWidget(self.header)
        
        self.lbl_bearing  = QLabel("BEARING:  ---\u00b0")
        self.lbl_range    = QLabel("RANGE:    --- NM")
        self.lbl_altitude = QLabel("ALTITUDE: ---")
        self.lbl_aspect   = QLabel("ASPECT:   ---")
        
        for lbl in [self.lbl_bearing, self.lbl_range, self.lbl_altitude, self.lbl_aspect]:
            lbl.setStyleSheet("color: #b4ffb4; font-weight: bold;")
            layout.addWidget(lbl)
        
        main_layout.addWidget(self.container)
        
        self._drag_pos = None
        self._is_dragging = False
        self.custom_pos = None

    def _apply_container_style(self, fs):
        self.container.setStyleSheet(f"""
            QWidget {{
                background-color: rgba(10, 20, 15, 235);
                border: 1px solid #2a4035;
                border-radius: 4px;
                font-family: Consolas;
                font-size: {fs}px;
            }}
            QLabel {{
                font-family: Consolas;
                font-size: {fs}px;
                color: #b4ffb4;
                border: none;
                background: transparent;
            }}
        """)

    def update_font_scale(self, scale):
        self.font_scale = scale
        fs = int(11 * scale)
        self._apply_container_style(fs)
        self.setFixedSize(int(self.BASE_W * scale), int(self.BASE_H * scale))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._drag_pos = event.position().toPoint()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._is_dragging and self.parent():
            new_pos = self.mapToParent(event.position().toPoint()) - self._drag_pos
            self.move(new_pos)
            self.custom_pos = new_pos
            event.accept()

    def mouseReleaseEvent(self, event):
        self._is_dragging = False

    def update_braa(self, braa):
        self.lbl_bearing.setText(f"BEARING:  {braa['bearing']:03d}°")
        self.lbl_range.setText(f"RANGE:    {braa['range']} NM")
        self.lbl_altitude.setText(f"ALTITUDE: FL{braa['altitude']//100:03d}")
        self.lbl_aspect.setText(f"ASPECT:   {braa['aspect']}")

class InterceptInfoPanel(QWidget):
    BASE_W, BASE_H = 210, 95

    def __init__(self, parent=None):
        super().__init__(parent)
        self.font_scale = 1.0
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(self.BASE_W, self.BASE_H)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.container = QWidget()
        self._apply_container_style(11)
        
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)
        
        self.header = QLabel("INTERCEPT SOLUTION")
        self.header.setStyleSheet("color: #ffaa00; font-weight: bold; border-bottom: 1px solid #2a4035; padding-bottom: 2px;")
        layout.addWidget(self.header)
        
        self.lbl_cut = QLabel("CUT HEADING: ---\u00b0")
        self.lbl_tti = QLabel("TIME TO INT: ---")
        
        for lbl in [self.lbl_cut, self.lbl_tti]:
            lbl.setStyleSheet("color: #ffaa00; font-weight: bold;")
            layout.addWidget(lbl)
        
        main_layout.addWidget(self.container)
        
        self._drag_pos = None
        self._is_dragging = False
        self.custom_pos = None

    def _apply_container_style(self, fs):
        self.container.setStyleSheet(f"""
            QWidget {{
                background-color: rgba(10, 20, 15, 235);
                border: 1px solid #2a4035;
                border-radius: 4px;
                font-family: Consolas;
                font-size: {fs}px;
            }}
            QLabel {{
                font-family: Consolas;
                font-size: {fs}px;
                color: #ffaa00;
                border: none;
                background: transparent;
            }}
        """)

    def update_font_scale(self, scale):
        self.font_scale = scale
        fs = int(11 * scale)
        self._apply_container_style(fs)
        self.setFixedSize(int(self.BASE_W * scale), int(self.BASE_H * scale))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._drag_pos = event.position().toPoint()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._is_dragging and self.parent():
            new_pos = self.mapToParent(event.position().toPoint()) - self._drag_pos
            self.move(new_pos)
            self.custom_pos = new_pos
            event.accept()

    def mouseReleaseEvent(self, event):
        self._is_dragging = False

    def update_intercept(self, cut_hdg, tti_sec):
        self.lbl_cut.setText(f"CUT HEADING: {int(cut_hdg):03d}°")
        self.lbl_tti.setText(f"TIME TO INT: {int(tti_sec//60):02d}:{int(tti_sec%60):02d}")

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
        self.lbl_title.setStyleSheet("font-weight: bold; border: none; background: transparent;")
        
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
        
        grid = QFormLayout(self.tab_general)
        grid.setContentsMargins(10, 10, 10, 10)
        grid.setSpacing(8)
        
        self.lbl_callsign = QLabel()
        self.lbl_iff = QLabel()
        self.lbl_type = QLabel()
        self.lbl_alt = QLabel()
        self.lbl_spd = QLabel()
        self.lbl_hdg = QLabel()
        
        val_style = "color: #e0e0e0; font-weight: bold; border: none; background: transparent;"
        for lbl in [self.lbl_callsign, self.lbl_iff, self.lbl_type, self.lbl_alt, self.lbl_spd, self.lbl_hdg]:
            lbl.setStyleSheet(val_style)
            
        label_style = "color: #558888; border: none; background: transparent;"
        
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

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._drag_pos = event.position().toPoint()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._is_dragging:
            if self.parent():
                new_pos = self.mapToParent(event.position().toPoint()) - self._drag_pos
                self.move(new_pos)
                self.custom_pos = new_pos
            event.accept()

    def mouseReleaseEvent(self, event):
        self._is_dragging = False

    def on_class_changed(self, button):
        if self.current_unit:
            cls_str = button.text()
            cls = "FRIENDLY"
            if cls_str == "UNK": cls = "UNKNOWN"
            elif cls_str == "HST": cls = "HOSTILE"
            elif cls_str == "BND": cls = "BANDIT"
            elif cls_str == "FND": cls = "FRIENDLY"
            
            if hasattr(self, 'radar') and self.radar:
                self.radar.set_track_classification(self.current_unit, cls)
            elif self.parent() and hasattr(self.parent(), 'set_track_classification'):
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
        
        tn = geometry.generate_link16_tn(name)
        title = f"TRK #{tn}"
        self.lbl_title.setText(title)
        
        self.lbl_callsign.setText(name)
        
        if is_hostile:
            self.lbl_iff.setText("NO RESPONSE")
            self.lbl_iff.setStyleSheet("color: #ffaa00; font-weight: bold; border: none; background: transparent;")
        else:
            self.lbl_iff.setText("M4/5 VALID")
            self.lbl_iff.setStyleSheet("color: #55ff55; font-weight: bold; border: none; background: transparent;")
            
        self.class_group.blockSignals(True)
        if current_cls == "FRIENDLY": self.btn_fnd.setChecked(True)
        elif current_cls == "UNKNOWN": self.btn_unk.setChecked(True)
        elif current_cls == "HOSTILE": self.btn_hst.setChecked(True)
        elif current_cls == "BANDIT": self.btn_bnd.setChecked(True)
        self.class_group.blockSignals(False)
        
        self.refresh_ui_colors(current_cls)
            
        self.lbl_type.setText(unit_type_str)
        
        alt_kft = int((data.get('y', 0) * 3.28084) / 1000)
        self.lbl_alt.setText(f"FL{alt_kft * 10:03d}")
        
        speed_kts = calculate_speed(data.get('vx', 0), data.get('vz', 0))
        self.lbl_spd.setText(f"{speed_kts} GS")
        
        heading_rad = data.get('heading')
        if heading_rad is None:
            vx = data.get('vx', 0)
            vz = data.get('vz', 0)
            if vx != 0 or vz != 0:
                heading_rad = math.atan2(vz, vx)
            else:
                heading_rad = 0
        hdg_deg = int(math.degrees(heading_rad)) % 360
        self.lbl_hdg.setText(f"{hdg_deg:03d}°")
        
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
                    
                self.lbl_fuel.setStyleSheet(f"color: {color}; font-weight: bold; border: none; background: transparent;")
            else:
                self.lbl_fuel.setText("N/A")
                self.lbl_fuel.setStyleSheet("color: #777777; font-weight: bold; border: none; background: transparent;")
                
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

def get_styled_input_text(parent, title, prompt, default_text=""):
    dialog = QInputDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setLabelText(prompt)
    dialog.setTextValue(default_text)
    dialog.setStyleSheet("""
        QDialog { background-color: #101e19; color: #b4ffb4; border: 1px solid #2a4035; font-family: Consolas; }
        QLabel { color: #00e6ff; font-family: Consolas; font-weight: bold; font-size: 12px; }
        QLineEdit { background-color: #162420; color: #ffffff; border: 1px solid #2a4035; border-radius: 4px; padding: 4px; font-family: Consolas; font-size: 12px; }
        QPushButton { background-color: #162420; color: #b4ffb4; border: 1px solid #2a4035; border-radius: 4px; padding: 6px 12px; font-family: Consolas; font-weight: bold; }
        QPushButton:hover { background-color: #2a4035; border: 1px solid #b4ffb4; }
    """)
    ok = dialog.exec()
    return dialog.textValue(), ok == QInputDialog.DialogCode.Accepted

def get_styled_input_double(parent, title, prompt, value=30.0, min_v=1.0, max_v=500.0, decimals=1):
    dialog = QInputDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setLabelText(prompt)
    dialog.setDoubleValue(value)
    dialog.setDoubleRange(min_v, max_v)
    dialog.setDoubleDecimals(decimals)
    dialog.setStyleSheet("""
        QDialog { background-color: #101e19; color: #b4ffb4; border: 1px solid #2a4035; font-family: Consolas; }
        QLabel { color: #00e6ff; font-family: Consolas; font-weight: bold; font-size: 12px; }
        QDoubleSpinBox { background-color: #162420; color: #ffffff; border: 1px solid #2a4035; border-radius: 4px; padding: 4px; font-family: Consolas; font-size: 12px; }
        QPushButton { background-color: #162420; color: #b4ffb4; border: 1px solid #2a4035; border-radius: 4px; padding: 6px 12px; font-family: Consolas; font-weight: bold; }
        QPushButton:hover { background-color: #2a4035; border: 1px solid #b4ffb4; }
    """)
    ok = dialog.exec()
    return dialog.doubleValue(), ok == QInputDialog.DialogCode.Accepted

class VectorParamsDialog(QDialog):
    def __init__(self, current_alt_ft=20000, current_spd_kts=350, parent=None):
        super().__init__(parent)
        self.setWindowTitle("VECTOR PARAMS SETUP")
        self.setFixedSize(320, 180)
        self.setStyleSheet("""
            QDialog { background-color: #101e19; color: #b4ffb4; border: 1px solid #2a4035; font-family: Consolas; }
            QLabel { color: #00e6ff; font-family: Consolas; font-weight: bold; font-size: 11px; }
            QSpinBox { background-color: #162420; color: #ffffff; border: 1px solid #2a4035; border-radius: 4px; padding: 4px; font-family: Consolas; font-size: 11px; }
            QPushButton { background-color: #162420; color: #b4ffb4; border: 1px solid #2a4035; border-radius: 4px; padding: 6px 12px; font-family: Consolas; font-weight: bold; }
            QPushButton:hover { background-color: #2a4035; border: 1px solid #b4ffb4; }
        """)
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        from PyQt6.QtWidgets import QSpinBox
        self.spin_alt = QSpinBox()
        self.spin_alt.setRange(1000, 60000)
        self.spin_alt.setSingleStep(1000)
        self.spin_alt.setValue(int(current_alt_ft))
        self.spin_alt.setSuffix(" ft")
        
        self.spin_spd = QSpinBox()
        self.spin_spd.setRange(100, 1200)
        self.spin_spd.setSingleStep(10)
        self.spin_spd.setValue(int(current_spd_kts))
        self.spin_spd.setSuffix(" kts")
        
        form.addRow("TARGET ALTITUDE:", self.spin_alt)
        form.addRow("TARGET SPEED:", self.spin_spd)
        layout.addLayout(form)
        
        btn_box = QHBoxLayout()
        btn_ok = QPushButton("CONFIRM VECTOR")
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("CANCEL")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_ok)
        btn_box.addWidget(btn_cancel)
        layout.addLayout(btn_box)

    def get_values(self):
        return self.spin_alt.value(), self.spin_spd.value()


class AirspaceNameInput(QDialog):
    def __init__(self, radar_view, parent=None):
        super().__init__(parent)
        self.radar_view = radar_view
        self.selected_color = QColor(255, 100, 100)
        # FramelessWindowHint: no OS title bar / taskbar entry
        # parent=main_window means Qt positions it over the main window (not a separate system window)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        # Do NOT use WA_TranslucentBackground — container stylesheet handles background
        self.setFixedSize(280, 170)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.container = QWidget()
        self.container.setStyleSheet("""
            QWidget {
                background-color: rgba(10, 20, 15, 245);
                border: 1px solid #2e5548;
                border-radius: 5px;
                color: #b4ffb4;
                font-family: Consolas;
            }
            QLabel {
                font-family: Consolas;
                font-size: 11px;
                color: #b4ffb4;
                border: none;
                background: transparent;
            }
            QLineEdit {
                background-color: #162420;
                border: 1px solid #2a4035;
                color: #ffffff;
                padding: 4px;
                border-radius: 3px;
                font-family: Consolas;
                font-size: 11px;
            }
            QPushButton {
                background-color: #162420;
                border: 1px solid #2a4035;
                color: #b4ffb4;
                padding: 5px;
                border-radius: 3px;
                font-family: Consolas;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #2a4035;
                border: 1px solid #b4ffb4;
            }
        """)
        
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        
        title = QLabel("AIRSPACE DESIGNATION")
        title.setStyleSheet("color: #00e6ff; font-weight: bold; font-size: 11px; border-bottom: 1px solid #2a4035; padding-bottom: 2px;")
        layout.addWidget(title)
        
        self.input = QLineEdit()
        self.input.setPlaceholderText("Enter Airspace Name (e.g. ROZ ALPHA)")
        self.input.returnPressed.connect(self.accept)
        layout.addWidget(self.input)
        
        color_layout = QHBoxLayout()
        self.btn_color = QPushButton("Select Airspace Color")
        self.btn_color.clicked.connect(self.choose_color)
        color_layout.addWidget(self.btn_color)
        layout.addLayout(color_layout)
        
        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton("CONFIRM")
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel = QPushButton("CANCEL")
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)
        
        main_layout.addWidget(self.container)
        
        self._drag_pos = None
        self._is_dragging = False

    def choose_color(self):
        from PyQt6.QtWidgets import QColorDialog
        # Use radar_view as parent so OS dialog isn't blocked by this embedded QWidget
        color = QColorDialog.getColor(self.selected_color, self.radar_view, "Select Airspace Color")
        if color.isValid():
            self.selected_color = color
            self.btn_color.setStyleSheet(
                f"background-color: {color.name()}; color: #ffffff; font-weight: bold; border: 1px solid #ffffff;"
            )


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
        self.radar_view.finalize_airspace_naming(name, self.selected_color)
        from PyQt6.QtWidgets import QApplication
        QApplication.restoreOverrideCursor()
        super().accept()

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
        self.radar_view.viewport().unsetCursor()
        from PyQt6.QtWidgets import QApplication
        QApplication.restoreOverrideCursor()
        super().reject()

    def showEvent(self, event):
        self.input.setFocus()
        super().showEvent(event)

class AirspaceManagerPanel(QWidget):
    BASE_W, BASE_H = 300, 420

    def __init__(self, radar_view, parent=None):
        super().__init__(parent)
        self.radar_view = radar_view
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(self.BASE_W, self.BASE_H)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.container = QWidget()
        self._apply_container_style(10)
        
        layout = QVBoxLayout(self.container)
        
        header_layout = QHBoxLayout()
        self.lbl_title = QLabel("Airspace Manager")
        self.lbl_title.setStyleSheet("font-weight: bold; border: none; background: transparent;")
        
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
        
        btn_layout = QHBoxLayout()
        self.btn_export = QPushButton("Export JSON")
        self.btn_export.setStyleSheet("""
            QPushButton { background-color: #2a4035; color: #b4ffb4; border: 1px solid #336666; padding: 4px; font-weight: bold; border-radius: 4px; }
            QPushButton:hover { background-color: #336666; color: white; }
        """)
        self.btn_export.clicked.connect(self.export_airspaces_json)
        
        self.btn_import = QPushButton("Import JSON")
        self.btn_import.setStyleSheet("""
            QPushButton { background-color: #2a4035; color: #b4ffb4; border: 1px solid #336666; padding: 4px; font-weight: bold; border-radius: 4px; }
            QPushButton:hover { background-color: #336666; color: white; }
        """)
        self.btn_import.clicked.connect(self.import_airspaces_json)
        
        btn_layout.addWidget(self.btn_export)
        btn_layout.addWidget(self.btn_import)
        layout.addLayout(btn_layout)
        
        action_layout = QHBoxLayout()
        self.btn_change_color = QPushButton("🎨 Change Color")
        self.btn_change_color.setStyleSheet("""
            QPushButton { background-color: #2a4035; color: #b4ffb4; border: 1px solid #336666; padding: 5px; font-weight: bold; border-radius: 4px; }
            QPushButton:hover { background-color: #336666; color: white; }
        """)
        self.btn_change_color.clicked.connect(self.change_color_selected)

        self.btn_delete = QPushButton("Delete Selected")
        self.btn_delete.setStyleSheet("""
            QPushButton { background-color: #aa3333; color: white; border: 1px solid #ff5555; padding: 5px; font-weight: bold; border-radius: 4px; }
            QPushButton:hover { background-color: #ff5555; }
        """)
        self.btn_delete.clicked.connect(self.delete_selected)
        
        action_layout.addWidget(self.btn_change_color)
        action_layout.addWidget(self.btn_delete)
        layout.addLayout(action_layout)
        
        main_layout.addWidget(self.container)

    def _apply_container_style(self, fs):
        self.container.setStyleSheet(f"""
            QWidget {{
                background-color: rgba(15, 25, 20, 230);
                border: 1px solid #336666;
                border-radius: 5px;
                font-family: Consolas;
                font-size: {fs}px;
            }}
            QListWidget {{
                background-color: #162420;
                color: #b4ffb4;
                border: 1px solid #2a4035;
                font-size: {fs}px;
            }}
            QListWidget::item:selected {{
                background-color: #2a4035;
            }}
        """)

    def update_font_scale(self, scale):
        fs = int(10 * scale)
        self._apply_container_style(fs)
        self.resize(int(self.BASE_W * scale), int(self.BASE_H * scale))

    def change_color_selected(self):
        current_item = self.list_widget.currentItem()
        if not current_item:
            return
        name = current_item.text()
        if name in self.radar_view.airspaces:
            data = self.radar_view.airspaces[name]
            curr_color = QColor(data.get('color_hex', '#ff6464'))
            from PyQt6.QtWidgets import QColorDialog
            color = QColorDialog.getColor(curr_color, self, f"Change Color for '{name}'")
            if color.isValid():
                data['color_hex'] = color.name()
                if 'poly' in data and data['poly']:
                    pen = QPen(color, 2)
                    pen.setCosmetic(True)
                    fill_color = QColor(color.red(), color.green(), color.blue(), 50)
                    data['poly'].setPen(pen)
                    data['poly'].setBrush(QBrush(fill_color))
                if 'text' in data and data['text']:
                    data['text'].setDefaultTextColor(color)

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

    def export_airspaces_json(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Export Airspaces", "airspaces_config.json", "JSON Files (*.json)")
        if filepath:
            data_to_save = {}
            for name, data in self.radar_view.airspaces.items():
                pts = []
                poly = data.get('poly')
                if poly:
                    polygon = poly.polygon()
                    for i in range(polygon.count()):
                        pt = polygon.at(i)
                        pts.append({'x': pt.x(), 'y': pt.y()})
                color_hex = data.get('color_hex', '#ff6464')
                data_to_save[name] = {'points': pts, 'color': color_hex}
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=2, ensure_ascii=False)
            QMessageBox.information(self, "Export Success", f"Airspaces exported to {os.path.basename(filepath)}")

    def import_airspaces_json(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Import Airspaces", "", "JSON Files (*.json)")
        if filepath and os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for name, info in data.items():
                    pts = [QPointF(p['x'], p['y']) for p in info.get('points', [])]
                    c_hex = info.get('color', '#ff6464')
                    if len(pts) >= 3:
                        self.radar_view.create_airspace_from_points(name, pts, QColor(c_hex))
                self.list_widget.clear()
                self.list_widget.addItems(self.radar_view.airspaces.keys())
                QMessageBox.information(self, "Import Success", f"Imported airspaces from {os.path.basename(filepath)}")
            except Exception as e:
                QMessageBox.warning(self, "Import Failed", f"Could not import file: {e}")
