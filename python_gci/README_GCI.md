# External GCI Interface (LotATC Lite)

## Setup Instructions
1. **地圖資料匯出 (Map Data Extraction)**:
   - In DCS Mission Editor, load `export_map_data.lua` via DO SCRIPT FILE to export the current map's layout.
   - Run the python extractor to build the map dataset:
     ```bash
     python python_gci/extract_map_data.py
     ```
   - This will automatically create `python_gci/map_data/<THEATRE>/` and save `airbases.csv` and `coastline.csv`.
2. **啟動雷達 (Start GCI)**:
   - Load `External_GCI_Exporter.lua` in your DCS mission to export radar data. Ensure you have an AWACS or EWR radar unit placed for the Blue coalition.
   - Run the GCI client:
     ```bash
     pip install -r python_gci/requirements.txt
     python python_gci/app.py
     ```

## Features
- **Realistic Detections:** Enemy aircraft are only drawn if a Blue coalition radar can physically see them.
- **Modern UI:** Built on PyQt6 with a dark, high-performance radar scope.
- **Velocity Vectors:** Shows heading and speed for all tracks.
- **Altitude Tags:** Displays altitude in thousands of feet (Flight Level).
