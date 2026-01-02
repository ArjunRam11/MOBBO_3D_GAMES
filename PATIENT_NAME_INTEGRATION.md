# Patient Name Integration - From Godot to Python

## Overview

The patient name is now automatically retrieved from the Godot registry (`registry.tscn`) and sent to Python with the recording command. This enables the proper folder structure:

```
Mobbo_data/
└── [ACTUAL_PATIENT_NAME]/
    └── session_DDMMYYYY_HHMMSS/
        ├── Board_Data/
        │   └── Board_Poses.json
        ├── CoP_Data/
        │   └── data_*.csv
        └── Foot_Data/
            └── foot_*.csv
```

## How It Works

### 1. Patient Login in Godot (registry.tscn)
```
User logs in → PatientDB.current_patient_id set → Patient name stored in PatientDB
```

Patient data stored as:
```gdscript
PatientDB.patient_register[hospital_id] = {
    "name": patient_name,  # ← This is what we retrieve
    "age": age,
    "gender": gender,
    ...
}
```

### 2. Recording Start in Godot (timer_manager.gd)

When user clicks "Start Recording" button:

```gdscript
# timer_manager.gd (lines 232-274)
func send_recording_command(state: bool, trial_path: String):
    # Get current patient name from PatientDB
    var patient_name: String = ""
    if PatientDB and PatientDB.current_patient_id != "":
        var patient_data = PatientDB.get_patient(PatientDB.current_patient_id)
        if patient_data and patient_data.has("name"):
            patient_name = patient_data["name"]
            print("📋 Patient name retrieved: %s" % patient_name)

    # Create command packet with patient name
    var command = {
        "action": "toggle_recording",
        "state": state,
        "trial_path": trial_path,
        "patient_name": patient_name,  # ← INCLUDED!
        "timestamp": Time.get_ticks_msec()
    }

    # Send via UDP to Python port 9000
    udp_socket.put_packet(json_string.to_utf8_buffer())
```

**JSON Packet Sent to Python:**
```json
{
    "action": "toggle_recording",
    "state": true,
    "trial_path": "trial_24122025_193000",
    "patient_name": "arjn",
    "timestamp": 1234567890
}
```

### 3. Recording Command in Python (main.py)

When Python receives the command (lines 890-934):

```python
elif command.get('action') == 'toggle_recording':
    recording_state = command.get('state', False)
    trial_name = command.get('trial_path', '')
    patient_name = command.get('patient_name', '').strip()  # ← FROM GODOT!

    print(f"Record command received: state={recording_state}, trial_name={trial_name}, patient='{patient_name}'")

    if recording_state and trial_name:
        # Pass patient_name to the recorder
        self.mobbo.set_recording_state(recording_state, trial_path, patient_name=patient_name)
```

### 4. Folder Creation in Python (board_pose_json_recorder.py)

The recorder creates the complete hierarchy:

```python
def _create_session_folder(self, patient_name: str, trial_path: str) -> str:
    # Build: Mobbo_data/[PATIENT_NAME]/session_[TIMESTAMP]/
    base_path = os.path.join(os.getcwd(), "Mobbo_data")
    patient_dir = os.path.join(base_path, patient_name)

    os.makedirs(patient_dir, exist_ok=True)  # Create patient folder

    timestamp = datetime.now().strftime("%d%m%Y_%H%M%S")
    session_name = f"session_{timestamp}"
    session_folder = os.path.join(patient_dir, session_name)

    os.makedirs(session_folder, exist_ok=True)  # Create session folder
    return session_folder
```

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ GODOT GAME ENGINE                                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  registry.tscn                                              │
│  ├─ Patient Login                                           │
│  ├─ PatientDB.current_patient_id = "hospital_id_123"       │
│  └─ PatientDB.patient_register[...]["name"] = "arjn"       │
│                                                             │
│  timer_manager.gd                                           │
│  ├─ User clicks "Start Recording"                          │
│  ├─ Retrieves: patient_data = PatientDB.get_patient(...)   │
│  ├─ Extracts: patient_name = patient_data["name"]          │
│  └─ Sends JSON with patient_name to Python via UDP:9000    │
│                                                             │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           │ UDP Port 9000
                           │ JSON: {
                           │   "action": "toggle_recording",
                           │   "state": true,
                           │   "trial_path": "trial_...",
                           │   "patient_name": "arjn"  ← KEY!
                           │ }
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ PYTHON BACKEND (main.py)                                    │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Receives command on port 9000                              │
│  ├─ Extracts: patient_name = command["patient_name"]        │
│  ├─ Calls: mobbo.set_recording_state(..., patient_name=...) │
│  │                                                           │
│  └─ COP_wifi_data.py                                        │
│     └─ Calls: initialize_recorder(patient_name, trial_path) │
│                                                              │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│ FOLDER CREATION (board_pose_json_recorder.py)               │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  patient_name = "arjn"                                      │
│  timestamp = "24122025_193000"                              │
│                                                              │
│  Creates:                                                   │
│  ├─ Mobbo_data/                                             │
│  │  └─ arjn/                          ← PATIENT FOLDER      │
│  │     └─ session_24122025_193000/    ← SESSION FOLDER      │
│  │        ├─ Board_Data/                                    │
│  │        │  └─ Board_Poses.json                            │
│  │        ├─ CoP_Data/                                      │
│  │        │  └─ data_192.168.0.100_...csv                  │
│  │        └─ Foot_Data/                                    │
│  │           └─ foot_data_...csv                           │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

## Expected Python Console Output

When recording starts:

```
Record command received: state=True, trial_name=trial_24122025_193000, patient='arjn'
✅ Patient name from Godot: arjn
📁 Creating folder for patient: arjn
✅ Recording started
   Patient: arjn
   Folder will be created: Mobbo_data/arjn/session_[timestamp]/

📍 Building session structure for patient: arjn
   Base path: E:\...\Mobbo_data
   Patient dir: E:\...\Mobbo_data\arjn
✅ Patient directory ready: E:\...\Mobbo_data\arjn
✅ New session folder created: E:\...\Mobbo_data\arjn\session_24122025_193000
✅ JSON recorder initialized for patient 'arjn' at: E:\...\Mobbo_data\trial_24122025_193000
✅ Session folder set: E:\...\Mobbo_data\arjn\session_24122025_193000
✅ CoP data folder: E:\...\Mobbo_data\arjn\session_24122025_193000\CoP_Data
📊 CoP CSV file opened: E:\...\CoP_Data\data_192.168.0.100_23000_24122025_193000.csv
```

## Testing Checklist

### Before Testing
- [ ] Restart Python interpreter (clear __pycache__)
- [ ] Ensure Godot game is running
- [ ] Ensure Python is running with new code

### Test Steps
1. **Login to Patient Registry**
   - Open Godot game
   - Go to Patient Registry (registry.tscn)
   - Select a patient (or create new one with name "arjn")
   - Click "Login"

2. **Start Recording**
   - In game, click "Start Recording" button
   - **Check Godot Console Output:**
     ```
     📋 Patient name retrieved: arjn
     Recording command sent to Python: {"action":"toggle_recording",...,"patient_name":"arjn"}
     ```

3. **Verify Python Received Patient Name**
   - Check Python console for:
     ```
     Record command received: state=True, trial_name=trial_..., patient='arjn'
     ✅ Patient name from Godot: arjn
     ```

4. **Verify Folder Structure Created**
   - Navigate to: `Mobbo_data/arjn/session_DDMMYYYY_HHMMSS/`
   - Should see:
     - `Board_Data/Board_Poses.json`
     - `CoP_Data/data_*.csv`
     - `Foot_Data/foot_*.csv`

5. **Verify JSON Metadata**
   - Open `Board_Poses.json`
   - Should contain:
     ```json
     {
         "metadata": {
             "patient_name": "arjn",
             "session_folder": "session_24122025_193000",
             ...
         },
         "poses": [...]
     }
     ```

6. **Stop Recording**
   - Click "Stop Recording" button
   - Verify timer resets to 00:00:00
   - Check Python console for "Recording stopped" message

## Fallback Behavior

If patient name is **NOT** provided by Godot:

```python
if not patient_name:
    patient_name = "unknown_patient"
    print(f"⚠️ No patient name from Godot. Using: {patient_name}")
```

Folder created as:
```
Mobbo_data/unknown_patient/session_DDMMYYYY_HHMMSS/...
```

## Files Modified

| File | Changes | Lines |
|------|---------|-------|
| `timer_manager.gd` | Added patient name retrieval from PatientDB | 238-248 |
| `main.py` | Extract and use patient_name from Godot command | 894, 908-915 |
| `board_pose_json_recorder.py` | Already supports patient_name parameter | 65, 102-139 |
| `COP_wifi_data.py` | Already supports patient_name parameter | 232-268 |

## Integration Status

✅ **COMPLETE**
- Godot retrieves patient name from registry
- Godot sends patient name in recording command
- Python receives and uses patient name
- Folder structure created with patient name
- JSON metadata includes patient name

## Next Steps

1. **Test with real patient data** - Verify folder structure correct
2. **Monitor Python logs** - Ensure no "unknown_patient" warnings
3. **Verify CoP data recording** - CSV files in correct location
4. **Check board pose JSON** - Verify patient_name and file paths included
5. **(Optional) Update Godot UI** - Show patient name in recording status display

## Troubleshooting

### Issue: Folder created as "unknown_patient"
**Cause:** PatientDB not initialized or patient not logged in properly
**Solution:**
- Ensure patient is selected in registry
- Check that login button is clicked
- Verify PatientDB.current_patient_id is set

### Issue: Patient name not in JSON
**Cause:** Old Python process still running
**Solution:**
- Kill all Python processes
- Clear __pycache__ folders
- Restart Python

### Issue: No folders created at all
**Cause:** recording_state not being set properly
**Solution:**
- Check Python console for errors
- Verify Godot is sending JSON with correct format
- Check that "patient_name" field is present in JSON

## References

- **Godot Registry Script:** `NOARKGames/Main_screen/Scripts/registry.gd` (line 219)
- **PatientDB Location:** `NOARKGames/Main_screen/Scripts/patient_db.gd` (lines 12, 108-119)
- **Timer Manager Recording:** `NOARKGames/Games/BoardViz/timer_manager.gd` (lines 232-274)
- **Python Main Handler:** `main.py` (lines 890-934)
- **JSON Recorder Patient Support:** `board_pose_json_recorder.py` (lines 65, 102-139)
