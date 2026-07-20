# DCS External GCI API Documentation

所有暴露給 GCI 的外部介面必須完整記錄於此。此文件作為 `app.py`, `backend.py` 與 `External_GCI_Exporter.lua` 之間溝通與資料交換的唯一真理來源 (Single Source of Truth)。

## 1. 資料格式定義 (Data Schemas)

### Unit (單位資料結構)
由 `External_GCI_Exporter.lua` 定期透過 UDP JSON 傳送至 Python 後端。
```json
{
    "unit_name": "Dagger 1-1-1",
    "group_name": "Dagger 1",
    "type": "F-16C bl.50",
    "x": -250000.5,
    "y": 6000.0,
    "z": 650000.2,
    "vx": 150.5,
    "vy": 0.0,
    "vz": 200.3,
    "heading": 0.927,
    "is_friendly": true
}
```
* **x, z**: DCS 平面座標 (X為南北向，Z為東西向)，單位為公尺 (m)。
* **y**: DCS 高度 (Altitude)，單位為公尺 (m)。
* **vx, vy, vz**: 三維速度向量，單位為公尺/秒 (m/s)。
* **heading**: 機頭朝向 (弧度 radians)。
* **is_friendly**: 布林值，代表是否為己方聯軍單位。

### Track Object (雷達航跡結構)
後端 `backend.py` 彙整後的航跡結構：
```json
{
    "friendlies": [ { "unit_name": "...", ... } ],
    "hostiles": [ { "unit_name": "...", ... } ]
}
```

### BRAA Output (戰管攔截資訊)
由 `geometry.py` 輸出的計算結果：
```json
{
    "bearing": 275,
    "range": 45,
    "altitude": 25000,
    "aspect": "HOT"
}
```
* **bearing**: 從友軍看向目標的方位角 (度，0-360)。
* **range**: 距離，單位為海里 (NM)。
* **altitude**: 目標高度，單位為英呎 (Feet)。
* **aspect**: 目標相對態勢 (HOT, FLANK, COLD)。

## 2. 座標系統 (Coordinate System)

### DCS 座標系轉為 UI 場景座標系
DCS 的座標系統 (X, Z) 與標準笛卡爾座標 (X, Y) 或螢幕繪圖座標系不同：
- DCS **X 軸** 對應地理的 **北/南** (正北為正)。
- DCS **Z 軸** 對應地理的 **東/西** (正東為正)。

在 PyQt6 UI (`app.py`) 中的轉換公式：
```python
def dcs_to_scene(x, z):
    return z, -x
```
* Scene X = DCS Z (正東)
* Scene Y = -DCS X (正北，PyQt中 Y 向下為正，所以需加上負號反轉)

## 3. 幾何演算法 (Geometric Algorithms)

### BRAA Calculation (BRAA 計算邏輯)
位於 `geometry.py`：
1. **方位角 (Bearing)**：使用 `math.atan2(dx, dz)` 取得弧度後轉換為度數 (0~360)。
2. **射程 (Range)**：使用 Euclidean distance `sqrt(dx^2 + dz^2)` 取得公尺後，除以 `1852.0` 轉換為海里 (NM)。
3. **高度 (Altitude)**：將 DCS 的 Y 值 (公尺) 乘上 `3.28084` 轉換為英呎。
4. **陣位 (Aspect)**：目標速度向量與 LOS (Line of Sight) 視線向量的角度差。
   - 角度差 <= 60度: **HOT** (迎頭)
   - 60度 < 角度差 < 120度: **FLANK** (側翼)
   - 角度差 >= 120度: **COLD** (追尾)

### 速度計算 (Ground Speed Calculation)
位於 `app.py` UI 呈現層：
- 地面速度 (m/s) = `sqrt(vx^2 + vz^2)`
- 轉換為節 (Knots) = `m/s * 1.94384`

## 4. API 列表 (API List)

### Backend 外部介面
```python
backend = GCIBackend(host="0.0.0.0", port=10082)
backend.start() # 背景執行緒啟動 UDP 接收
backend.get_tracks() -> dict # 回傳包含 'friendlies' 與 'hostiles' 的字典
```

### Geometry 幾何函數
```python
from geometry import calculate_braa
calculate_braa(friendly_dict, target_dict) -> dict # 回傳 BRAA_Object
```
