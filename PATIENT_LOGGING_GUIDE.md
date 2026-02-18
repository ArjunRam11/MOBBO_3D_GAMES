# Patient Data Logging System

## Overview
This system automatically logs CoP (Center of Pressure) and foot keypoint data for each patient. The data is saved in CSV files organized by patient name and session date.

## Folder Structure
```
NOARKGames/
└── Mobbo_data/
    ├── effe/
    │   └── session1_02012026_162443/
    │       ├── CoP_20260102_162443.csv
    │       └── FootKeypoints_20260102_162443.csv
    ├── Arjun/
    │   └── session1_20251226_163926/
    │       ├── CoP_20251226_163926.csv
    │       └── FootKeypoints_20251226_163926.csv
    └── [patient_name]/
        └── session[N]_DDMMYYYY_HHMMSS/
            ├── CoP_DDMMYYYY_HHMMSS.csv
            └── FootKeypoints_DDMMYYYY_HHMMSS.csv
```

## Integration with Godot

### 1. Setting Patient Name from Godot
When a patient logs in via Godot, send their patient ID to Python:

```gdscript
# From Godot (in global_script.gd or wherever you handle patient login)
var patient_id = "patient_name"  # e.g., "effe", "Arjun"
_outgoing_message = "PATIENT:" + patient_id
udp.put_packet(_outgoing_message.to_utf8_buffer())
```

### 2. Handling Patient Messages in Python
In your main.py or data processing thread, parse the patient ID message:

```python
# When receiving from Godot
if message.startswith("PATIENT:"):
    patient_id = message.replace("PATIENT:", "").strip()
    godot_bridge_helper.set_patient(patient_id)
    print(f"✅ Patient set to: {patient_id}")
```

## Usage in Python

### Starting Logging
```python
# Set patient first
godot_bridge_helper.set_patient("Arjun")

# Then start logging
success = godot_bridge_helper.start_patient_logging()
if success:
    print("🔴 Logging started")
```

### Stopping Logging
```python
success = godot_bridge_helper.stop_patient_logging()
if success:
    print("⚪ Logging stopped")
```

### Logging Foot Keypoints
```python
# When you have foot keypoint data
left_heel = (x1, y1, z1)
left_toe = (x2, y2, z2)
right_heel = (x3, y3, z3)
right_toe = (x4, y4, z4)

godot_bridge_helper.log_foot_keypoints_internal(
    left_heel, left_toe, right_heel, right_toe
)
```

### Checking Logging Status
```python
status = godot_bridge_helper.get_status()
print(status['patient_logging'])
# Output:
# {
#     'is_logging': True,
#     'current_patient': 'Arjun',
#     'cop_file': '.../Mobbo_data/Arjun/session1_.../CoP_...csv',
#     'foot_file': '.../Mobbo_data/Arjun/session1_.../FootKeypoints_...csv',
#     'buffered_cop_records': 0,
#     'buffered_foot_records': 0,
#     'logging_duration': 123.45
# }
```

## CSV File Formats

### CoP Data (CoP_DDMMYYYY_HHMMSS.csv)
```
timestamp,epoch_time,gcop_x,gcop_y,gcop_z,gcop_weight,local_cops_count
2026-01-02T16:24:43.123456,1735851883.123456,0.15,-0.08,0.0,45.2,2
2026-01-02T16:24:43.133456,1735851883.133456,0.14,-0.09,0.0,45.5,2
```

### Foot Keypoints (FootKeypoints_DDMMYYYY_HHMMSS.csv)
```
timestamp,epoch_time,left_heel_x,left_heel_y,left_heel_z,left_toe_x,left_toe_y,left_toe_z,right_heel_x,right_heel_y,right_heel_z,right_toe_x,right_toe_y,right_toe_z
2026-01-02T16:24:43.123456,1735851883.123456,-0.10,0.25,0.05,-0.08,0.35,0.02,0.12,0.24,0.04,0.14,0.36,0.01
```

## Features

✅ **Automatic Session Numbering** - Sessions are numbered (1, 2, 3...) automatically
✅ **Atomic Writes** - Data is buffered and flushed every 1 second for reliability
✅ **Thread-Safe** - Uses locks to prevent data corruption
✅ **Timestamp Tracking** - Both ISO format and Unix epoch timestamps
✅ **Multiple Patients** - Supports unlimited patients with organized folder structure

## Integration with Existing Recording System

The patient logging system works alongside the existing "Start Recording" button:
- **Start Recording** button → saves video and other media
- **Patient Logging** → saves CSV data automatically when logging is started

Both can run simultaneously without interference.

## Notes

- Session folders are created automatically with timestamps
- Data is automatically flushed to disk every 1 second
- Logging stops gracefully when `stop_patient_logging()` is called
- All data files are in CSV format for easy analysis in Python, MATLAB, Excel, etc.
