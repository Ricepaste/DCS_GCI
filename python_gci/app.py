import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QGraphicsScene, QGraphicsView, QGraphicsItem
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPolygonF
from PyQt6.QtCore import Qt, QTimer, QPointF
from backend import GCIBackend
from geometry import calculate_braa

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

    def update_tracks(self):
        tracks = self.backend.get_tracks()
        current_names = set()
        
        friendly_data = {}
        hostile_data = {}
        
        for f in tracks['friendlies']:
            self._update_single_track(f, QColor(50, 200, 255), is_hostile=False)
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

        # 自動置中於第一個友軍 (僅執行一次)
        if not hasattr(self, 'has_centered') and tracks['friendlies']:
            f = tracks['friendlies'][0]
            fsx, fsy = self.dcs_to_scene(f['x'], f['z'])
            self.centerOn(fsx, fsy)
            self.has_centered = True

        # 處理點擊選取與 BRAA 引導線
        selected_friendlies = []
        selected_hostiles = []
        
        for name, items in self.track_items.items():
            if items['icon'].isSelected():
                if items['is_hostile']:
                    selected_hostiles.append(hostile_data[name])
                else:
                    selected_friendlies.append(friendly_data[name])
                    
        # 如果恰好選中一個友軍和一個敵軍，畫出攔截線與 BRAA
        if len(selected_friendlies) == 1 and len(selected_hostiles) == 1:
            f = selected_friendlies[0]
            h = selected_hostiles[0]
            
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
        
        alt_kft = int((data['y'] * 3.28084) / 1000)
        label_html = f"{name}<br>FL{alt_kft * 10:03d}"
        
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
            
            self.track_items[name] = {'icon': icon, 'line': line, 'text': text, 'is_hostile': is_hostile}
        
        items = self.track_items[name]
        items['icon'].setPos(sx, sy)
        
        # 被選取時加粗圖示，否則保持原本線寬
        if items['icon'].isSelected():
            selected_pen = QPen(color)
            selected_pen.setWidth(2)
            items['icon'].setPen(selected_pen)
        else:
            normal_pen = QPen(color)
            normal_pen.setWidth(0)
            items['icon'].setPen(normal_pen)
            
        items['line'].setLine(sx, sy, fsx, fsy)
        items['text'].setPos(sx + 10, sy - 10)
        items['text'].setHtml(label_html)

class GCIMainWindow(QMainWindow):
    def __init__(self, backend):
        super().__init__()
        self.setWindowTitle("DCS External GCI (LotATC Lite)")
        self.resize(1024, 768)
        
        self.radar = RadarView(backend)
        self.setCentralWidget(self.radar)

def run_app():
    backend = GCIBackend(host="0.0.0.0")
    backend.start()
    
    app = QApplication(sys.argv)
    window = GCIMainWindow(backend)
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    run_app()
