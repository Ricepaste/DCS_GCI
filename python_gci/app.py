import sys
import os
import math
from PyQt6.QtWidgets import QApplication, QMainWindow, QGraphicsScene, QGraphicsView, QGraphicsItem, QVBoxLayout, QHBoxLayout, QWidget, QPushButton
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPolygonF, QPixmap, QImage
from PyQt6.QtCore import Qt, QTimer, QPointF
from backend import GCIBackend
from geometry import calculate_braa, calculate_speed, to_dms, sync_ordered_selection

class RadarView(QGraphicsView):
    def __init__(self, backend):
        super().__init__()
        self.backend = backend
        self.scene = QGraphicsScene(self)
        self.scene.setSceneRect(-2000000, -2000000, 4000000, 4000000) # 4000km x 4000km
        self.setScene(self.scene)
        
        self.setBackgroundBrush(QBrush(QColor(10, 20, 15)))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 啟用拖曳平移 (允許點擊拖拉)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        
        self.track_items = {}
        self.checked_in_tracks = set() # 儲存已報到的友軍名單
        self.ordered_selection = []    # 儲存點擊順序，以便區分 BRAA 的起點與終點
        
        self.show_airbases = True
        self.airbase_items = []
        
        # 內建的高加索主要機場 (備用)
        self.airbases = {
            "Batumi": {"x": -233180, "z": 207399, "course": 0},
            "Kobuleti": {"x": -197274, "z": 226815, "course": 0},
            "Senaki": {"x": -118501, "z": 241643, "course": 0},
            "Kutaisi": {"x": -123305, "z": 286348, "course": 0},
            "Vaziani": {"x": -99665, "z": 503117, "course": 0},
            "Beslan": {"x": 139178, "z": 435017, "course": 0},
            "Mozdok": {"x": 232049, "z": 462529, "course": 0},
            "Min Vody": {"x": 269781, "z": 272828, "course": 0},
        }
        
        # 決定當前要讀取的地圖資料目錄
        base_dir = os.path.dirname(__file__)
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
                        self.airbases[name] = {"x": bx, "z": bz, "course": course}
                        
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
        
        self.intercept_text = self.scene.addText("")
        self.intercept_text.setDefaultTextColor(QColor(255, 255, 0))
        self.intercept_text.setFont(QFont("Consolas", 12, QFont.Weight.Bold))
        self.intercept_text.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        self.intercept_text.setZValue(20)
        self.intercept_text.hide()
        
        self.scale(0.01, 0.01)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_tracks)
        self.timer.start(100)
        
    def wheelEvent(self, event):
        zoomInFactor = 1.15
        zoomOutFactor = 1 / zoomInFactor
        if event.angleDelta().y() > 0:
            zoomFactor = zoomInFactor
        else:
            zoomFactor = zoomOutFactor
        self.scale(zoomFactor, zoomFactor)

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

    def update_tracks(self):
        tracks = self.backend.get_tracks()
        current_names = set()
        
        friendly_data = {}
        hostile_data = {}
        
        for f in tracks['friendlies']:
            color = QColor(50, 255, 50) if f['unit_name'] in self.checked_in_tracks else QColor(50, 200, 255)
            self._update_single_track(f, color, is_hostile=False)
            current_names.add(f['unit_name'])
            friendly_data[f['unit_name']] = f
            
        for h in tracks['hostiles']:
            self._update_single_track(h, QColor(255, 50, 50), is_hostile=True)
            current_names.add(h['unit_name'])
            hostile_data[h['unit_name']] = h
            
        for name in list(self.track_items.keys()):
            if name not in current_names:
                items = self.track_items.pop(name)
                self.scene.removeItem(items['icon'])
                self.scene.removeItem(items['line'])
                self.scene.removeItem(items['text'])
                for dot in items.get('history_dots', []):
                    self.scene.removeItem(dot)

        # 自動置中於第一個友軍 (僅執行一次)
        if not hasattr(self, 'has_centered') and tracks['friendlies']:
            f = tracks['friendlies'][0]
            fsx, fsy = self.dcs_to_scene(f['x'], f['z'])
            self.centerOn(fsx, fsy)
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
            
            # 顯示在連線中點
            mid_x = (fsx + hsx) / 2
            mid_y = (fsy + hsy) / 2
            self.intercept_text.setPos(mid_x, mid_y)
            self.intercept_text.setPlainText(info)
            self.intercept_text.show()
        else:
            self.intercept_line.hide()
            self.intercept_text.hide()

    def _update_single_track(self, data, color, is_hostile):
        name = data['unit_name']
        sx, sy = self.dcs_to_scene(data['x'], data['z'])
        
        future_x = data['x'] + data['vx'] * 30
        future_z = data['z'] + data['vz'] * 30
        fsx, fsy = self.dcs_to_scene(future_x, future_z)
        
        speed_kts = calculate_speed(data['vx'], data['vz'])
        alt_kft = int((data['y'] * 3.28084) / 1000)
        
        label_html = f"{name}<br>FL{alt_kft * 10:03d}<br>{speed_kts} GS"
        
        if name not in self.track_items:
            size = 6
            pen = QPen(color)
            pen.setWidth(0) 
            
            if is_hostile:
                poly = QPolygonF([
                    QPointF(0, -size), QPointF(size, 0),
                    QPointF(0, size), QPointF(-size, 0)
                ])
                icon = self.scene.addPolygon(poly, pen, QBrush(Qt.BrushStyle.NoBrush))
            else:
                icon = self.scene.addEllipse(-size, -size, size*2, size*2, pen, QBrush(Qt.BrushStyle.NoBrush))
                
            icon.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            icon.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable) # 允許選取
            icon.setZValue(10)
            
            line = self.scene.addLine(0, 0, 0, 0, pen)
            line.setZValue(5)
            
            text = self.scene.addText("")
            text.setDefaultTextColor(color)
            text.setFont(QFont("Consolas", 10))
            text.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            text.setZValue(15)
            
            self.track_items[name] = {'icon': icon, 'line': line, 'text': text, 'history_dots': [], 'is_hostile': is_hostile}
        
        items = self.track_items[name]
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
            
        # 更新殘影位置與透明度
        for i, (hx, hz) in enumerate(history_points):
            hsx, hsy = self.dcs_to_scene(hx, hz)
            dot = items['history_dots'][i]
            dot.setPos(hsx, hsy)
            # 越舊的點越透明
            alpha = int(255 * (i + 1) / len(history_points)) * 0.7
            dot_color = QColor(color)
            dot_color.setAlpha(int(alpha))
            dot.setBrush(QBrush(dot_color))
            
        # 動態更新文字與連線顏色 (可能因為右鍵報到而改變)
        items['text'].setDefaultTextColor(color)
        
        # 被選取時加粗圖示，否則保持原本線寬
        if items['icon'].isSelected():
            selected_pen = QPen(color)
            selected_pen.setWidth(2)
            items['icon'].setPen(selected_pen)
            items['line'].setPen(selected_pen)
        else:
            normal_pen = QPen(color)
            normal_pen.setWidth(0)
            items['icon'].setPen(normal_pen)
            items['line'].setPen(normal_pen)
            
        items['line'].setLine(sx, sy, fsx, fsy)
        items['text'].setPos(sx + 10, sy - 10)
        items['text'].setHtml(label_html)

class GCIMainWindow(QMainWindow):
    def __init__(self, backend):
        super().__init__()
        self.setWindowTitle("DCS External GCI (LotATC Lite)")
        self.resize(1200, 800)
        
        main_widget = QWidget()
        layout = QHBoxLayout(main_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 雷達主畫面
        self.radar = RadarView(backend)
        self.setWindowTitle(f"DCS External GCI (LotATC Lite) - {self.radar.current_theatre}")
        layout.addWidget(self.radar, stretch=1)
        
        # 控制面板 (窄邊條)
        sidebar = QVBoxLayout()
        sidebar.setContentsMargins(10, 10, 10, 10)
        
        from PyQt6.QtWidgets import QStyle
        self.btn_mark = QPushButton()
        self.btn_mark.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        self.btn_mark.setToolTip("標記友軍 (Toggle Control) - 點擊友軍後按此按鈕以標記接管狀態")
        self.btn_mark.setFixedSize(40, 40)
        self.btn_mark.clicked.connect(self.radar.toggle_selected_friendly)
        
        self.btn_toggle_airbases = QPushButton()
        self.btn_toggle_airbases.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon))
        self.btn_toggle_airbases.setToolTip("顯示/隱藏機場與跑道 (Declutter)")
        self.btn_toggle_airbases.setFixedSize(40, 40)
        self.btn_toggle_airbases.clicked.connect(self.radar.toggle_airbases)
        
        sidebar.addWidget(self.btn_mark)
        sidebar.addWidget(self.btn_toggle_airbases)
        sidebar.addStretch()
        
        layout.addLayout(sidebar)
        self.setCentralWidget(main_widget)

def run_app():
    backend = GCIBackend(host="0.0.0.0")
    backend.start()
    
    app = QApplication(sys.argv)
    window = GCIMainWindow(backend)
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    run_app()
