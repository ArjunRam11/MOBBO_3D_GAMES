# Quick Test Guide - Reset Board + UI

**Updated**: December 16, 2025

---

## 30-Second Quick Test

1. **Start Python**:
   ```bash
   python main.py
   ```
   Watch for: `📡 Command receiver listening on UDP port 9000`

2. **Start Godot** (press F5 in Godot Editor)
   Watch for: Boards render in 3D view

3. **In Godot**:
   - Look for "MOBBO Controls" panel on RIGHT side
   - Click "Reset Board" button
   - Look for cyan text and blue border

4. **Check Console** (Python side):
   - Should see: `📨 Reset board command received`
   - Should see: `✅ Board reset complete!`
   - Should NOT see: `list index out of range`

5. **Click Reset Board Again**:
   - Button should respond immediately
   - No "stuck" appearance

✅ **If all above pass → System is working!**

---

## Full Test Sequence (5 minutes)

### Setup (30 seconds)

```bash
# Terminal 1: Start Python
cd e:\Godot_interface\MOBBO_3D_GAMES\MOBBO_3D_GAMES
python main.py
```

Wait for: `✅ All processing threads started`

```
# Terminal 2 or IDE: Start Godot
# Press F5 in Godot Editor
```

Wait for: Boards appear in 3D visualization

### Test 1: First Reset (1 minute)

**In Godot UI**:
1. Observe the MOBBO Controls panel
   - ✅ Panel on RIGHT side
   - ✅ Title is large and cyan
   - ✅ "Visualization" section visible
   - ✅ "Reset Board" button visible

2. Click "Reset Board"

**Observe Python Console**:
```
📨 Reset board command received from Godot!
🔴 Stopping all threads...
✅ BOS thread stop initiated
🔄 Resetting board pose sent flag...
✅ Board pose flags reset
🔍 Re-detecting board positions...
🎥 Attempting board detection with frame: <class 'Frame_Process'>
📊 Board detection returned 2 board(s)
✅ New board positions detected
📡 Ensuring board pose will be sent to Godot...
✅ Board pose send flag confirmed
▶️ Restarting compute_COP thread...
✅ compute_COP thread restarted successfully
✅ Board reset complete!
```

**Expected Result**:
- ✅ Boards fade out, then reappear at new positions
- ✅ CoP point (cyan dots) continues updating
- ✅ No error messages
- ✅ UI remains responsive

### Test 2: Button State (1 minute)

1. Immediately click "Reset Board" again
2. Button should NOT appear "stuck" or highlighted
3. Click 2-3 more times rapidly
4. Verify each click registers

**Expected**:
- ✅ Button responds to every click
- ✅ No "selected" state persists
- ✅ Python receives each command

**Check Python Console**:
```
📨 Reset board command received from Godot!
[...full reset sequence...]
✅ Board reset complete!

📨 Reset board command received from Godot!
[...full reset sequence...]
✅ Board reset complete!
```

### Test 3: UI Elements (1 minute)

1. Observe text colors:
   - ✅ Title "MOBBO Controls" is bright cyan
   - ✅ "Visualization" label is cyan
   - ✅ "CoP Recording" label is cyan

2. Look for recording buttons:
   - ✅ Should see 1-2 buttons per board IP
   - ✅ Buttons should be tan/brown (OFF state)

3. Click a recording button:
   - ✅ Button turns RED (ON state)
   - ✅ Console shows recording started
   - Click again:
   - ✅ Button turns tan (OFF state)
   - ✅ Console shows recording stopped

### Test 4: Board Movement (1 minute)

1. Move ArUco boards to new location in front of camera
2. Click "Reset Board"
3. Observe:
   - ✅ Boards detected at new positions
   - ✅ Board meshes move in Godot visualization
   - ✅ Reference board designation might change (if different board is closest)

**Check Python Console**:
```
📊 Board detection returned 2 board(s)
```

Should show each time boards are re-detected.

---

## Troubleshooting

### Problem: Panel not visible on right side

**Solution**:
- Restart Godot (F5)
- Check if panel is cut off by screen edge
- Verify Godot window is not too narrow

**Debug**: In Godot console should show:
```
✅ UI controls created on right side (CanvasLayer)
```

### Problem: Button stuck in pressed state

**Solution**:
- Check Python console - board detection might be failing
- Try clicking elsewhere first, then click Reset Board again
- Restart Python and Godot if persists

**Debug**: Python should show:
```
🔘 Reset button deselected - ready for next press
```

### Problem: Reset command not reaching Python

**Solution**:
- Check Python console for: `📡 Command receiver listening on UDP port 9000`
- If missing, restart Python
- Verify Godot is on same machine or proper network

**Debug**: Godot console should show:
```
📤 Sending reset command to Python: stop_all_threads()
✅ Reset command sent to Python via UDP port 9000
```

### Problem: No boards detected after reset

**Solution 1** - Boards not in camera view:
- Ensure ArUco boards are in front of camera
- Check lighting (boards need to be well-lit)
- Verify markers are not damaged

**Solution 2** - Detection timeout:
- Check Python console for timing
- Try moving boards closer to camera
- Try adjusting camera focus

**Debug**: Python console should show:
```
📊 Board detection returned 2 board(s)
```

If it shows 0, boards aren't detected by camera.

### Problem: System freezes after reset

**Solution**:
- Check Python console for any `CRITICAL` errors
- Verify both threads restarted:
  - `✅ compute_COP thread restarted successfully`
- If frozen, press Ctrl+C in Python terminal to gracefully exit

**Debug**: Never should see:
```
❌ CRITICAL: Failed to restart thread
```

If you do, there's a system issue - restart and check Python logs.

---

## Expected Console Output Patterns

### Successful Reset

```
📨 Reset board command received from Godot!
🔴 Stopping all threads...
✅ BOS thread stop initiated
[...diagnostic output...]
✅ Board reset complete!
```

### Board Detection Success

```
🎥 Attempting board detection with frame: <class 'Frame_Process'>
📊 Board detection returned 2 board(s)
```

### Board Detection Failure (but recovers)

```
🎥 Attempting board detection with frame: <class 'Frame_Process'>
📊 Board detection returned 0 board(s)
❌ ERROR: No boards detected during board_pose_detected_set()!
   Camera may not be capturing boards, or ArUco detection failed
✅ New board positions detected (or warning if detection failed)
✅ compute_COP thread restarted successfully
✅ Board reset complete!
```

**This is OK** - System continues with last known positions.

---

## Success Criteria

### UI ✅
- [ ] MOBBO Controls panel on right side
- [ ] Panel is fully visible (not cut off)
- [ ] Text is bright and readable
- [ ] No errors in Godot console

### Button Functionality ✅
- [ ] Reset Board button visible and clickable
- [ ] Button doesn't stay in "pressed" state
- [ ] Can click multiple times
- [ ] Each click triggers reset

### Python Integration ✅
- [ ] Reset command received each time
- [ ] Board detection runs
- [ ] Thread restarts successfully
- [ ] No crashes or freezes

### Data Flow ✅
- [ ] Board positions update after reset
- [ ] CoP data continues flowing
- [ ] Recording buttons work
- [ ] Visualizations update in Godot

---

## Performance Expectations

| Operation | Time | Notes |
|-----------|------|-------|
| Reset command sent | < 10ms | UDP to Python |
| Thread stop | ~1s | Graceful shutdown |
| Board detection | 0.5-2s | Depends on lighting |
| Thread restart | 100ms | New thread creation |
| Total reset cycle | 2-4s | From click to ready |
| Next reset available | Immediate | After thread restarts |

If reset takes > 5 seconds, check:
- Board detection issues
- Camera performance
- System load

---

## When to Restart

**Restart Python if**:
- `list index out of range` error appears
- Threads not restarting
- Reset command not received
- System completely frozen

**Restart Godot if**:
- UI not appearing
- Panel in wrong position
- Buttons not responding
- Data not updating

**Restart Both if**:
- No communication between systems
- Multiple consecutive errors
- Visualizations not updating

---

## Next Steps After Testing

1. **If all tests pass** ✅
   - System is ready for production
   - You can proceed with data collection
   - Boards can be reset between trials

2. **If some tests fail** ⚠️
   - Check troubleshooting section
   - Review Python/Godot console logs
   - Verify camera and board setup

3. **For optimization**:
   - Monitor reset timing
   - Check thread performance
   - Optimize board detection if needed

---

## Support

**Issue**: [Describe problem]
**Check**: [Expected vs actual output]
**Solution**: [Restart/debug steps]
**Escalate**: If issue persists after restart

---

**Last Updated**: December 16, 2025
**Version**: 1.0 - Complete Implementation
**Status**: READY FOR TESTING ✅
