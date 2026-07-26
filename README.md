# Top Gun: Maverick - DCS 任務模擬框架 (Modular Framework)

這是一套基於 DCS World 與 MOOSE 腳本庫所開發的「高度擬真、模組化」任務控制框架。
本框架的設計初衷是為了完美還原電影《捍衛戰士：獨行俠》中的終極任務體驗，包含峽谷低空狂飆、精準計時、高智商戰管 (GCI/AWACS) 語音與交戰指令。

---

## 🛠️ 安裝前提 (Prerequisites)

1. **依賴環境**：本腳本強烈依賴 `MOOSE.lua` 函式庫。
2. **掛載順序**：在 DCS 任務編輯器 (Mission Editor) 中，必須遵守以下載入順序：
   *   `MISSION START` -> `DO SCRIPT FILE` -> 載入 `MOOSE.lua`
   *   `ONCE` (Time More 2 秒) -> `DO SCRIPT FILE` -> 依序載入本框架的腳本（建議先載入 `TopGun_Core.lua`，再載入其他模組）。

---

## 📦 模組介紹與設定說明 (Modules)

本框架採用模組化設計，您可以根據任務需求自由決定要掛載哪些模組。

### 1. `TopGun_Core.lua` (核心系統)
*   **功能**：建立全域變數 `TOPGUN_MISSION`，作為所有模組之間溝通的橋樑。
*   **設定**：**必須**第一個載入。

### 2. `TopGun_GCI.lua` (極致擬真預警機/戰管與戰區司令部)
*   **功能**：提供完全符合 NATO Brevity（北約軍事簡語）標準的戰管體驗，並兼具戰區交戰指揮權。
    *   **F10 報到系統**：玩家必須先 Check-in，系統才會開啟進階功能。
    *   **主動威脅感知 (BRAA)**：GCI 會根據敵機距離「動態調整通報頻率」（>50海浬: 60秒 / 15-30海浬: 30秒 / <15海浬: 15秒 / 狗戰: 自動閉嘴）。
    *   **Request Picture**：要求戰場宏觀圖像，以 8 方位中文 (如: 西北) 顯示敵機動向。
    *   **狀態監控**：自動偵測玩家油量 (Bingo) 與彈藥量 (Winchester) 並建議返航 (RTB)。
    *   **交戰指令 (Commit Authority)**：當敵軍闖入指定禁飛區 (Kill Box) 時，戰管會主動打破靜默，鎖定最近的玩家下達強制交戰指令 (Commit Order)。
    *   **物理雷達限制**：絕不開天眼，敵軍必須被我方雷達掃描到才會通報。
*   **任務編輯器設定**：
    *   在地圖上放置一架 E-3A 或 E-2D 預警機，或是地面雷達，並將其群組名稱前綴設定為 `AWACS` (例如 `AWACS_Magic`)。
    *   (可選) 在地圖上畫一個區域 (Zone)，命名為 `Kill_Box_Alpha` 作為交戰禁飛區。

### 3. `TopGun_SAM.lua` (峽谷防空陷阱)
*   **功能**：強制執行「Hard Deck (最低安全高度)」限制。持續監控玩家的絕對離地高度 (AGL)。一旦玩家拉高超過 300 英呎，所有隱藏的防空飛彈雷達將瞬間開機鎖定；只要俯衝回低空，飛彈雷達就會自動丟失目標並關機。
*   **任務編輯器設定**：
    *   在地圖上畫一個多邊形區域 (Zone)，命名為 `Canyon_Zone`。
    *   放置敵方防空飛彈單位 (如 SA-10, SA-3)，將其群組名稱前綴設定為 `SAM_Trap` (例如 `SAM_Trap_1`)。

### 4. `TopGun_Timer.lua` (峽谷極限計時器)
*   **功能**：一個正向挑戰碼表 (Stopwatch)。當玩家衝入峽谷起點時自動開始計時，並在畫面上方持續刷新碼表，不會干擾通訊畫面。
*   **任務編輯器設定**：
    *   在地圖上畫一個區域 (Zone)，命名為 `Ingress_Zone` (峽谷入口)。

---

## 🚀 未來擴充計畫 (WIP)
- [ ] **`TopGun_Ambush.lua` (五代機無縫伏擊)**：目標摧毀後自動 Spawn 五代機進行追殺。
- [ ] **`TopGun_Bomb.lua` (精準轟炸判定)**：捕捉炸彈落點，判定是否精準命中通風口並計算 3D 誤差距離。

---

## 開發紀錄 (Changelog)
* **2026-07-20 (LotATC Lite 版本)**:
  * 徹底重構為 External GCI 架構，完全掌握程式控制權，不再依賴 DCS 內部黑箱微觀 AI。
  * 支援 **無限縮放平移** 雷達畫布。
  * 支援 **UI 按鈕切換友軍標記 (Toggle Control)** 變更航跡顏色。
  * 支援 **任意兩目標動態 BRAA 計算** (點擊兩目標即顯示連線、方位角、距離、高度、態勢)。
  * 支援 **地面速度 (Ground Speed, GS)** 即時顯示。
  * 支援 **靜態 DCS 地圖背景載入** (`python_gci/images/map.png`)，以及**動態向量海岸線與機場資料 (Vector Maps)**。
  * 支援 **多人伺服器玩家 ID 擷取**，真人玩家將顯示專屬 ID 而非機體呼號。
* **2026-07-21 (GCI 戰術指揮、UI 擴充與多人連線)**:
  * 實作 **ROE (交戰規則) 手動宣告系統**：將敵機分為 `UNKNOWN` (黃色)、`BANDIT` (紅色)、`HOSTILE` (紅色) 級別，雷達光點將根據指揮官的手動宣告改變顏色與縮寫標籤。
  * 擴充 **動態航機懸浮資訊面板 (Status Panel)**：新增 `WEAPONS` 與 `FUEL` 可持久化編輯欄位，支援記錄各航機獨立的戰術筆記。
  * 引入 **自動機型縮寫前綴** (如 `[A]` 代表 AWACS, `[U]`, `[F]`, `[H]`, `[B]`)，並優化了文字圖層置中顯示以解決縮放偏移問題。
  * 實裝 **現代化 GCI 專屬游標 (Custom Cursor)**：自訂螢光綠準星游標並實作滑鼠手動平移 (Manual Panning)，提升擬真戰管操作手感。
  * 新增 **SAM 防空導彈動態威脅圈 (Threat Rings)**：自動識別地面 SAM/防空單位 (S-300, Patriot, Buk, Tor, Kub, Osa, Tunguska 等) 並繪製半透明虛線威脅圈；支援側邊欄專屬按鈕與快捷鍵 `T` 即時 Toggle 切換開關。
  * 新增 **多人連線架構 (TCP Client-Server)**：支援開房主機 (Host Mode) 廣播雷達資料與連線玩家 (Client Mode) 透過虛擬區域網路 (如 Hamachi) 即時觀看雷達。
  * 支援 **雙陣營雷達獨立視角 (Dual Coalition View)**：支援開房主機同時匯出藍軍 (BLUE) 與紅軍 (RED) 雷達網資料。連線玩家可自由選擇觀看陣營，維持兩軍情報徹底隔離 (Fog of War)。
  * 優化 **海量單位傳輸效能 (UDP Payload Optimization & Clutter Filter)**：實裝地面非威脅單位過濾 (自動過濾一般車輛與步兵)、數值精度壓縮 (1 位小數) 與藍紅軍分拆 UDP 封包發送，徹底解決多人大型戰役中 UDP 封包超過 64KB 上限導致停更的嚴重 Bug。
  * 修復 **ECM 電子干擾航跡標籤顯示 (Jammed Track Labels)**：修正干擾目標被錯誤隱藏字卡的 Bug，保留干擾波束射線之同時完整渲染航跡號碼 (TN)、高度與速度字卡。
  * 優化 **北約 GCI 規範 UI 與動態字體縮放 (NATO GCI Compliant UI & Dynamic Font Scaling)**：徹底移除娛樂性 Emoji 與混亂多色渲染，改為北約戰管 console 嚴謹單色綠/藍/琥珀配色與極簡 `+` 十字戰術地標；同時修復 HTML 標籤內嵌 `font-size` 樣式與 layout 異步，實現 100% 實時字體與面板 UI 縮放。
  * 實裝 **空域手繪完成命名/上色對話框 (Airspace Creation Dialog & Color Picker)**：修復空域繪製完成後的命名與色彩選擇對話框 (`AirspaceNameInput`)，支援自訂邊框與填滿顏色，並可導出/導入 `airspaces_config.json`。
  * 修正 **Lua Exporter 防崩潰與中立陣營相容性 (Safe Lua Exporter & Neutral Scan)**：重構 `External_GCI_Exporter.lua` 陣營枚舉存取邏輯（安全回退至整數 `0, 1, 2`），防止特定 DCS 環境中存取未定義 `coalition.side` 觸發 Lua runtime 異常；修復 `export_telemetry_safe(time)` 的 `time` 參數在部分特定呼叫環境下為 `nil` 時嘗試進行加法運算導致的 `attempt to perform arithmetic on local 'time' (a nil value)` 崩潰異常（改為回退至 `timer.getTime()`），保障腳本 100% 穩定持續執行。
  * 修復 **啟動黑屏與地圖鏡頭對焦 (Launch Camera Auto-Centering)**：修正無空中單位時鏡頭偏移至 (0,0) 海域導致畫面黑屏的 Bug，啟動時自動精準對焦至當前地圖機場群中央。
  * 新增 **GUI 主視窗元件與 Layout 完整性單元測試 (`test_gci_main_window_initialization_and_layout`)**：自動驗證 `centralWidget` 視圖掛載、RadarView 正確綁定、所有側邊欄按鈕按鍵實體化與字體縮放事件連動，防止未預期的縮排或掛載錯誤導致畫面全黑。
  * 實裝 **自動交戰衝突警報與接近率計算 (Conflict Alert & Closure Rate)**：當己方空中單位與敵方單位距離小於等於 50 NM 且雙方相向靠近接近率 $V_c \ge 300\text{ KTS}$ 時，自動於最危險之目標間繪製警報連線並標示接近速度；支援快捷鍵 `C` 與邊欄專屬按鈕開關。採用一機一線最高威脅篩選演算法，完全消除多機混戰時之蜘蛛網視覺擁擠。
  * 重構 **雙欄軍規滾動側邊欄 UI (2-Column Scrollable Military Sidebar UI)**：將側邊欄按鈕按功能邏輯重構為三大直觀類別（`DISPLAY` 圖層開關、`TOOLS` 戰術與測量工具、`CONTROL` 戰管與系統維護），並採用 **2 欄矩陣 (QGridLayout)** 配合 **無縫滾動區域 (QScrollArea)** 雙層防護機制；垂直佔用高度直接減半，徹底解決大螢幕/4K 放大（100%~175%）及低解析度下按鈕擠壓重疊與溢出問題。
  * 實裝 **預設空域資料自動載入 (Default Airspaces Auto-Load)**：雷達視圖啟動時自動掃描讀取同目錄下的 `airspaces_config.json`（包含預設地形/山脈空域劃分），無須每次手動 Import 即可在啟動後直接繪製於雷達畫面上。
  * 實裝 **輕量級 AI 引導航點與動態單位生成 (AI Vectoring & Preset Spawning)**：
    * **飛行指定點 (`[V] Direct AI Vector`)**：右鍵點擊任何 AI 航跡並選取目標位置，雷達直接透過 UDP 10089 端口發送 `GoToWaypoint` 任務指令，引導 AI 轉向飛往指定座標點。
    * **預設單位生成 (`[S] Spawn Preset Unit`)**：在地圖空白處右鍵即可選擇生成藍/紅軍預設 CAP (F-16C / Su-27)、CAS (A-10C / Su-25T) 與直升機單位 (AH-64D / Ka-50)，完全相容 DCS 原生 Lua API `coalition.addGroup` 且維持 100% 程式輕量。
  * 重構 **Python GCI GUI 代碼架構 (Modular UI Refactoring)**：將原本 3,290 多行的單一 `app.py` 成功解耦並拆分為 `python_gci/ui/` 模組化結構 (`radar_view.py`, `main_window.py`, `context_menu.py`, `panels.py`)；保持 100% 向後相容性，大幅提升維護性、測試獨立性與 LLM 開發效率。

## 📡 DCS 外部戰場監控系統 (External GCI)

本專案包含一個外部的戰場管制 (GCI) 雷達介面，透過 UDP Sockets 將 DCS 遊戲內的雷達偵測資料即時傳送到外部 Python 程式，提供一個現代化、無黑箱、且具備真實雷達死角模擬的 GCI 介面。

### ⚠️ 環境設定要求 (De-sanitization)
為了讓 DCS 能夠使用 UDP Sockets 傳送遙測資料給 Python，**必須解除 DCS 的 Lua 沙盒限制**（因為腳本需要使用 `require("socket")`）：
1. 進入你的 DCS 安裝目錄（例如：`C:\Program Files\Eagle Dynamics\DCS World OpenBeta`）。
2. 用文字編輯器打開 `Scripts/MissionScripting.lua`。
3. 找到檔案底部的 `sanitizeModule('os')`, `sanitizeModule('io')`, `sanitizeModule('lfs')`, `sanitizeModule('require')`, `sanitizeModule('loadlib')`, `sanitizeModule('package')`。
4. 在 `require` 和 `package` 這兩行前面加上 `--` 進行註解（變成 `--sanitizeModule('require')` 和 `--sanitizeModule('package')`）。
5. 存檔後重開 DCS。

### 如何使用 (How to use)
1. **Python 端 (雷達介面)**：
   - 進入 `python_gci` 資料夾。
   - 安裝依賴庫：`pip install -r requirements.txt` (需要 PyQt6)。
   - 啟動雷達介面：`python app.py`。
   - 在啟動對話框中選擇模式：
     - **Host Mode (Server)**: 適用於運行 DCS 的主機。
     - **Client Mode (Connect)**: 適用於連線的朋友，請輸入主機的 Hamachi IP 與 Port (預設 `10088`)。
2. **DCS 端 (資料匯出)**：
   - 在任務編輯器中，利用 `DO SCRIPT FILE` 掛載 `External_GCI_Exporter.lua`。
   - **注意：** 你的藍軍必須要有雷達單位 (如 AWACS 或 EWR 預警雷達)，因為本腳本強調真實性，只會將「藍軍雷達實際偵測到的目標」匯出到 Python GCI 介面上。
3. 任務開始後，切換到 Python 視窗，你就能在深色雷達螢幕上即時看到友軍與敵軍的動態航跡了！

### 📦 打包與 GitHub 自動發布 (Build & Release)

#### 1. 本地一鍵打包 (`.exe`)
在專案根目錄執行 PowerShell 打包腳本：
```powershell
.\build.ps1
```
腳本會自動安裝 `PyInstaller` 並將程式打包為獨立的 `python_gci/dist/GCI_Client.exe`。朋友可以直接執行，不需安裝 Python。

#### 2. GitHub Actions 自動化發布 (CI/CD)
本專案已配置 GitHub Actions (`.github/workflows/release.yml`)。
當你在 Git 中推動一個版本 Tag (例如 `v1.0.0`) 時：
```bash
git tag v1.0.0
git push origin v1.0.0
```
GitHub Actions 將會自動觸發 Windows 建置伺服器、執行 Pytest 測試、編譯 `.exe` 執行檔，並自動建立 GitHub Release 且將 `GCI_Client.exe` 附加在發布頁面供人下載！

### 🗺️ 向量地圖生成工具 (Vector Map Extractor)
為了讓雷達能夠精準顯示海岸線與機場位置，並且支援 DCS **所有未來的地圖**（高加索、敘利亞、馬里亞納等），我們提供了一套全自動地圖資料掃描與匯出工具。

1. **DCS 內匯出 (Lua)**：
   - 進入 DCS 任務編輯器或隨便開一個該地圖的任務。
   - 透過觸發器 `DO SCRIPT FILE` 或是 Web Console 執行 `export_map_data.lua`。
   - 腳本會自動計算該地圖的邊界，並掃描海岸線與機場，輸出到系統的 `dcs.log` 檔案中。這利用了 `env.info` 巧妙繞過了 DCS Mission Scripting 環境對於寫檔 (lfs/io) 的沙盒限制。

2. **Python 端萃取**：
   - 離開任務後，開啟終端機執行：
     ```powershell
     python python_gci/extract_map_data.py
     ```
   - 腳本會自動讀取 `Saved Games/DCS/Logs/dcs.log`，將地圖點陣資料萃取成 `coastline.csv` 與 `airbases.csv`。

3. **啟動雷達**：
   - 只要 `python_gci` 資料夾底下存在上述兩個 `.csv` 檔案，`app.py` 啟動時就會自動載入，覆蓋預設資料，為你繪製極具現代感的輕量化戰術雷達圖！

### 🎨 現代化 UI 與戰術空域管理 (Tactical Airspace & UI)
GCI 介面內建了豐富的無邊框浮動面板 (Floating UI) 以及戰術空域繪製工具：
1. **Airspace 繪製**：點擊畫面上方的「Add Airspace」按鈕，左鍵在雷達圖上點擊多個點來圈出多邊形空域，右鍵完成繪製並為其命名。這非常適合用來標記禁航區 (No-Fly Zones) 或是 CAP 巡邏區。
2. **Airspace 管理**：點擊「Manage Airspace」可以開啟管理面板，支援一鍵刪除不需要的空域圖層。所有的空域都會自動設置為滑鼠穿透 (`NoButton`)，絕對不會干擾你點擊下方的飛機航跡。
3. **無邊框飛機狀態面板**：雙擊任何一架飛機，即可在雷達畫面上喚出半透明、科技感十足的浮動狀態卡 (Status Panel)，即時監控該目標的速度、高度、航向與機種，不會彈出突兀的 OS 原生視窗。
