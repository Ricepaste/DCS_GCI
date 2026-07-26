import sys
import os
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

from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFormLayout, QLineEdit, QComboBox, QDialogButtonBox
)
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QCursor
from PyQt6.QtCore import Qt, QPointF

from backend import GCIBackend
from ui import (
    GCIMainWindow, RadarView, AircraftStatusPanel, AirspaceManagerPanel,
    get_styled_input_text, get_styled_input_double, get_base_dir
)

def create_gci_cursor():
    cursor_size = 20
    pixmap = QPixmap(cursor_size, cursor_size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
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
