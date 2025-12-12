# FBP Visualization Debugging Guide

## Current Status

**FBP is ENABLED in code**:
- ✅ Python: Sending FBP data (main.py:1008-1009)
- ✅ Python: BoS data also enabled (main.py:845-846)
- ✅ Godot: Listening on Port 8001 for FBP + BoS
- ✅ BoardSetup: Calling `update_fbp_from_network()` (BoardSetup.gd:91)

## Debug Output Added

I've added comprehensive debug logging to trace the FBP data flow:

### 1. Global Script (Port 8001 Reception)
**File**: [global_script.gd](NOARKGames/Main_screen/Scripts/global_script.gd)

```gdscript
# Lines 582-583: Packet reception check
🔍 FBP packet received on Port 8001

# Line 614: Keypoint count
  📍 FBP keypoints array size: 18

# Line 672: Success message
🧍 Body Pose: 18 keypoints detected
```

### 2. BoardSetup (Visualization)
**File**: [BoardSetup.gd](NOARKGames/Games/BoardViz/BoardSetup.gd)

```gdscript
# Line 483: Function called
🎬 BoardSetup: update_fbp_from_network() called

# Line 520: Keypoints received
  ✅ FBP keypoints received: 18 keypoints
```

---

## What To Check

### Run Godot and look for these messages every ~1.6 seconds:

#### ✅ **GOOD** - FBP Working:
```
🔍 FBP packet received on Port 8001
  📍 FBP keypoints array size: 18
🧍 Body Pose: 18 keypoints detected

🎬 BoardSetup: update_fbp_from_network() called
  ✅ FBP keypoints received: 18 keypoints
```

#### ❌ **BAD** - Not Receiving Data:
```
🎬 BoardSetup: update_fbp_from_network() called
  ❌ network_manager.fbp_data is null/empty
```
**Cause**: Port 8001 not receiving FBP packets from Python

#### ⚠️ **BAD** - Data Invalid:
```
⚠️ Keypoint X coord Y is null
⚠️ Keypoint X coord Y is not finite
```
**Cause**: FBP data contains null/NaN values - strict validation rejecting it

---

## Diagnostic Steps

### Step 1: Check Python is Sending to Port 8001
Look for this in Python console:
```
INFO - ✅ GodotBridgeHelper started (Dual UDP)
INFO -    Port 8000: Sending CoP + Board Pose
INFO -    Port 8001: Sending FBP + BoS
```

### Step 2: Check Godot is Listening on Port 8001
Godot console should show (only prints once at startup - currently commented):
```
✅ UDP socket bound to port 8001 - ready to receive FBP + BoS
```

### Step 3: Check Data Flow
Run Godot and watch for the debug messages above. The messages print **every 100 frames** (~1.6 seconds).

---

## Common Issues & Fixes

### Issue 1: "network_manager.fbp_data is null/empty"
**Cause**: FBP data not arriving on Port 8001

**Check**:
1. Is Python bridge started? Look for "Godot bridge started"
2. Is someone visible in camera frame?
3. Is MediaPipe detecting pose? Check Python console for keypoints

**Fix**: Ensure camera can see person and MediaPipe is running

---

### Issue 2: FBP data arriving but validation failing
**Symptoms**:
```
⚠️ Keypoint 5 coord 1 is null
```

**Cause**: Some keypoints have null values (not detected by MediaPipe)

**Fix**: The validation in global_script.gd is TOO STRICT. It rejects data if ANY coordinate is null.

**Solution**: We need to RELAX validation to allow null keypoints (just skip rendering them).

Let me know if you see this error and I'll fix the validation!

---

### Issue 3: Keypoints detected but spheres not visible
**Symptoms**:
```
✅ FBP keypoints received: 18 keypoints
```
But no skeleton visible in 3D view.

**Possible Causes**:
1. **Spheres are too small** - increase scale
2. **Spheres are outside camera view** - adjust camera
3. **Coordinate transformation wrong** - check POSITION_SCALE

---

## Next Step

**Run Godot now** and paste the debug output you see. This will tell us exactly where the FBP data flow is breaking!

Look for messages starting with:
- 🔍 (data reception)
- 🎬 (visualization attempt)
- ✅ (success)
- ❌ (failure with reason)
