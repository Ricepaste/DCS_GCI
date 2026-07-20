import sys
import io
import folium
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QTimer
import os

# Add parent directory to path so we can import backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from python_gci.backend import GCIBackend

class MapWindow(QMainWindow):
    def __init__(self, backend):
        super().__init__()
        self.backend = backend
        self.setWindowTitle("Satellite Map Prototype (Warning: Flickers on update)")
        self.resize(1024, 768)
        
        self.web_view = QWebEngineView()
        self.setCentralWidget(self.web_view)
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_map)
        self.timer.start(2000) # 每 2 秒更新一次，避免網頁載入過度閃爍
        
        self.first_load = True
        
    def update_map(self):
        tracks = self.backend.get_tracks()
        
        # 預設中心：高加索
        center = [42.0, 42.0]
        if tracks['friendlies']:
            f = tracks['friendlies'][0]
            if 'lat' in f and 'lon' in f:
                center = [f['lat'], f['lon']]
                
        # 建立地圖 (衛星圖)
        m = folium.Map(
            location=center, 
            zoom_start=9,
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri'
        )
        
        for f in tracks['friendlies']:
            if 'lat' in f and 'lon' in f:
                folium.Marker(
                    [f['lat'], f['lon']], 
                    tooltip=f"{f['unit_name']}",
                    icon=folium.Icon(color='blue', icon='plane', prefix='fa')
                ).add_to(m)
                
        for h in tracks['hostiles']:
            if 'lat' in h and 'lon' in h:
                folium.Marker(
                    [h['lat'], h['lon']], 
                    tooltip=h['unit_name'], 
                    icon=folium.Icon(color='red', icon='fighter-jet', prefix='fa')
                ).add_to(m)
                
        # 將地圖轉為 HTML 字串
        data = io.BytesIO()
        m.save(data, close_file=False)
        html = data.getvalue().decode()
        
        self.web_view.setHtml(html)

if __name__ == "__main__":
    backend = GCIBackend(host="0.0.0.0")
    backend.start()
    
    app = QApplication(sys.argv)
    window = MapWindow(backend)
    window.show()
    sys.exit(app.exec())
