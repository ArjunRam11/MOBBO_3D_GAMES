# Board Pose JSON Recording Documentation

## Overview

Board pose data is now automatically saved to JSON format instead of CSV. The JSON file includes board layout information and accumulates multiple board poses (one per reset) in a single file for each trial session.

## How It Works

### 1. Recording Flow

**Automatic Process (No Godot Changes Needed):**

1. **User clicks "Start" button in Godot**
   - Sends `toggle_recording` command via UDP to Python
   - Python initializes JSON recorder for the trial

2. **Board layout is analyzed**
   - Board positions are detected via ArUco markers
   - Layout is analyzed (1x2, 2x1, 2x2, etc.)
   - Layout data is passed to the recording system

3. **First board pose is recorded**
   - Board position data with rotation and translation is saved to JSON
   - Includes board layout information in the JSON metadata

4. **User clicks "Reset" button** (or starts new recording)
   - Second board pose is recorded
   - **Appended to the same JSON file** (not a new file)
   - All previous poses remain in the file

5. **Subsequent resets**
   - Additional poses continue to be appended to the same JSON
   - Single JSON file contains entire trial history

### 2. File Location

```
Mobbo_data/
└── {user_name}/
    └── session{N}_{date_time}/
        └── trial{N}_{date_time}/
            ├── Board_Data/                    ← Board poses saved here (NEW)
            │   └── Board_Poses_{timestamp}.json   (replaces old CSV files)
            ├── Cop_Data/
            ├── Foot_Data/
            └── Video/
```

**Key Difference from CSV:**
- Old: Multiple CSV files (one per reset) → `Board_Position_{timestamp}.csv`
- **New: Single JSON file** → `Board_Poses_{timestamp}.json`

### 3. JSON File Format

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
    "alignment_quality": {
      "x_variance": 0.04,
      "y_variance": 22.35,
      "x_aligned": true,
      "y_aligned": false,
      "alignment_threshold": 5.0
    },
    "board_positions": {
      "11": {"x": 0.0, "y": 0.0},
      "12": {"x": 61.69, "y": 4.73}
    }
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
        },
        {
          "board_translation": [0.6169, 0.0473, 1.05],
          "ip_address": "192.168.0.103",
          "angle": [0.1, 0.2, 0.3],
          "rotation_matrix": [1, 0, 0, 0, 1, 0, 0, 0, 1],
          "board_aruco_ids": [12]
        }
      ]
    },
    {
      "timestamp": "2025-12-24T14:37:50.123",
      "board_data": [...]  ← Second reset pose
    },
    {
      "timestamp": "2025-12-24T14:37:56.450",
      "board_data": [...]  ← Third reset pose
    }
  ]
}
```

## Key Features

### 1. Accumulation
- Each time you click Start/Reset, a new pose is added to the `poses` array
- **Same JSON file is updated** (not a new file created)
- No manual file management needed

### 2. Board Layout Included
- Layout information is stored once at the file level
- Available for all poses in the file
- Contains spacing, alignment quality, and board grid info

### 3. Atomic Writes
- JSON file is written atomically (temp file → rename)
- Prevents corruption if process crashes during write
- Safe for concurrent access

### 4. Full Pose History
- Complete record of all board poses during trial
- Each pose timestamped for temporal analysis
- Useful for tracking pose drift or calibration changes

### 5. JSON Serializable
- All numpy arrays converted to Python lists
- All data types compatible with JSON
- Easy to parse in any programming language

## Python Implementation

### Files Modified

#### 1. `board_pose_json_recorder.py` (NEW)
**Class:** `BoardPoseJSONRecorder`

```python
# Initialize for a trial
recorder = BoardPoseJSONRecorder(trial_path)

# Set board layout once
recorder.set_board_layout(layout_data_dict)

# Record poses (called on each Start/Reset)
json_file = recorder.record_board_pose(board_position_list)

# Each call appends to the same file
```

**Global Functions:**
```python
initialize_recorder(trial_path)  # Initialize global instance
set_board_layout(layout_data)    # Set layout on global instance
record_board_pose_global(board_list)  # Record using global instance
```

#### 2. `COP_wifi_data.py` (MODIFIED)
**New Method:**
```python
class MobboData:
    def set_board_layout(self, layout_data):
        """Set board layout information for JSON recording"""
        # Passes layout to JSON recorder
```

**Modified Method:**
```python
def set_recording_state(self, state, trial_path):
    # Now initializes JSON recorder when recording starts
    # Keeps same instance for entire trial
```

**Updated Method:**
```python
def record_board_data(self):
    # Now uses JSON recorder instead of CSV
    # Appends to existing JSON file
```

#### 3. `main.py` (MODIFIED)
```python
# After analyzing board layout:
if self.mobbo:
    self.mobbo.set_board_layout(layout_formatted)
```

## Usage from Godot

**No changes required!** The Godot code remains exactly the same:

1. Click "Start" button
   - Triggers `send_recording_command(true, trial_path)` via UDP
   - Python initializes JSON recorder

2. ArUco boards are detected
   - Board layout is analyzed
   - Automatically included in JSON

3. Click "Reset" or "Stop" then "Start" again
   - New pose is recorded
   - **Appended to same JSON file**

## File Size & Performance

**JSON vs CSV Comparison:**

| Aspect | CSV | JSON |
|--------|-----|------|
| Single pose, 2 boards | ~200 bytes | ~400 bytes |
| 5 poses, 2 boards | 5 files × 200B = 1KB | 1 file × 2KB = 2KB |
| 10 poses, 4 boards | 10 files × 500B = 5KB | 1 file × 7KB = 7KB |
| **Efficiency** | Multiple files | Single file ✓ |
| **Easy parsing** | Basic | Better (structured) ✓ |
| **Layout included** | No | Yes ✓ |

## Data Analysis Example (Python)

```python
import json

# Load the JSON file
with open('Board_Poses_20251224_143744.json', 'r') as f:
    data = json.load(f)

# Access layout information
layout = data['board_layout']
print(f"Board arrangement: {layout['layout']}")
print(f"Spacing X: {layout['spacing']['x_spacing']:.2f} cm")
print(f"Spacing Y: {layout['spacing']['y_spacing']:.2f} cm")

# Analyze pose changes over time
for pose_idx, pose in enumerate(data['poses']):
    timestamp = pose['timestamp']
    num_boards = len(pose['board_data'])
    print(f"Pose {pose_idx+1}: {timestamp}, {num_boards} boards")

    # Access board positions
    for board in pose['board_data']:
        trans = board['board_translation']
        ip = board['ip_address']
        print(f"  Board {ip}: position=({trans[0]:.3f}, {trans[1]:.3f}, {trans[2]:.3f})")
```

## Advantages

1. **Single File:** All poses for a trial in one place
2. **Layout Tracking:** Board layout included automatically
3. **Structured Data:** Hierarchical JSON format is cleaner than CSV
4. **Easy Integration:** Import with `json.load()`, parse immediately
5. **Searchable:** Can find specific poses by timestamp
6. **Extensible:** Easy to add new fields without breaking old files

## Backward Compatibility

- Old CSV files are not deleted
- New JSON files are saved alongside existing data
- No changes to Godot code required
- Completely transparent to user

## Troubleshooting

**Issue:** Board layout not in JSON file
- **Cause:** Layout analyzer didn't run before first recording
- **Solution:** Board detection must complete before clicking Start

**Issue:** Multiple JSON files created per trial
- **Cause:** Different trial paths used for each recording
- **Solution:** Use same `trial_path` for all resets in a trial

**Issue:** JSON file is empty or has no poses
- **Cause:** `set_board_data()` not called before recording
- **Solution:** Ensure board position data is set before recording starts

## Future Enhancements

1. Add pose analysis metrics (variance, drift detection)
2. Automatic JSON to CSV converter if needed
3. Real-time JSON viewer in Godot
4. Pose interpolation between resets
5. Comparison tool for multiple trials
