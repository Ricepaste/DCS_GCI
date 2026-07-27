from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QPushButton, QLabel, QComboBox, QScrollArea
)
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QPen, QColor, QFont
from PyQt6.QtCore import Qt, QSize

from ui.radar_view import RadarView, get_base_dir
from ui.panels import AirspaceManagerPanel

def create_sidebar_icon(shape_type):
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter()
    if painter.begin(pixmap):
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
    elif shape_type == "threat_custom":
        painter.drawEllipse(4, 4, 24, 24)
        painter.drawLine(4, 16, 28, 16)
        painter.drawLine(16, 4, 16, 28)
    elif shape_type == "pin":
        painter.drawEllipse(10, 4, 12, 12)
        painter.drawLine(16, 16, 16, 28)
    elif shape_type == "coalition":
        painter.drawRect(4, 6, 10, 20)
        painter.drawRect(18, 6, 10, 20)
    elif shape_type == "conflict":
        painter.drawLine(4, 4, 28, 28)
        painter.drawLine(4, 28, 28, 4)
        painter.drawEllipse(11, 11, 10, 10)
    
    if painter.isActive():
        painter.end()
    return QIcon(pixmap)

def create_sidebar_button(shape_type, label_text, tooltip):
    btn = QPushButton(label_text)
    btn.setIcon(create_sidebar_icon(shape_type))
    btn.setToolTip(tooltip)
    btn.setFixedSize(86, 55)
    btn.setProperty("shape_type", shape_type)
    btn.setStyleSheet("""
        QPushButton {
            background-color: #162420;
            border: 1px solid #2a4035;
            border-radius: 4px;
            color: #b4ffb4;
            font-family: Consolas;
            font-size: 11px;
            font-weight: bold;
            text-align: center;
            padding-top: 2px;
        }
        QPushButton:hover {
            background-color: #2a4035;
            border: 1px solid #b4ffb4;
            color: #ffffff;
        }
        QPushButton:pressed {
            background-color: #b4ffb4;
            color: #000000;
        }
    """)
    return btn

def create_sidebar_group_label(title):
    lbl = QLabel(title)
    lbl.setStyleSheet("""
        QLabel {
            color: #558877;
            font-family: Consolas;
            font-size: 11px;
            font-weight: bold;
            padding-top: 4px;
            padding-bottom: 2px;
            border-bottom: 1px solid #2a4035;
        }
    """)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return lbl

class GCIMainWindow(QMainWindow):
    def __init__(self, backend):
        super().__init__()
        self.backend = backend
        c_name = getattr(self.backend, 'coalition', 'blue').upper()
        self.setWindowTitle(f"DCS External GCI (LotATC Lite) - [{c_name} COALITION]")
        self.resize(1240, 850)
        
        main_widget = QWidget()
        layout = QHBoxLayout(main_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.radar = RadarView(backend)
        self.radar.main_window = self
        self.setWindowTitle(f"DCS External GCI (LotATC Lite) - {self.radar.current_theatre} [{c_name}]")
        
        layout.addWidget(self.radar, stretch=1)
        
        sidebar_scroll = QScrollArea()
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sidebar_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        sidebar_scroll.setStyleSheet("""
            QScrollArea {
                background-color: #0d1714;
                border: none;
                border-left: 1px solid #2a4035;
            }
            QScrollBar:vertical {
                background-color: #0d1714;
                width: 6px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background-color: #2a4035;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #b4ffb4;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        sidebar_widget = QWidget()
        sidebar_widget.setStyleSheet("background-color: #0d1714;")
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(6, 6, 6, 6)
        sidebar_layout.setSpacing(6)
        
        sidebar_layout.addWidget(create_sidebar_group_label("DISPLAY"))
        grid_display = QGridLayout()
        grid_display.setSpacing(4)
        
        self.btn_toggle_airbases = create_sidebar_button("airbase", "BASE", "顯示/隱藏機場與跑道 (Declutter)")
        self.btn_toggle_airbases.clicked.connect(self.radar.toggle_airbases)
        
        self.btn_toggle_labels = create_sidebar_button("label", "LABEL", "字卡模式循環: MINIMAL (僅TN) → FULL (全展開) → NONE (無字卡) → MINIMAL")
        self.btn_toggle_labels.clicked.connect(self.radar.toggle_all_labels)
        
        self.btn_toggle_threats = create_sidebar_button("threat", "SAM", "顯示/隱藏 SAM 導彈威脅圈 (Threat Rings) [快捷鍵 T]")
        self.btn_toggle_threats.clicked.connect(self.radar.toggle_threat_rings)
        
        self.btn_toggle_conflicts = create_sidebar_button("conflict", "VC ALERT", "顯示/隱藏 交戰衝突接近率連線 (Conflict Alert) [快捷鍵 C]")
        self.btn_toggle_conflicts.clicked.connect(self.radar.toggle_conflict_alerts)
        
        grid_display.addWidget(self.btn_toggle_airbases, 0, 0)
        grid_display.addWidget(self.btn_toggle_labels, 0, 1)
        grid_display.addWidget(self.btn_toggle_threats, 1, 0)
        grid_display.addWidget(self.btn_toggle_conflicts, 1, 1)
        sidebar_layout.addLayout(grid_display)
        
        sidebar_layout.addWidget(create_sidebar_group_label("TOOLS"))
        grid_tools = QGridLayout()
        grid_tools.setSpacing(4)
        
        self.btn_draw_airspace = create_sidebar_button("airspace", "ZONE", "手繪劃定戰術空域 (ROZ/CAP)")
        self.btn_draw_airspace.clicked.connect(self.toggle_draw_airspace)

        self.btn_draw_custom_threat = create_sidebar_button("threat_custom", "R-RING", "手繪威脅圈 (Custom Threat Ring)")
        self.btn_draw_custom_threat.clicked.connect(self.radar.toggle_draw_custom_threat_circle)

        self.btn_add_marker = create_sidebar_button("pin", "TAC PIN", "放置戰術地標標記 (TacPen Marker)")
        self.btn_add_marker.clicked.connect(self.radar.toggle_add_tactical_marker)

        self.btn_set_bullseye = create_sidebar_button("bullseye", "BULLS", "自定義靶眼位置 (Bullseye)")
        self.btn_set_bullseye.clicked.connect(self.toggle_set_bullseye)

        grid_tools.addWidget(self.btn_draw_airspace, 0, 0)
        grid_tools.addWidget(self.btn_draw_custom_threat, 0, 1)
        grid_tools.addWidget(self.btn_add_marker, 1, 0)
        grid_tools.addWidget(self.btn_set_bullseye, 1, 1)
        sidebar_layout.addLayout(grid_tools)

        sidebar_layout.addWidget(create_sidebar_group_label("CONTROL"))
        grid_control = QGridLayout()
        grid_control.setSpacing(4)
        
        self.btn_mark = create_sidebar_button("mark", "CHECK", "標記友軍 (Toggle Control) - 點擊友軍後按此按鈕標記接管")
        self.btn_mark.clicked.connect(self.radar.toggle_selected_friendly)

        self.btn_toggle_coalition = create_sidebar_button("coalition", "SIDE", "切換 GCI 觀看陣營 (BLUE / RED)")
        self.btn_toggle_coalition.clicked.connect(self.toggle_gci_coalition)

        self.btn_manage_airspace = create_sidebar_button("manager", "MANAGE", "管理與刪除空域 / 導出導入 JSON")
        self.btn_manage_airspace.clicked.connect(self.open_airspace_manager)

        self.font_combo = QComboBox()
        self.font_combo.addItems(["100%", "110%", "120%", "130%", "150%", "175%"])
        self.font_combo.setToolTip("調整 UI 與字體縮放比例 (適配大螢幕/4K)")
        self.font_combo.setFixedSize(68, 44)
        self.font_combo.setStyleSheet("""
            QComboBox {
                background-color: #162420; color: #b4ffb4; border: 1px solid #2a4035;
                font-family: Consolas; font-weight: bold; border-radius: 4px; font-size: 10px;
                padding-left: 6px;
            }
            QComboBox QAbstractItemView {
                background-color: #162420; color: #b4ffb4; selection-background-color: #2a4035;
            }
        """)
        self.font_combo.currentIndexChanged.connect(self.on_font_scale_changed)

        grid_control.addWidget(self.btn_mark, 0, 0)
        grid_control.addWidget(self.btn_toggle_coalition, 0, 1)
        grid_control.addWidget(self.btn_manage_airspace, 1, 0)
        grid_control.addWidget(self.font_combo, 1, 1)
        sidebar_layout.addLayout(grid_control)

        sidebar_layout.addStretch()
        sidebar_scroll.setWidget(sidebar_widget)
        self.sidebar_scroll = sidebar_scroll
        
        layout.addWidget(sidebar_scroll)
        self.setCentralWidget(main_widget)
        
        self.apply_ui_scale(1.0)

    def on_font_scale_changed(self, index):
        scales = [1.0, 1.1, 1.2, 1.3, 1.5, 1.75]
        if 0 <= index < len(scales):
            self.apply_ui_scale(scales[index])

    def apply_ui_scale(self, scale):
        self._ui_scale = scale
        btn_w = int(86 * scale)
        btn_h = int(55 * scale)
        combo_h = int(55 * scale)
        combo_w = int(86 * scale)
        scroll_w = int(200 * scale)
        base_font_pt = int(10 * scale)
        btn_font_pt = int(11 * scale)
        icon_size = int(24 * scale)

        if hasattr(self, 'sidebar_scroll') and self.sidebar_scroll:
            self.sidebar_scroll.setFixedWidth(scroll_w)

        from PyQt6.QtWidgets import QApplication
        app_font = QFont("Consolas", base_font_pt)
        QApplication.instance().setFont(app_font)

        sidebar_buttons = [
            self.btn_mark, self.btn_toggle_airbases, self.btn_toggle_threats, self.btn_toggle_conflicts,
            self.btn_draw_custom_threat, self.btn_add_marker, self.btn_toggle_coalition,
            self.btn_toggle_labels, self.btn_set_bullseye, self.btn_draw_airspace,
            self.btn_manage_airspace,
        ]
        for btn in sidebar_buttons:
            btn.setFixedSize(btn_w, btn_h)
            btn.setIconSize(QSize(icon_size, icon_size))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #162420;
                    border: 1px solid #2a4035;
                    border-radius: 4px;
                    color: #b4ffb4;
                    font-family: Consolas;
                    font-size: {btn_font_pt}px;
                    font-weight: bold;
                    text-align: center;
                    padding-top: 2px;
                }}
                QPushButton:hover {{
                    background-color: #2a4035;
                    border: 1px solid #b4ffb4;
                    color: #ffffff;
                }}
                QPushButton:pressed {{
                    background-color: #b4ffb4;
                    color: #000000;
                }}
            """)

        self.font_combo.setFixedSize(combo_w, combo_h)
        self.font_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: #162420; color: #b4ffb4; border: 1px solid #2a4035;
                font-family: Consolas; font-weight: bold; border-radius: 4px;
                font-size: {base_font_pt}px;
                padding-left: 6px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #162420; color: #b4ffb4; selection-background-color: #2a4035;
                font-size: {base_font_pt}px;
            }}
        """)

        self.radar.set_font_scale(scale)

        if hasattr(self, 'manager_panel') and self.manager_panel:
            self.manager_panel.update_font_scale(scale)

    def toggle_gci_coalition(self):
        new_c = "red" if getattr(self.backend, 'coalition', 'blue') == "blue" else "blue"
        self.backend.set_coalition(new_c)
        c_upper = new_c.upper()
        self.statusBar().showMessage(f"GCI Coalition switched to: {c_upper}")
        self.setWindowTitle(f"DCS External GCI (LotATC Lite) - {self.radar.current_theatre} [{c_upper}]")

    def toggle_set_bullseye(self):
        self.radar.toggle_set_bullseye()

    def toggle_draw_airspace(self):
        self.radar.toggle_draw_airspace()

    def open_airspace_manager(self):
        if not hasattr(self, "manager_panel") or not self.manager_panel:
            self.manager_panel = AirspaceManagerPanel(self.radar, self.centralWidget())
        else:
            self.manager_panel.list_widget.clear()
            self.manager_panel.list_widget.addItems(self.radar.airspaces.keys())
        self.manager_panel.show()
        self.manager_panel.raise_()
        self.manager_panel.move(50, 50)
