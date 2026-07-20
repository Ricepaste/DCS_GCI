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
    sea_path = os.path.join(base_dir, 'sea.csv')
    airbase_path = os.path.join(base_dir, 'airbases.csv')
    
    print(f"正在從 {log_path} 讀取地圖資料...")
    
    coast_count = 0
    sea_count = 0
    airbase_count = 0
    
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as log_file, \
         open(coast_path, 'w', encoding='utf-8') as coast_out, \
         open(sea_path, 'w', encoding='utf-8') as sea_out, \
         open(airbase_path, 'w', encoding='utf-8') as airbase_out:
         
        for line in log_file:
            if "COASTLINE_PT:" in line:
                parts = line.split("COASTLINE_PT:")
                if len(parts) >= 2:
                    points = parts[1].strip().split(";")
                    for pt in points:
                        if pt:
                            coast_out.write(f"{pt}\n")
                            coast_count += 1
            elif "SEA_PT:" in line:
                parts = line.split("SEA_PT:")
                if len(parts) >= 2:
                    points = parts[1].strip().split(";")
                    for pt in points:
                        if pt:
                            sea_out.write(f"{pt}\n")
                            sea_count += 1
            elif "AIRBASE_PT:" in line:
                parts = line.split("AIRBASE_PT:")
                if len(parts) >= 2:
                    # 可能包含 3 或 4 個參數 (name,x,z,course)
                    airbase_out.write(f"{parts[1].strip()}\n")
                    airbase_count += 1
                    
    print(f"成功匯出 {airbase_count} 座機場至 airbases.csv")
    print(f"成功匯出 {coast_count} 個海岸線邊界至 coastline.csv")
    print(f"成功匯出 {sea_count} 個海洋填色方塊至 sea.csv")
    print("您現在可以啟動 app.py，它將自動讀取這兩個檔案並生成全新的戰術雷達！")

if __name__ == "__main__":
    extract_map_data_from_log()
