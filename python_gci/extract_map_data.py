import os

def extract_map_data_from_log():
    # 尋找標準的 DCS Log 路徑
    user_profile = os.environ.get('USERPROFILE', '')
    log_path = os.path.join(user_profile, 'Saved Games', 'DCS', 'Logs', 'dcs.log')
    
    if not os.path.exists(log_path):
        log_path = os.path.join(user_profile, 'Saved Games', 'DCS.openbeta', 'Logs', 'dcs.log')
        if not os.path.exists(log_path):
            print("找不到 DCS log 檔案！請確認您的 Saved Games 資料夾路徑。")
            return

    print(f"正在從 {log_path} 讀取地圖資料...")
    
    coast_lines = []
    airbase_lines = []
    
    current_theatre = "Caucasus" # Default fallback
    
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as log_file:
        for line in log_file:
            if "=== DCS MAP DATA EXPORT START" in line:
                coast_lines.clear()
                airbase_lines.clear()
                
                # Extract theatre if available
                if "START: " in line:
                    parts = line.split("START: ")
                    if len(parts) >= 2:
                        current_theatre = parts[1].split(" ===")[0].strip()
                        
            elif "COASTLINE_PT:" in line:
                parts = line.split("COASTLINE_PT:")
                if len(parts) >= 2:
                    points = parts[1].strip().split(";")
                    for pt in points:
                        if pt:
                            coast_lines.append(pt)
            elif "AIRBASE_PT:" in line:
                parts = line.split("AIRBASE_PT:")
                if len(parts) >= 2:
                    airbase_lines.append(parts[1].strip())

    if not coast_lines and not airbase_lines:
        print("未在 dcs.log 中找到任何地圖資料，請確認您已在 DCS 內執行過 export_map_data.lua")
        return

    base_dir = os.path.dirname(__file__)
    map_data_dir = os.path.join(base_dir, 'map_data', current_theatre)
    os.makedirs(map_data_dir, exist_ok=True)
    
    coast_path = os.path.join(map_data_dir, 'coastline.csv')
    airbase_path = os.path.join(map_data_dir, 'airbases.csv')
    current_map_path = os.path.join(base_dir, 'map_data', 'current_map.txt')
                    
    with open(coast_path, 'w', encoding='utf-8') as coast_out:
        for pt in coast_lines:
            coast_out.write(f"{pt}\n")
            
    with open(airbase_path, 'w', encoding='utf-8') as airbase_out:
        for pt in airbase_lines:
            airbase_out.write(f"{pt}\n")
            
    with open(current_map_path, 'w', encoding='utf-8') as map_out:
        map_out.write(current_theatre)
            
    print(f"成功擷取地圖: {current_theatre}")
    print(f"成功匯出 {len(airbase_lines)} 座機場至 map_data/{current_theatre}/airbases.csv")
    print(f"成功匯出 {len(coast_lines)} 個海岸線邊界至 map_data/{current_theatre}/coastline.csv")
    print("您現在可以啟動 app.py，它將自動讀取這份地圖資料並生成全新的戰術雷達！")

if __name__ == "__main__":
    extract_map_data_from_log()
