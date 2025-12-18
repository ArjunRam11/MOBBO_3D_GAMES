# Reset Board Testing - Quick Start Guide

**Status**: ✅ Ready for Testing

---

## 5-Minute Quick Test

### Step 1: Start Python (1 minute)

```bash
cd e:\Godot_interface\MOBBO_3D_GAMES\MOBBO_3D_GAMES
python main.py
```

**Wait for this message in Python console:**
```
📡 Command receiver listening on UDP port 9000
✅ SUCCESS: Command receiver listening on UDP port 9000
```

If you don't see this, something is blocking port 9000. Check for other Python instances.

---

### Step 2: Start Godot (1 minute)

1. Open Godot editor
2. Load BoardSetup scene
3. Press Play or F5

**Wait 3-5 seconds for systems to connect.**

You should see:
- CoP visualization (usually center of feet area)
- Board positions visible
- Status messages in both consoles

---

### Step 3: Physically Move Boards (1 minute)

1. Stop Godot (press ESC or stop button)
2. **Physically move one or more ArUco boards** to a different location
3. Press Play to restart Godot

**The old board positions should still display** (this is expected).

---

### Step 4: Click Reset Button (1 minute)

1. Look at Godot scene (bottom-left area)
2. Find the **"Reset Board"** button
3. **Click it**

**Watch both consoles:**

#### Python Console (Expected):
```
📨 Reset board command received from Godot!
🔴 Stopping all threads...
✅ BOS thread stop initiated (called from within thread)
⏳ Waiting 1 second for graceful shutdown...
🔍 Re-detecting board positions...
✅ New board positions detected
📡 Signaling board pose change to Godot...
✅ Board pose change flag set
▶️ Restarting compute_COP thread...
✅ compute_COP thread restarted
✅ Board reset complete!
```

#### Godot Visualization (Expected):
- ✅ Visualizations disappear (brief moment)
- ✅ Wait 1-2 seconds
- ✅ Visualizations reappear at **NEW positions**
- ✅ CoP indicator moves to reflect new board positions

---

### Step 5: Verify Success

If you see all of the above:

✅ **RESET BOARD IS WORKING PERFECTLY!**

---

## Troubleshooting

### Problem 1: Don't see "Command receiver listening on UDP port 9000"

**Solutions:**
1. Close all other Python instances: `taskkill /F /IM python.exe`
2. Check if port 9000 is in use: `netstat -ano | findstr 9000`
3. Restart Python: `python main.py`

---

### Problem 2: Click Reset but nothing happens

**Check:**
1. Is Python console showing any error messages?
2. Is Godot console showing the command sent?
3. Try clicking Reset again (may need to wait after previous reset)

**Solution:**
1. Close Godot
2. Restart Python: `Ctrl+C` then `python main.py`
3. Restart Godot
4. Try Reset again

---

### Problem 3: Visualizations don't reappear after reset

**This could mean:**
1. Board detection failed (check if boards are visible to camera)
2. No CoP data from force plates (check force plate connections)
3. Thread restart failed

**Check Python console for error messages.**

---

### Problem 4: System hangs/freezes after reset

**This should NOT happen with the new code.**

If it does:
1. Press `Ctrl+C` in Python console to stop
2. Restart: `python main.py`
3. Report the error messages

---

## Extended Test (5-10 minutes)

### Test Multiple Resets

1. Click Reset 3-5 times in a row
2. Verify each reset completes successfully
3. Verify no errors accumulate
4. Verify system remains responsive

**Expected result**: All resets work smoothly, no errors.

---

### Test with Moving Objects

1. Perform reset
2. Have a person stand on the force plates
3. Have them move around
4. Click Reset again
5. Verify CoP visualization follows movements correctly

**Expected result**: CoP data flows smoothly before and after reset.

---

### Test Rapid Resets

1. Click Reset
2. Immediately click Reset again (within 1 second)
3. Verify both resets complete (may queue)

**Expected result**: System queues second reset, completes both smoothly.

---

## Success Criteria Checklist

After testing, verify ALL of these:

- [ ] Python console shows "Command receiver listening on UDP port 9000" on startup
- [ ] Python receives reset command when you click button
- [ ] Python shows "Reset board command received from Godot!"
- [ ] Python shows "Board reset complete!" (not frozen mid-sequence)
- [ ] Godot visualizations disappear and reappear
- [ ] Board positions appear DIFFERENT after reset
- [ ] CoP/GCoP visualizations updated with new positions
- [ ] System responsive to multiple resets
- [ ] NO error messages in either console
- [ ] Reset completes within 1-3 seconds

**If ALL checkboxes are ✅**: **SYSTEM IS READY FOR PRODUCTION!**

---

## Expected Reset Duration

| Phase | Duration | What You See |
|-------|----------|--------------|
| Command Send | ~50ms | Reset button briefly disabled |
| Python Shutdown | ~1000ms | Python showing "Waiting..." |
| Board Detection | ~500-1000ms | Python detecting new positions |
| Thread Restart | ~50-100ms | Python restarting thread |
| Godot Update | ~500ms | Visualizations reappearing |
| **TOTAL** | **~2-3 seconds** | System back to normal |

---

## Console Output Reference

### ✅ GOOD Output

```
📨 Reset board command received from Godot!
🔴 Stopping all threads...
✅ BOS thread stop initiated (called from within thread)
⏳ Waiting 1 second for graceful shutdown...
🔍 Re-detecting board positions...
✅ New board positions detected
📡 Signaling board pose change to Godot...
✅ Board pose change flag set
▶️ Restarting compute_COP thread...
✅ compute_COP thread restarted
✅ Board reset complete!
```

### ❌ BAD Output Examples

```
❌ Error during reset sequence: [error message]
```
**Action**: Check error message, check board detection, restart Python.

```
⚠️ Error stopping BOS thread: cannot join current thread
```
**Action**: This should NOT happen with the new code. If it does, restart Python.

```
[No output when clicking Reset button]
```
**Action**: Socket not listening, restart Python, verify port 9000.

---

## Debug Information

If something goes wrong, save this information:

1. **Full Python console output** (copy-paste all text)
2. **Full Godot console output** (look in Output panel)
3. **Error messages** (if any)
4. **Exact steps to reproduce**
5. **What you expected vs. what happened**

Include this when reporting issues.

---

## Getting Help

If the reset doesn't work:

1. Check the main documentation: `RESET_BOARD_COMPLETE_IMPLEMENTATION.md`
2. Review the troubleshooting section above
3. Check that all prerequisites are met (Python running, Godot loaded, boards detected)
4. Try restarting both Python and Godot
5. Check for port conflicts: `netstat -ano | findstr 9000`

---

## Summary

The Reset Board feature should now:
- ✅ Detect reset commands from Godot
- ✅ Re-detect board positions
- ✅ Update visualizations with new positions
- ✅ Continue operating smoothly after reset
- ✅ Handle multiple resets without issues

**Ready to test!** 🚀
