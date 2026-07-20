# DCS GCI API 規格與架構文件

本文件記錄 `DCS External GCI (LotATC Lite)` 的外部介面、資料格式定義，以及幾何與座標系統。

## 1. 資料格式定義 (Data Schemas)

### Unit (單位結構)
代表從 DCS 擷取到的單個實體資訊。
```python
{
    'unit_name': str,      # 單位唯一名稱或 ID
    'x': float,            # DCS 座標系下的 X 軸 (正北向)
    'y': float,            # 高度，預設單位為公尺
    'z': float,            # DCS 座標系下的 Z 軸 (正東向)
    'vx': float,           # X 軸速度分量 (m/s)
    'vy': float,           # Y 軸速度分量 (m/s)
    'vz': float,           # Z 軸速度分量 (m/s)
    'coalition': int,      # 陣營代碼 (1=紅軍, 2=藍軍)
    'type': str            # 單位機型或種類 (可選)
}
```

### Track Object (航跡物件)
代表在 GCI 雷達畫面上管理的航跡狀態。
```python
{
    'friendlies': [Unit, ...], # 友軍單位清單
    'hostiles': [Unit, ...]    # 敵軍單位清單
}
```

### BRAA Output (攔截資訊)
表示友軍到敵軍的相對攔截幾何。
```python
{
    'bearing': int,        # 目標方位角 (0-359 度)
    'range': int,          # 目標距離 (海浬 NM)
    'altitude': int,       # 目標高度 (英呎 ft)
    'aspect': str          # 陣位 (HOT, FLANK, BEAM, DRAG)
}
```

## 2. 座標系統 (Coordinate System)

### DCS 世界座標
DCS 使用左手座標系，其定義為：
- `X 軸`：正向朝**北 (North)**
- `Z 軸`：正向朝**東 (East)**
- `Y 軸`：正向朝**上 (Up/Altitude)**

### Qt Scene 邏輯視窗座標
Qt 的 `QGraphicsScene` 為螢幕渲染座標系：
- `Scene_X`：正向朝**右**
- `Scene_Y`：正向朝**下**

### 座標轉換 (`dcs_to_scene`)
為了將 DCS 座標映射到雷達畫面，轉換邏輯為：
```python
Scene_X = Z 軸 (DCS East -> Screen Right)
Scene_Y = -X 軸 (DCS North -> Screen Up)
```

## 3. 幾何演算法 (Geometric Algorithms)

### BRAA Calculation
計算 `friendly` 到 `target` 的相對幾何。
- **方位角 (Bearing)**：
  使用 `math.atan2(target.z - friendly.z, target.x - friendly.x)`，並轉為度數 `(deg + 360) % 360`。
- **射程 (Range)**：
  2D 歐幾里得距離 `sqrt(dx^2 + dz^2)`。
  單位轉換：公尺 * `0.000539957` 轉為海浬 (NM)。
- **高度 (Altitude)**：
  單位轉換：公尺 * `3.28084` 轉為英呎 (ft)。

## 4. API 列表 (API List)

### Backend 模組 (`backend.py`)
```python
backend = GCIBackend(host='0.0.0.0', port=10082)
backend.start()
backend.get_tracks() -> dict  # 回傳 {'friendlies': [], 'hostiles': []}
backend.stop()
```

### Geometry 模組 (`geometry.py`)
```python
# 計算 BRAA 資訊
braa = calculate_braa(friendly_unit, target_unit)

# 計算真速 (True Airspeed)
knots = calculate_speed(vx, vz)

# 經緯度或座標轉度分秒格式
dms_str = to_dms(decimal_degree, is_lat=True)
```

## 5. 多地圖支援與資料儲存
Lua 腳本會將地圖資訊匯出，Python 會自動建立對應資料夾。
- 路徑：`map_data/<THEATRE_NAME>/`
- 包含檔案：`airbases.csv`、`coastline.csv`
- 當前地圖：由 `map_data/current_map.txt` 決定。
