# JSON Board Pose Recording Implementation Summary

## Overview
Converted board pose saving from CSV format to JSON format with automatic accumulation of multiple poses and board layout information.

## Files Created

### 1. `board_pose_json_recorder.py` (NEW)
**Purpose:** Core module for JSON-based board pose recording

**Key Components:**
- `BoardPoseJSONRecorder` class: Main recorder for board pose data
  - `__init__(trial_path)`: Initialize recorder for a trial
  - `set_board_layout(layout_data)`: Store board layout information
  - `record_board_pose(board_position_list)`: Record a pose and append to JSON
  - `_format_board_data()`: Convert numpy arrays to JSON-serializable format
  - `_write_json_atomic()`: Atomic file writes to prevent corruption
  - `poses_get()`: Get list of recorded poses
  - `get_json_file_path()`: Get path to JSON file

- Global functions for module-level access:
  - `initialize_recorder(trial_path)`: Initialize global instance
  - `get_recorder()`: Get global instance
  - `set_board_layout(layout_data)`: Set layout on global instance
  - `record_board_pose_global(board_position_list)`: Record using global instance

**File Structure:**
```
Board_Data/
└── Board_Poses_{timestamp}.json  (single file, accumulates multiple poses)
```

## Files Modified

### 1. `COP_wifi_data.py`
**Changes:**
- Added imports:
  - `from board_pose_json_recorder import BoardPoseJSONRecorder, initialize_recorder, set_board_layout, record_board_pose_global`
  - `import logging`

- Added global variable:
  - `json_recorder = None` (line 24): Global JSON recorder instance

- Modified `record_board_data()` method:
  - **Old:** Wrote CSV file with board data
  - **New:** Uses global `json_recorder` to append pose to JSON
  - Flattens nested board position data before recording
  - Logs JSON file path instead of CSV filename

- Modified `set_recording_state()` method:
  - **Old:** Just set flags, no recorder initialization
  - **New:** Initializes `json_recorder` when recording starts (first time only)
  - Reuses same recorder instance for all poses in trial
  - Logs recorder initialization

- Added new method `set_board_layout(layout_data)`:
  - Passes board layout information to JSON recorder
  - Called from main.py after layout analysis

### 2. `main.py`
**Changes:**
- Modified board layout analysis section (lines 772-774):
  - Added call to `self.mobbo.set_board_layout(layout_formatted)`
  - Passes analyzed board layout to recording system
  - Integrates layout info into JSON file

## Documentation Created

### 1. `BOARD_POSE_JSON_DOCUMENTATION.md`
Complete documentation including:
- How it works (recording flow)
- File location and structure
- JSON format with examples
- Key features (accumulation, atomicity, etc.)
- Python implementation details
- Usage from Godot
- Data analysis examples
- Advantages over CSV
- Troubleshooting guide

### 2. `JSON_RECORDING_IMPLEMENTATION_SUMMARY.md` (this file)
Technical summary of implementation

## Data Flow

### Recording Initiation
```
Godot Button (Start)
  ↓
UDP: toggle_recording(state=true, trial_path)
  ↓
Python: timer_manager.send_recording_command()
  ↓
Python: BOSEstimator.handle_recording_command()
  ↓
main.py: mobbo.set_recording_state(True, trial_path)
  ↓
COP_wifi_data.py: MobboData.set_recording_state()
  ↓
Initialize: json_recorder = BoardPoseJSONRecorder(trial_path)
```

### Board Layout Analysis
```
ArUco boards detected
  ↓
main.py: analyze_board_layout(translations_dict)
  ↓
Get: layout_formatted = format_layout_for_godot(layout_info)
  ↓
Pass to recording: mobbo.set_board_layout(layout_formatted)
  ↓
COP_wifi_data.py: json_recorder.set_board_layout(layout_data)
  ↓
board_pose_json_recorder.py: Store in self.board_layout_data
```

### Board Pose Recording
```
Recording active & board_save flag set
  ↓
COP_wifi_data.py: record_board_data()
  ↓
Flatten board_position data
  ↓
json_recorder.record_board_pose(board_data_list)
  ↓
Create pose entry with timestamp
  ↓
Add pose to self.poses list
  ↓
Build complete JSON with layout
  ↓
Write atomically to file
  ↓
Log "Board pose N saved to JSON"
```

### Reset (Subsequent Recordings)
```
Godot Button (Start again)
  ↓
Same flow as Recording Initiation
  ↓
json_recorder already exists (not reinitialized)
  ↓
Second board_save flag triggers second record_board_data()
  ↓
New pose appended to self.poses
  ↓
SAME JSON file updated with additional pose
```

## JSON Output Structure

```json
{
  "metadata": {
    "recording_session": "trial_20251224_143744",
    "created_at": "2025-12-24T14:37:44.650",
    "total_poses": 3
  },
  "board_layout": {
    "num_boards": 2,
    "layout": "1x2",
    "rows": 1,
    "cols": 2,
    "arrangement_type": "left_right",
    "board_grid": [[11, 12]],
    "spacing": {
      "x_spacing": 61.69,
      "y_spacing": 4.73
    },
    "alignment_quality": {...},
    "board_positions": {"11": {"x": 0.0, "y": 0.0}, "12": {"x": 61.69, "y": 4.73}}
  },
  "poses": [
    {
      "timestamp": "2025-12-24T14:37:44.650",
      "board_data": [
        {
          "board_translation": [0.0, 0.0, 1.0],
          "ip_address": "192.168.0.102",
          "angle": [0.1, 0.2, 0.3],
          "rotation_matrix": [1, 0, 0, 0, 1, 0, 0, 0, 1],
          "board_aruco_ids": [11]
        }
      ]
    },
    {
      "timestamp": "2025-12-24T14:37:50.123",
      "board_data": [...]
    },
    {
      "timestamp": "2025-12-24T14:37:56.450",
      "board_data": [...]
    }
  ]
}
```

## Key Benefits

1. **Single File Per Trial:** All poses accumulated in one JSON instead of multiple CSVs
2. **Layout Included:** Board layout information automatically included
3. **Atomic Writes:** JSON file written atomically to prevent corruption
4. **Easy Parsing:** JSON format is structured and language-agnostic
5. **Timestamp Tracking:** Each pose timestamped for temporal analysis
6. **No Godot Changes:** Completely transparent to Godot code
7. **Backward Compatible:** Old CSV data not deleted, coexists with new JSON

## Testing Recommendations

1. **Single Recording:**
   - Click Start
   - Boards detected
   - Verify Board_Poses_*.json created
   - Verify layout included in JSON
   - Click Stop

2. **Multiple Resets:**
   - Click Start
   - Verify first pose in JSON
   - Click Reset (or Stop + Start)
   - Verify second pose APPENDED to same file
   - Click Reset again
   - Verify third pose added
   - Check total_poses count is 3

3. **Layout Verification:**
   - Open JSON file
   - Verify "board_layout" section contains:
     - Correct layout (1x2, 2x1, etc.)
     - Correct spacing values
     - Correct board arrangement type

4. **Data Integrity:**
   - Verify no numpy arrays in JSON (all converted to lists)
   - Verify all data is JSON serializable
   - Verify timestamps are ISO format

## Backward Compatibility

- Old CSV files in Board_Data/ are not touched
- New JSON files use different naming pattern
- Godot code unchanged
- All existing functionality preserved
- Can gradually migrate to JSON format

## Migration Path (if needed)

To convert old CSV files to JSON format:

```python
import csv
import json

def csv_to_json(csv_file, trial_path):
    """Convert old CSV board_position file to JSON format"""
    board_data = []
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            board_data.append({
                'board_translation': json.loads(row['board_translation']),
                'ip_address': row['ip_address'],
                'angle': json.loads(row['angle']),
                'rotation_matrix': json.loads(row['rotation_matrix']),
                'board_aruco_ids': json.loads(row['board_aruco_ids'])
            })

    json_data = {
        'metadata': {
            'recording_session': 'migrated',
            'created_at': '2025-12-24T00:00:00',
            'total_poses': 1
        },
        'poses': [{
            'timestamp': '2025-12-24T00:00:00',
            'board_data': board_data
        }]
    }

    with open(f'{trial_path}/Board_Data/Board_Poses_migrated.json', 'w') as f:
        json.dump(json_data, f, indent=2)
```

## Performance Impact

**File Size:**
- JSON slightly larger than CSV (formatted with indentation)
- Single file overhead minimal
- Acceptable trade-off for structured data and included layout

**Write Time:**
- Similar to CSV (atomic write adds minimal overhead)
- No performance degradation

**Memory:**
- Poses accumulated in memory (manageable for typical trial length)
- For very long sessions (100+ resets), consider streaming

## Future Enhancements

1. Streaming JSON (JSONL format) for very long sessions
2. Compression (gzip) for large files
3. Real-time JSON viewer in Godot overlay
4. Automatic pose analysis and statistics
5. Visualization tools for pose drift detection
