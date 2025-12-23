# Testing Guide - FBP/BoS Race Condition Fix

## Quick Start

### 1. Start the Application
```bash
python main.py
```

### 2. Open Godot Game
- Start the Godot game engine
- Connect to the MOBBO server

### 3. Watch the Console
Look for these messages in **Python console**:
```
✅ GodotBridgeHelper started (ATOMIC MODE):
   Port 8000: CoP + Board Pose
   Port 8001: FBP + BoS
```

Look for these messages in **Godot console**:
```
🔍 FBP packet received on Port 8001
  📍 FBP keypoints array size: 18
🧍 Body Pose: 18 keypoints detected
👣 BoS Data: Left=True, Right=True
```

---

## Testing Phases

### Phase 1: Quick Check (5 minutes)
**Objective:** Verify no immediate crashes

```
✅ FBP skeleton appears in 3D view
✅ BoS polygons appear in 3D view
✅ Movement tracking works smoothly
✅ No error messages in console
```

**If you see errors:**
- "Invalid type in function 'get'" → STILL A BUG
- "Null reference" → STILL A BUG
- Other errors → Check console output

---

### Phase 2: Stability Test (15 minutes)
**Objective:** Verify stability during normal use

- Walk around in front of the camera
- Perform various movements
- Watch FBP skeleton track your body
- Watch BoS polygons update with foot positions

**Expected behavior:**
- Smooth continuous tracking
- No glitches or gaps
- No momentary freezes
- No error messages

---

### Phase 3: Board Reset Test (5 minutes)
**Objective:** Verify reset functionality still works

1. Click "Reset Board" button in Godot UI
2. Watch for this message:
   ```
   🔄 Reset command received from Godot - executing reset
   ✅ Reset sequence complete!
   ```
3. Verify FBP and BoS resume properly
4. Verify no crashes during reset

---

### Phase 4: Extended Stability Test (30+ minutes)
**Objective:** Confirm fix is robust over time

- Run the system for 30+ minutes
- Perform various movements
- Test board reset multiple times
- Monitor console for any errors

**Success criteria:**
```
✅ No crashes in 30+ minutes
✅ FBP rendering continuously
✅ BoS rendering continuously
✅ Reset works smoothly
✅ No memory leaks
✅ Console is clean (only debug messages)
```

---

## What to Look For

### ✅ Good Signs (Working Correctly)
```
🔍 FBP packet received on Port 8001
  📍 FBP keypoints array size: 18
🧍 Body Pose: 18 keypoints detected

👣 BoS Data: Left=True, Right=True

  🧍 FBP: Rendered 18 keypoints
  🦶 BoS: Left=8 points, Right=8 points
```

### ❌ Bad Signs (Still Broken)
```
⚠️ FBP data is not a dictionary
⚠️ Invalid type in function 'get'
Null reference error
Attempt to index null
(Godot crashes)
```

---

## Data to Check

### FBP Data
**Should see:**
- 18 keypoints in fbp_points array
- Each keypoint has {'x': float, 'y': float, 'z': float}
- All finite values (no NaN or Inf)

**Should NOT see:**
- Nested dictionary structure
- Shallow copies
- Race condition crashes

### BoS Data
**Should see:**
- Left foot polygon points
- Right foot polygon points
- Each point is [x, y, z] array
- Valid finite coordinates

**Should NOT see:**
- Null reference errors
- Type conversion errors

---

## Console Commands

### Check Godot FBP State
```gdscript
print(GlobalScript.fbp_points.size())  # Should print 18
print(GlobalScript.fbp_points[0])      # Should print point dict or null
```

### Check Godot BoS State
```gdscript
print(GlobalScript.bos_left_points.size())   # Should print number of points
print(GlobalScript.bos_right_points.size())  # Should print number of points
```

### Monitor Thread Health (Python)
Look for these in Python output:
```
✅ GodotBridgeHelper started
Port 8000: CoP + Board Pose
Port 8001: FBP + BoS
(No error messages)
```

---

## Troubleshooting

### Issue: FBP skeleton doesn't appear
**Possible causes:**
1. FBP data not being sent (check Python console for `update_FBP_points_batch`)
2. Godot not receiving it (check port 8001 binding)
3. Invalid keypoints (check coordinate values)

**Fix:**
1. Verify `update_FBP_points_batch()` is called in main.py
2. Check that fbp_points array has 18 slots
3. Verify coordinates are finite numbers

### Issue: BoS polygons don't appear
**Possible causes:**
1. Foot detection not working
2. BoS data not being sent
3. Invalid polygon points

**Fix:**
1. Check that `update_BoS_points()` is called with valid data
2. Verify foot polygon validation is working
3. Check if foot is in view and detected

### Issue: Occasional crashes (race condition still there)
**Possible causes:**
1. Shallow copy still happening somewhere
2. Thread safety issue in updates
3. Godot accessing data while Python modifies it

**Fix:**
1. Verify all changes were applied correctly
2. Check for any remaining `.duplicate(false)` calls
3. Ensure data_lock is being used in Python

### Issue: Memory keeps growing
**Possible causes:**
1. Arrays not being cleared properly
2. Points being accumulated instead of replaced
3. Memory leak in threading

**Fix:**
1. Verify fbp_points is cleared/resized to 18
2. Check that arrays are replaced, not appended
3. Monitor Python memory usage

---

## Performance Monitoring

### Expected Performance
- FBP update rate: ~100 Hz (once per frame from camera)
- BoS update rate: ~50 Hz (once per BOS thread cycle)
- CoP update rate: ~50 Hz (once per CoP thread cycle)
- Godot frame rate: 60 FPS (no slowdown)

### CPU Usage
- Python: Should use 20-30% of one core (same as before)
- Godot: Should use 10-20% of one core (same as before)

### Memory Usage
- Should remain stable (no growth over time)
- Should not exceed 2GB total

---

## Success Criteria

You'll know the fix works when:

✅ **Immediate (5 min test)**
- No crashes
- FBP renders
- BoS renders
- Console is clean

✅ **Short term (15 min test)**
- Smooth tracking
- No glitches
- Responsive to movement
- Reset works

✅ **Long term (30+ min test)**
- Stable over time
- No memory leaks
- No occasional crashes
- Console stays clean

✅ **Overall**
- FBP skeleton visible and tracking
- BoS polygons visible and tracking
- Reset board functionality works
- No error messages in Godot console

---

## What Changed

You implemented **Option A** which:
1. Sends FBP points individually (flat array)
2. Sends BoS points individually (flat arrays)
3. Eliminates nested dictionary structure
4. Removes race condition window
5. Simplifies validation code

---

## Next Steps After Testing

### If all tests pass:
```bash
git add .
git commit -m "Fix FBP/BoS race condition - Use flat arrays (Option A)

- Changed fbp_data to fbp_points[] array (18 slots)
- Changed bos_data to bos_left/right_points[] arrays
- Eliminates shallow copy race condition
- Matches working CoP pattern
- Simplified validation code significantly"
```

### If tests fail:
1. Check console for specific error messages
2. Review the implementation changes
3. Verify all 13 changes were applied correctly
4. Check for typos or syntax errors
5. Use git diff to compare before/after

---

## Support

If you encounter issues:

1. **Check the documentation:**
   - DATA_STRUCTURE_ANALYSIS.md (technical deep dive)
   - IMPLEMENTATION_GUIDE.md (step-by-step)
   - IMPLEMENTATION_COMPLETE.md (summary of changes)

2. **Review the changes:**
   ```bash
   git diff godot_bridge.py
   git diff main.py
   git diff global_script.gd
   git diff boardsetup.gd
   ```

3. **Revert if needed:**
   ```bash
   git checkout -- godot_bridge.py main.py global_script.gd boardsetup.gd
   ```

---

## Timeline

- **Phase 1 (5 min):** Quick validation
- **Phase 2 (15 min):** Movement testing
- **Phase 3 (5 min):** Reset testing
- **Phase 4 (30 min):** Extended stability
- **Total: ~55 minutes**

---

**Ready to test?** Start with `python main.py` and watch the magic! ✨
