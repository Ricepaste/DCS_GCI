# DCS API (External GCI Interface)

所有暴露給 GCI 的外部介面必須完整記錄於此。此模組為 Python (PyQt6) 與 DCS Lua Exporter 之間的橋樑，負責資料傳遞與幾何運算。

## 1. 資料格式定義 (Data Schemas)

### Unit (Telemetry Record)
每個由 Lua 發送或 `backend.py` 解析後的單位資料結構：
```json
{
    "unit_name": "F-16C_1",
    "type": "F-16C bl.50",
    "player_name": "Player1",
    "x": -250000.5,
    "y": 5000.0,
    "z": 150000.2,
    "vx": 120.5,
    "vy": 0.0,
    "vz": 100.2,
    "coalition": 2,
    "history": [[-250100, 149900], [-250200, 149800]]
}
```
* **x/y/z**: DCS 座標系。`x` 為北，`y` 為高度(公尺)，`z` 為東。
* **vx/vy/vz**: 速度向量 (公尺/秒)。

### Track Object
`backend.get_tracks()` 回傳的航跡彙整物件：
```json
{
    "friendlies": [ { "unit_name": "...", ... } ],
    "hostiles": [ { "unit_name": "...", ... } ],
    "airbases": [ { "name": "Kobuleti", "x": -245000, "z": 140000, "lat": 41.83, "lon": 41.87 } ]
}
```

### BRAA Output
`geometry.calculate_braa(f, h)` 回傳值：
```python
{
    "bearing": 135,   # 方位角 (整數度，相對於正北)
    "range": 45,      # 射程 (海浬)
    "altitude": 150,  # 敵機高度 (百呎 / FL)
    "aspect": "HOT"   # 陣位 (HOT, FLANK, COLD, TAIL)
}
```

### MGRS Format
`geometry.latlon_to_mgrs(lat, lon)` 回傳的 MGRS 字串格式 (10km 精度)：
```
"37T FH 12345 67890" (字串)
```

---

## 2. 座標系統 (Coordinate System)

* **DCS 座標系 (DCS XYZ)**:
  * X 軸：指向正北 (North)
  * Y 軸：高度 (Up)
  * Z 軸：指向正東 (East)
* **邏輯地圖座標系 (Scene Coordinates)**:
  * 由於 Qt `QGraphicsScene` 預設的座標系中，Y 軸是朝下的，而 X 軸朝右。
  * 為了正確繪製，轉換公式為：`Scene_X = DCS_Z`, `Scene_Y = -DCS_X`
* **Lat/Lon (經緯度)**:
  * 透過擷取到的機場基準點 (`ref_point`)，利用等距圓柱投影近似，將 DCS X/Z 平移與縮放為 Lat/Lon。

---

## 3. 幾何演算法 (Geometric Algorithms)

### BRAA Calculation
* **Bearing**: 計算 `atan2(hostile_z - friendly_z, hostile_x - friendly_x)`。
* **Range**: 使用畢氏定理求得距離，再除以 1852.0 轉換為海浬。
* **Aspect**: 計算友機到敵機的向量，與敵機本身速度向量的夾角。夾角越接近 180 度代表 HOT，接近 0 度代表 TAIL。

### Intersection Logic (碰撞/攔截預測)
* 基於 **Law of Sines (正弦定理)** 與相對速度向量求解。
* 計算友機要以目前速率飛向哪個航向 (Cut Heading)，才能恰好與直線飛行的敵機於某點 (Impact Point) 同時抵達。
* 計算過程中若發現 `sin(alpha) > 1`，代表友機速度不足以攔截敵機，無解。

---

## 4. API 列表 (API List)

### Backend API
* `backend.start()`: 啟動 UDP 監聽執行緒。
* `backend.get_tracks() -> dict`: 回傳最新的敵我與機場航跡資料字典。

### Geometry API (`geometry.py`)
* `calculate_braa(f_data: dict, h_data: dict) -> dict`: 計算並回傳 BRAA_Object。
* `calculate_speed(vx: float, vz: float) -> int`: 將公尺/秒轉換為節 (Knots) 並四捨五入。
* `calculate_intercept_heading(fx, fz, f_v, hx, hz, hvx, hvz) -> tuple`: 回傳 `(cut_heading, time_to_intercept_sec, impact_x, impact_z)` 或 `None`。
* `generate_link16_tn(unit_name: str) -> str`: 依據單位名稱雜湊生成 5 碼 Link 16 J-Series Track Number (例如: `J1024`)。
* `latlon_to_mgrs(lat: float, lon: float) -> str`: 將經緯度轉換為 MGRS 字串。
* `dcs_to_latlon(dcs_x, dcs_z, ref_x, ref_z, ref_lat, ref_lon, theatre="Caucasus") -> tuple(lat, lon)`: 使用 DCS 戰區專屬 TM 投影 (中央經線由 `DCS_THEATRE_CENTRAL_MERIDIANS` 字典查表) 搭配參考點校準，將 DCS 座標轉為經緯度。精度 < 300m。
* `latlon_to_dcs(lat, lon, ref_x, ref_z, ref_lat, ref_lon, theatre="Caucasus") -> tuple(dcs_x, dcs_z)`: 反向轉換經緯度為 DCS 座標。
* `DCS_THEATRE_CENTRAL_MERIDIANS`: 各戰區的 TM 中央經線字典 (例: Caucasus=33°, Syria=36°)。
