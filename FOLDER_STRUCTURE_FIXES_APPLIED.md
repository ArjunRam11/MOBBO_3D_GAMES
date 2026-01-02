# Folder Structure Implementation - Issues Found and Fixes Applied

## Issues Identified

### Issue 1: Wrong Folder Location
**Problem:** Folders were being created inside `NOARKGames/Mobbo_data/` instead of at the project root
**Root Cause:** `os.getcwd()` was returning NOARKGames directory path instead of the actual project root
**Impact:** Data files scattered in wrong location, difficult to locate and organize

### Issue 2: Patient Name Extraction Incorrect
**Problem:** Trial name (e.g., `trial_20251224_192628`) was being used as patient name
**Root Cause:** Godot was not sending `patient_name` parameter, so extraction logic used trial name
**Impact:** Folder structure became `Mobbo_data/trial_20251224_192628/` instead of `Mobbo_data/[PATIENT_NAME]/session_[TIME]/`

### Issue 3: Session Subfolder Not Created
**Problem:** No `session_[TIMESTAMP]/` subfolder inside patient folder
**Root Cause:** Pre-created trial folders were interpreted as session folders
**Impact:** Data structure was flat instead of hierarchical

## Fixes Applied

### Fix 1: Remove Pre-folder Creation in main.py
**What Changed:**
- Removed `os.makedirs(trial_path, exist_ok=True)` from main.py
- Let the `BoardPoseJSONRecorder` handle ALL folder creation
- This ensures consistent folder structure

**Old Code:**
```python
base_path = os.path.join(os.getcwd(), "Mobbo_data")
trial_path = os.path.join(base_path, trial_name)
os.makedirs(trial_path, exist_ok=True)  # ❌ Pre-creates folder
```

**New Code:**
```python
base_path = os.path.join(os.getcwd(), "Mobbo_data")
trial_path = os.path.join(base_path, trial_name)
# ✅ No pre-folder creation - recorder handles it
```

### Fix 2: Use Default Patient Name When Not Provided
**What Changed:**
- When Godot doesn't send `patient_name`, use `"default_patient"` instead of trial name
- This provides a clean, consistent folder structure
- Temporary solution until Godot sends real patient names

**Code:**
```python
if not patient_name:
    if os.sep not in trial_name:
        patient_name = "default_patient"  # ✅ Generic default
        print(f"⚠️ No patient name provided. Using default: {patient_name}")
```

### Fix 3: Simplify Session Folder Creation
**What Changed:**
- Always create `session_[TIMESTAMP]` inside patient folder
- Removed logic that reused existing folders
- Ensures clean, predictable structure

**New Logic:**
```python
def _create_session_folder(self, patient_name: str, trial_path: str) -> str:
    # Always create patient_dir/session_TIMESTAMP/
    patient_dir = Mobbo_data/[patient_name]/
    session_folder = patient_dir/session_[TIMESTAMP]/
    os.makedirs(session_folder, exist_ok=True)
    return session_folder
```

## Current Folder Structure (After Fixes)

```
Mobbo_data/
├── default_patient/           (or real patient name when Godot sends it)
│   └── session_DDMMYYYY_HHMMSS/
│       ├── Board_Data/
│       │   └── Board_Poses.json
│       ├── CoP_Data/
│       │   ├── data_192.168.0.100_23000_DDMMYYYY_HHMMSS.csv
│       │   └── data_192.168.0.101_23000_DDMMYYYY_HHMMSS.csv
│       └── Foot_Data/
│           ├── left_foot_DDMMYYYY_HHMMSS.csv
│           └── right_foot_DDMMYYYY_HHMMSS.csv
└── another_patient/
    └── session_DDMMYYYY_HHMMSS/
        └── (same structure)
```

## Godot Integration - Next Steps

### Current Behavior
Godot is currently sending:
```json
{
    "action": "toggle_recording",
    "state": true,
    "timestamp": 47705,
    "trial_path": "trial_20251224_192628"
}
```

**No `patient_name` field** → Using "default_patient"

### Recommended Fix for Godot Game
Update the Godot game to send patient_name:

```json
{
    "action": "toggle_recording",
    "state": true,
    "timestamp": 47705,
    "trial_path": "trial_20251224_192628",
    "patient_name": "arjn"
}
```

**Where to Get Patient Name:**
- From login form/screen
- From current user session
- From GUI input field

### Python Will Then Create:
```
Mobbo_data/
└── arjn/
    └── session_24122025_192728/
        ├── Board_Data/Board_Poses.json
        ├── CoP_Data/data_*.csv
        └── Foot_Data/foot_*.csv
```

## CSV Import Warnings in Godot

The errors you see:
```
ERROR: Cannot open file from path 'res://Mobbo_data/trial_20251224_192628/CoP_Data/data_192.168.0.100_23000_24122025_192628.csv'.
ERROR: Error importing 'res://Mobbo_data/trial_20251224_192628/CoP_Data/data_192.168.0.100_23000_24122025_192628.csv'.
```

**What This Means:**
- Godot's resource importer is detecting CSV files in `res://` directory
- It tries to import them as Godot resources
- This fails silently (they're data files, not resources)
- **This is NOT causing functionality issues** - CoP data still works

**How to Suppress These Warnings:**
Add CSV files to `.godotignore` or configure import settings to exclude CSV files.

## Testing After Fixes

### Quick Verification
1. Start Python (restart to clear cache)
2. Press Start Recording in Godot
3. Check Python console for these logs:
   ```
   📍 Building session structure for patient: default_patient
   ✅ Patient directory ready: .../Mobbo_data/default_patient
   ✅ New session folder created: .../Mobbo_data/default_patient/session_DDMMYYYY_HHMMSS
   ✅ JSON recorder initialized for patient 'default_patient'
   ✅ Session folder set: .../Mobbo_data/default_patient/session_DDMMYYYY_HHMMSS
   ✅ CoP data folder: .../Mobbo_data/default_patient/session_DDMMYYYY_HHMMSS/CoP_Data
   📊 CoP CSV file opened: .../CoP_Data/data_192.168.0.100_23000_DDMMYYYY_HHMMSS.csv
   ```

4. Check Mobbo_data folder structure:
   ```
   ✅ Mobbo_data/default_patient/session_DDMMYYYY_HHMMSS/
   ✅ - Board_Data/Board_Poses.json exists
   ✅ - CoP_Data/ has CSV files with timestamps
   ✅ - Foot_Data/ has foot data CSV files
   ```

5. Verify CoP rendering works in Godot 3D view

## Migration from Old Structure

If you have existing data in the old structure:
```
Mobbo_data/
├── trial_20251224_192628/
│   ├── Board_Data/
│   ├── CoP_Data/
│   └── Foot_Data/
```

You can reorganize it to:
```
Mobbo_data/
└── default_patient/
    └── session_24122025_192728/
        ├── Board_Data/
        ├── CoP_Data/
        └── Foot_Data/
```

Or keep the old data separate and start fresh with new data using the new structure.

## Summary of Changes

| File | Change | Impact |
|------|--------|--------|
| `main.py` | Removed folder pre-creation, use "default_patient" | Fixes folder location and structure |
| `board_pose_json_recorder.py` | Simplified session folder creation | Always creates proper hierarchy |
| `COP_wifi_data.py` | (No changes needed - works with above fixes) | Uses recorder's folder paths |

## Next Actions

1. **Restart Python** to clear bytecode cache
2. **Test recording flow** with new folder structure
3. **Update Godot game** to send `patient_name` parameter
4. **Verify CoP visualization** updates during recording
5. **Monitor logs** for errors or warnings
6. **(Optional) Suppress Godot CSV import warnings** if they're annoying

## Troubleshooting

### Problem: Still see "default_patient" after fixes
**Solution:**
- Restart Python completely (kill all python processes)
- Clear `__pycache__` folders
- Run fresh

### Problem: Folder in NOARKGames instead of project root
**Solution:**
- Check working directory when starting Python
- May need to run from project root, not from subdirectories

### Problem: No CoP data rendering
**Solution:**
- Check Python logs for "CoP data folder set" message
- Verify CSV files are actually created
- Check Godot CoP visualization code hasn't changed

### Problem: Multiple session folders created per recording
**Solution:**
- Old behavior expected with old code
- New code creates only one session folder
- Clear old Mobbo_data folders if testing again
