# External GCI Interface (LotATC Lite)

## Setup Instructions
1. In DCS Mission Editor, set up a DO SCRIPT FILE to load `External_GCI_Exporter.lua`. Ensure you have an AWACS or EWR radar unit placed for the Blue coalition, as this script relies on real DCS radar detections.
2. In Python, run:
   ```bash
   pip install -r python_gci/requirements.txt
   python python_gci/app.py
   ```

## Features
- **Realistic Detections:** Enemy aircraft are only drawn if a Blue coalition radar can physically see them.
- **Modern UI:** Built on PyQt6 with a dark, high-performance radar scope.
- **Velocity Vectors:** Shows heading and speed for all tracks.
- **Altitude Tags:** Displays altitude in thousands of feet (Flight Level).
