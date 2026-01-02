# Testing the New Folder Structure Implementation

## Pre-Test Checklist

Before testing, ensure:
1. Python interpreter is restarted (to clear cache from previous versions)
2. No processes are holding locks on Mobbo_data folder
3. Old test data can be safely deleted
4. Godot game is running and connected to Python UDP socket (port 8000)

## Test Scenario 1: First-Time Recording (Single Patient)

### Setup
1. Start Python main.py
2. Godot: Login with patient name "test_patient_001"
3. Godot: Set up board layout with 2 boards in 1x2 arrangement

### Action
1. Click "Start Recording" button in Godot
2. Wait 5 seconds for CoP data to arrive
3. Observe Python console for logs
4. Click "Stop Recording" button

### Expected Results
```
✅ Folder Structure Created:
Mobbo_data/
└── test_patient_001/
    └── session_DDMMYYYY_HHMMSS/    (e.g., session_24122025_150000)
        ├── Board_Data/
        │   └── Board_Poses.json    (NEW - with layout info and CSV paths)
        ├── CoP_Data/
        │   ├── data_192.168.0.100_23000_DDMMYYYY_HHMMSS.csv
        │   └── data_192.168.0.101_23000_DDMMYYYY_HHMMSS.csv
        └── Foot_Data/
            └── foot_data_DDMMYYYY_HHMMSS.csv

✅ Python Console Output:
   "✅ JSON recorder initialized for patient 'test_patient_001' at: ..."
   "✅ Session folder set: e:\...\Mobbo_data\test_patient_001\session_24122025_150000"
   "✅ CoP data folder: e:\...\Mobbo_data\test_patient_001\session_24122025_150000\CoP_Data"
   "📊 CoP CSV file opened: ...data_192.168.0.100_23000_24122025_150000.csv"
   "📊 CoP CSV file opened: ...data_192.168.0.101_23000_24122025_150000.csv"
   "💾 Board pose 1 saved to JSON (...Board_Poses.json)"
   "   CoP data: CoP_Data/data_192.168.0.100_23000_24122025_150000.csv"

✅ JSON File Structure (Board_Poses.json):
{
    "metadata": {
        "patient_name": "test_patient_001",
        "session_folder": "session_24122025_150000",
        "created_at": "2025-12-24T15:00:XX.XXX",
        "total_poses": 1
    },
    "board_layout": {
        "num_boards": 2,
        "layout": "1x2",
        ...
    },
    "poses": [
        {
            "timestamp": "2025-12-24T15:00:XX.XXX",
            "board_data": [...],
            "data_files": {
                "cop_data": "CoP_Data/data_192.168.0.100_23000_24122025_150000.csv",
                "foot_data": null  (or Foot_Data path if foot recording enabled)
            }
        }
    ]
}

✅ Godot Display:
   Board visualization renders correctly
   CoP and GCoP markers update in real-time
   All data renders properly
```

## Test Scenario 2: Multiple Recording Sessions (Same Session)

### Setup
Session from Test Scenario 1 is complete and folder structure exists

### Action
1. Click "Start Recording" again (without restarting Python or Godot)
2. Wait 3 seconds
3. Click "Stop Recording"

### Expected Results
```
✅ Same Session Folder Reused:
Mobbo_data/test_patient_001/session_24122025_150000/
├── Board_Data/
│   └── Board_Poses.json (UPDATED - now has 2 poses)
├── CoP_Data/
│   ├── data_192.168.0.100_23000_24122025_150000.csv (from first recording)
│   ├── data_192.168.0.101_23000_24122025_150000.csv (from first recording)
│   ├── data_192.168.0.100_23000_24122025_150005.csv (NEW - from second recording)
│   └── data_192.168.0.101_23000_24122025_150005.csv (NEW - from second recording)
└── Foot_Data/
    ├── foot_data_24122025_150000.csv (from first recording)
    └── foot_data_24122025_150005.csv (NEW - from second recording)

✅ Python Console Output:
   "✅ Recording started - Trial path: ..."
   "📊 CoP CSV file opened: ...data_192.168.0.100_23000_24122025_150005.csv"
   "💾 Board pose 2 saved to JSON"

✅ JSON File Updated:
{
    "metadata": {
        "total_poses": 2
    },
    "poses": [
        { "timestamp": "2025-12-24T15:00:XX", ... },  // First pose
        { "timestamp": "2025-12-24T15:00:YY", ...     // Second pose with new CSV paths
           "data_files": {
               "cop_data": "CoP_Data/data_192.168.0.100_23000_24122025_150005.csv"
           }
        }
    ]
}
```

## Test Scenario 3: Board Reset During Recording

### Setup
Recording is active (from Test Scenario 2)

### Action
1. Godot: Click "Reset Board" button
2. Python detects board repositioning
3. New board pose calculated

### Expected Results
```
✅ Folder Structure Unchanged:
   Same session folder, no new folders created

✅ Python Console Output:
   "🔄 Recording new board pose #3"
   "💾 Board pose 3 saved to JSON"
   "   CoP data: CoP_Data/data_192.168.0.100_23000_24122025_150005.csv"

✅ JSON File Appended:
{
    "metadata": {
        "total_poses": 3
    },
    "poses": [
        { ... pose 1 ... },
        { ... pose 2 ... },
        {
            "timestamp": "2025-12-24T15:00:ZZ",
            "board_data": [...NEW POSITIONS...],
            "data_files": {
                "cop_data": "CoP_Data/data_192.168.0.100_23000_24122025_150005.csv"
                // Still references CURRENT recording's CSV, not new one
            }
        }
    ]
}

✅ Key Point:
   - Reset does NOT create new CSV files
   - Reset does NOT create new session folder
   - Reset ONLY appends new pose to existing JSON
   - Board pose history preserved
```

## Test Scenario 4: Different Patient (New Login)

### Setup
Test Scenario 3 complete

### Action
1. Godot: Logout (end session)
2. Godot: Login with different patient "test_patient_002"
3. Click "Start Recording"

### Expected Results
```
✅ New Patient Folder Created:
Mobbo_data/
├── test_patient_001/
│   └── session_24122025_150000/
│       └── (existing data unchanged)
└── test_patient_002/
    └── session_24122025_150015/    (NEW - different timestamp!)
        ├── Board_Data/
        │   └── Board_Poses.json
        ├── CoP_Data/
        │   └── (new CSV files for this patient)
        └── Foot_Data/

✅ Python Console Output:
   "✅ JSON recorder initialized for patient 'test_patient_002' at: ..."
   "✅ Session folder set: e:\...\Mobbo_data\test_patient_002\session_24122025_150015"

✅ Important:
   - Completely separate folders for each patient
   - Different timestamps for different session starts
   - Original patient_001 data untouched
```

## Verification Checklist

After running the tests, verify:

### Folder Structure
- [ ] Patient folders exist: `Mobbo_data/[patient_name]/`
- [ ] Session folder exists: `Mobbo_data/[patient]/session_DDMMYYYY_HHMMSS/`
- [ ] Three subfolders exist: Board_Data, CoP_Data, Foot_Data
- [ ] Board_Poses.json exists in Board_Data folder
- [ ] CSV files exist in CoP_Data and Foot_Data folders with timestamps

### JSON File Content
- [ ] metadata.patient_name matches logged-in patient
- [ ] metadata.session_folder matches actual folder name
- [ ] board_layout contains all expected fields (layout, rows, cols, etc.)
- [ ] poses array has correct number of entries
- [ ] Each pose has data_files with cop_data path
- [ ] File paths are relative and correctly formatted (e.g., "CoP_Data/...")
- [ ] All poses are appended (not overwritten on reset)

### CSV Files
- [ ] CSV files have correct naming with IP and timestamp
- [ ] CSV files have proper header row
- [ ] CSV files contain data rows
- [ ] Multiple recordings create multiple CSV files with different timestamps
- [ ] Reset does NOT create new CSV files

### Console Logging
- [ ] All initialization messages appear
- [ ] Patient name is correctly logged
- [ ] Session folder path is correctly logged
- [ ] CoP data folder path is correctly logged
- [ ] Board pose recording shows file paths
- [ ] No errors or exceptions in logs

### Data Integrity
- [ ] Board visualization renders correctly
- [ ] CoP data renders correctly
- [ ] GCoP marker positions correct
- [ ] Reset causes board to re-render correctly
- [ ] Multiple recordings don't interfere with each other

## Common Issues and Solutions

### Issue 1: JSON File Not Created
**Symptom**: Board_Poses.json doesn't exist in Board_Data folder
**Cause**:
- JSON recorder not initialized
- board_save flag not set
- Folder permissions issue

**Solution**:
- Check console for "JSON recorder initialized" message
- Verify board_save=True when recording starts
- Check folder write permissions

### Issue 2: CSV Files Not Created
**Symptom**: CoP_Data folder is empty
**Cause**:
- cop_data_folder not set from session folder
- start_recording() called with invalid folder

**Solution**:
- Check console for "CoP data folder set" message
- Verify cop_data_folder is set before recording starts
- Check that CoP data is actually being received

### Issue 3: Folder Structure Wrong
**Symptom**: Files created in flat structure, not patient/session hierarchy
**Cause**:
- Old code still running
- Python cache not cleared
- _recorder_instance not reinitialized

**Solution**:
- Restart Python completely (kill process)
- Clear __pycache__ folders
- Verify initialize_recorder called with correct patient_name

### Issue 4: Multiple CSV Files in CoP_Data Per Recording
**Symptom**: CoP CSV files have different timestamps for same recording session
**Cause**:
- start_recording called multiple times
- Multiple IP addresses creating separate files

**Solution**:
- This is expected! Multiple addresses = multiple CSV files
- Timestamp should be the same if started in same recording session
- If different timestamps, recording was stopped and restarted

## Performance Considerations

- **Folder creation**: Minimal overhead (happens once per session)
- **JSON persistence**: Load on init, write on each board pose (few KB files)
- **CSV generation**: One per address per recording start (continuous append)
- **File path tracking**: In-memory storage (no disk overhead)

## Next Steps After Validation

1. Confirm all test scenarios pass
2. Clear old test data
3. Deploy to production environment
4. Update Godot game to include patient_name in commands
5. Run with real patient data to confirm workflow
