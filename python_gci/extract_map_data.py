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

    base_dir = os.path.dirname(__file__)
    coast_path = os.path.join(base_dir, 'coastline.csv')
    sea_seed_path = os.path.join(base_dir, 'sea_seed.csv')
    airbase_path = os.path.join(base_dir, 'airbases.csv')
    
    print(f"正在從 {log_path} 讀取地圖資料...")
    
    coast_lines = []
    airbase_lines = []
    sea_seed_lines = []
    
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as log_file:
        for line in log_file:
            if "=== DCS MAP DATA EXPORT START" in line:
                coast_lines.clear()
                airbase_lines.clear()
                sea_seed_lines.clear()
            elif "COASTLINE_PT:" in line:
                parts = line.split("COASTLINE_PT:")
                if len(parts) >= 2:
                    points = parts[1].strip().split(";")
                    for pt in points:
                        if pt:
                            coast_lines.append(pt)
            elif "SEA_SEED:" in line:
                parts = line.split("SEA_SEED:")
                if len(parts) >= 2:
                    sea_seed_lines.append(parts[1].strip())
            elif "AIRBASE_PT:" in line:
                parts = line.split("AIRBASE_PT:")
                if len(parts) >= 2:
                    airbase_lines.append(parts[1].strip())
                    
    with open(coast_path, 'w', encoding='utf-8') as coast_out:
        for pt in coast_lines:
            coast_out.write(f"{pt}\n")
            
    with open(sea_seed_path, 'w', encoding='utf-8') as sea_seed_out:
        for pt in sea_seed_lines:
            sea_seed_out.write(f"{pt}\n")
            
    with open(airbase_path, 'w', encoding='utf-8') as airbase_out:
        for pt in airbase_lines:
            airbase_out.write(f"{pt}\n")
            
    print(f"成功匯出 {len(airbase_lines)} 座機場至 airbases.csv")
    print(f"成功匯出 {len(coast_lines)} 個海岸線邊界至 coastline.csv")
    if sea_seed_lines:
        print(f"成功提取 {len(sea_seed_lines)} 個海洋種子點至 sea_seed.csv")
    print("您現在可以啟動 app.py，它將自動讀取這兩個檔案並生成全新的戰術雷達！")

if __name__ == "__main__":
    extract_map_data_from_log()
