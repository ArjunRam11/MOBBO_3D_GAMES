# Data Folder Structure Implementation

## Overview
This document describes the restructured data folder organization system implemented to properly manage patient, session, and data file organization.

## New Folder Hierarchy

```
Mobbo_data/
└── [PATIENT_NAME]/                           # Patient directory (e.g., "arjn")
    └── session_[TIMESTAMP]/                  # Session directory (e.g., "session_24122025_145606")
        ├── Board_Data/
        │   └── Board_Poses.json             # Board pose data with layout info and CSV file paths
        ├── CoP_Data/
        │   ├── data_192.168.0.100_23000_[TIMESTAMP].csv
        │   └── data_192.168.0.101_23000_[TIMESTAMP].csv
        └── Foot_Data/
            └── foot_data_[TIMESTAMP].csv
```

## Key Changes

### 1. **Patient-Level Folder Organization**
- Each patient has their own folder under `Mobbo_data/[PATIENT_NAME]/`
- Patient folder is created automatically if it doesn't exist
- All sessions for a patient are stored under their folder

### 2. **Session Folder Persistence**
- One session folder is created per login/recording session
- Session folder persists across multiple recording start/stop cycles
- Session folder also persists across board resets
- Session folder name: `session_[TIMESTAMP]` where timestamp is from first recording start

### 3. **Separate Data Type Folders**
Inside each session folder, there are three dedicated folders:
- **Board_Data/**: Contains `Board_Poses.json` with board positioning data
- **CoP_Data/**: Contains timestamped CSV files for center of pressure data
- **Foot_Data/**: Contains timestamped CSV files for foot keypoint data

### 4. **Timestamped Data Files**
Each recording session generates new CSV files with timestamps:
- **CoP CSV**: `data_[IP]_[PORT]_[TIMESTAMP].csv`
- **Foot CSV**: `foot_data_[TIMESTAMP].csv`
- Timestamp format: `DDMMYYYY_HHMMSS` (e.g., `24122025_145608`)

### 5. **Board_Poses.json Structure**
The JSON file now includes:
- **metadata**: Patient name, session folder, creation timestamp, total poses
- **board_layout**: Board arrangement information (rows, cols, spacing)
- **poses**: Array of board poses, each containing:
  - `timestamp`: When the pose was recorded
  - `board_data`: Board position and rotation information
  - `data_files`: References to CoP and foot data CSV files

Example:
```json
{
    "metadata": {
        "patient_name": "arjn",
        "session_folder": "session_24122025_145606",
        "created_at": "2025-12-24T14:37:44.650",
        "total_poses": 2
    },
    "board_layout": {
        "num_boards": 2,
        "layout": "1x2",
        "rows": 1,
        "cols": 2,
        "arrangement_type": "left_right",
        "spacing": {"x_spacing": 61.69, "y_spacing": 4.73}
    },
    "poses": [
        {
            "timestamp": "2025-12-24T14:37:44.650",
            "board_data": [...],
            "data_files": {
                "cop_data": "CoP_Data/data_192.168.0.100_23000_24122025_145608.csv",
                "foot_data": "Foot_Data/foot_data_24122025_145608.csv"
            }
        },
        {
            "timestamp": "2025-12-24T14:37:50.123",
            "board_data": [...],
            "data_files": {...}
        }
    ]
}
```

## Recording Flow

### First Recording Start
1. Patient logs in with name (e.g., "arjn")
2. Recording start command received from Godot
3. System creates: `Mobbo_data/arjn/session_24122025_145606/`
4. Subfolders created: `Board_Data/`, `CoP_Data/`, `Foot_Data/`
5. New CSV files created with unique timestamp:
   - `CoP_Data/data_192.168.0.100_23000_24122025_145608.csv`
   - `Foot_Data/foot_data_24122025_145608.csv`
6. Board pose recorded with file path references

### Subsequent Recording Starts (Same Session)
1. Recording stop → CSV files closed
2. Recording start again → New CSV files created with new timestamp
3. Same session folder reused
4. New poses appended to existing `Board_Poses.json`

### Board Reset
1. Reset command received
2. Board pose redetected
3. New pose appended to existing `Board_Poses.json`
4. File references point to current recording's CSV files
5. No new folder created

## Modified Files

### 1. **board_pose_json_recorder.py**
- Now accepts `patient_name` parameter
- Creates/manages patient/session folder structure
- Automatically loads existing poses from JSON (for reset persistence)
- Records file path references in JSON
- `initialize_recorder(patient_name, trial_path)` signature updated

### 2. **COP_wifi_data.py**
- Tracks session folder and CoP data folder paths
- Creates timestamped CSV files in `CoP_Data/` subfolder
- Stores current recording's CSV path
- Passes CSV path to JSON recorder via `record_board_pose()`
- `set_recording_state()` accepts optional `patient_name` parameter

### 3. **main.py**
- Extracts patient name from Godot command or trial path
- Passes patient name to `set_recording_state()`
- Added debug logging for patient name handling

## Implementation Details

### Session Folder Creation Logic
```
If trial_path directory already exists:
    Use it as session folder
Else:
    Create new session folder with timestamp: session_DDMMYYYY_HHMMSS
```

### Patient Name Extraction
```
If patient_name explicitly provided:
    Use provided patient_name
Else if patient_name in trial_path:
    Extract first path component as patient_name
Else:
    Use "unknown_patient"
```

### CSV File Path Storage
- Absolute path: `Mobbo_data/arjn/session_24122025_145606/CoP_Data/data_*.csv`
- Relative path in JSON: `CoP_Data/data_*.csv`
- Allows JSON to be portable and reference files correctly

## Benefits of New Structure

1. **Better Organization**: Patient-level grouping makes it easy to find all data for a specific patient
2. **Session Persistence**: All data for a recording session stays in one folder
3. **Temporal Tracking**: Timestamps on CSV files show when each recording occurred
4. **Cross-Referenced Data**: JSON includes paths to all data files for easy correlation
5. **Reset Handling**: JSON accumulates poses instead of overwriting, preserving reset history
6. **Scalability**: Structure supports unlimited patients and sessions

## Migration Notes

Existing data in old format (flat structure) will need to be manually reorganized into the new patient/session structure if you want to maintain backward compatibility.
