# Reset Board System - Testing Guide

## ✅ System Status: READY FOR TESTING

Both Godot and Python sides are now complete and integrated.

---

## Quick Test (5 Minutes)

### Prerequisites
- Godot running with BoardSetup scene
- Python running with main.py
- Force plates connected
- Camera connected

### Test Steps

#### 1. Start Both Systems
```bash
# Terminal 1: Python
python main.py

# Terminal 2: Godot (or run through editor)
# Open Godot, run BoardSetup scene
```

#### 2. Verify Initial State
- [ ] Godot shows UI panel on left sidebar
- [ ] "MOBBO Controls" title visible
- [ ] "Reset Board" button visible
- [ ] Recording buttons appear (one per detected board)
- [ ] CoP data flowing (red sphere moving)

#### 3. Run Reset Test

**In Godot:**
1. Click "Reset Board" button
2. Observe:
   - ✅ CoP/BoS/FBP visualizations disappear immediately
   - ✅ Recording buttons reset to [OFF]
   - ✅ Console shows reset messages

**In Python Console:**
1. Watch for reset messages:
   ```
   📨 Reset board command received from Godot!
   🔴 Stopping all threads...
   ⏳ Waiting 1 second for graceful shutdown...
   🟢 Restarting board detection...
   ✅ Board reset complete!
   ```
2. Loading dialog appears: "Reset Board Position, please wait..."
3. After 2-5 seconds, board redetects

**Back in Godot:**
1. Visualizations reappear (CoP/BoS/FBP)
2. CoP follows foot movement
3. System back to normal

#### 4. Verify State
- [ ] All visualizations rendering
- [ ] CoP moves with foot
- [ ] BoS shows foot support polygon
- [ ] FBP shows foot keypoints
- [ ] No console errors

---

## Detailed Test Checklist

### Phase 1: Initial Setup ✅

```
GODOT SIDE:
  ✅ Scene loads without errors
  ✅ UI panel appears on left side
  ✅ "MOBBO Controls" title visible
  ✅ Reset Board button visible
  ✅ Recording buttons for each IP address
  ✅ CoP visualization visible (red sphere)
  ✅ BoS visualization visible (foot polygons)
  ✅ FBP visualization visible (foot keypoints)

PYTHON SIDE:
  ✅ main.py runs without errors
  ✅ ArUco detection running
  ✅ BOS computation running
  ✅ CoP data flowing
  ✅ Godot bridge connected
  ✅ All threads running
```

### Phase 2: Reset Button Click ✅

```
T=0ms:  Click "Reset Board" in Godot

GODOT SIDE (immediate):
  ✅ Print: "🔄 Resetting board visualization..."
  ✅ Print: "📤 Sending reset command to Python: stop_all_threads()"
  ✅ Print: "⏳ Waiting for Python to: stop threads (1s) → reinitialize board detection"
  ✅ Print: "✅ Board reset initiated (waiting for Python side...)"
  ✅ CoP visualization disappears
  ✅ BoS visualization disappears
  ✅ FBP visualization disappears
  ✅ All recording buttons reset to [OFF]
  ✅ Button colors reset to default

PYTHON SIDE (detected within 100ms):
  ✅ Print: "📨 Reset board command received from Godot!"
  ✅ Print: "🔴 Stopping all threads..."
```

### Phase 3: Thread Cleanup ✅

```
T=100-1000ms: Threads stopping

PYTHON SIDE:
  ✅ ArUco detection stops
  ✅ BOS computation stops
  ✅ Foot detection stops
  ✅ Godot bridge stops
  ✅ Print: "⏳ Waiting 1 second for graceful shutdown..."

GODOT SIDE:
  ✅ No new CoP data received
  ✅ No new visualizations updated
  ✅ No errors in console
```

### Phase 4: Board Redetection ✅

```
T=1000-1100ms: Wait period

PYTHON SIDE:
  ✅ Sleep(1) in progress
  ✅ All threads halted
  ✅ No data processing

GODOT SIDE:
  ✅ Waiting for new data
  ✅ UI still responsive
```

### Phase 5: Restart Board Detection ✅

```
T=1100-4000ms: Board redetection

PYTHON SIDE:
  ✅ Print: "🟢 Restarting board detection..."
  ✅ Loading dialog appears: "Reset Board Position, please wait..."
  ✅ ResetButtonProcess spawned
  ✅ Worker thread started
  ✅ ArUco detection restarted
  ✅ Board detected
  ✅ Coordinate frame recalculated

GODOT SIDE:
  ✅ Still waiting (might show loading in Python UI)
  ✅ No errors in console
```

### Phase 6: Resumption ✅

```
T=4000-5000ms: Recovery

PYTHON SIDE:
  ✅ Print: "✅ Board reset complete!"
  ✅ Godot bridge reconnects
  ✅ BOS thread restarts
  ✅ All detection threads running
  ✅ Normal data flow resumes
  ✅ First board_pose_data packet sent

GODOT SIDE:
  ✅ Receives new board_pose_data
  ✅ Board position updated
  ✅ CoP data resumes flowing
  ✅ CoP visualization reappears
```

### Phase 7: Full Operation ✅

```
T=5000ms+: Normal operation

GODOT SIDE:
  ✅ CoP renders (red sphere moves with foot)
  ✅ BoS renders (blue/orange foot support polygon)
  ✅ FBP renders (cyan foot keypoints)
  ✅ UI panel fully responsive
  ✅ Recording buttons clickable
  ✅ Reset button clickable
  ✅ No errors in console

PYTHON SIDE:
  ✅ Normal console output (periodic debug messages)
  ✅ All threads running
  ✅ Godot bridge connected
  ✅ No errors logged
```

---

## Expected Console Output

### Godot Console (Expected)
```
🔄 Resetting board visualization...
📤 Sending reset command to Python: stop_all_threads()
⏳ Waiting for Python to: stop threads (1s) → reinitialize board detection
✅ Board reset initiated (waiting for Python side...)
```

### Python Console (Expected)
```
📨 Reset board command received from Godot!
🔴 Stopping all threads...
⏳ Waiting 1 second for graceful shutdown...
🟢 Restarting board detection...
✅ Board reset complete!
```

---

## Troubleshooting

### Problem: "Reset Board" button doesn't appear
**Solution**:
- Check Godot console for UI creation errors
- Verify network_manager is connected
- Restart Godot scene

### Problem: Python doesn't detect reset command
**Solution**:
- Check Python console for error messages
- Verify godot_bridge is initialized
- Check network_manager attribute exists
- Verify reset_board_requested attribute is being read

### Problem: Board doesn't redetect after reset
**Solution**:
- Check Python console for board detection errors
- Verify camera is connected
- Verify ArUco boards are visible
- Check loading dialog appears (it may hide console)

### Problem: Godot visualizations don't reappear
**Solution**:
- Check Godot is receiving new board_pose_data
- Verify Godot bridge reconnected
- Check for coordinate transformation errors
- Restart both systems if needed

### Problem: System freezes during reset
**Solution**:
- This is normal (1-2 seconds of processing)
- Wait for loading dialog to complete
- Check Python console for progress
- If still frozen after 10 seconds, restart systems

---

## Advanced Testing

### Test 1: Multiple Resets
```
1. Click Reset Board
2. Wait for recovery
3. Click Reset Board again
4. Verify works correctly
5. Repeat 3-4 times
```

### Test 2: Reset with Recording Active
```
1. Turn ON CoP recording for an IP
2. Observe button shows [ON] in red
3. Click Reset Board
4. Verify button resets to [OFF]
5. Verify recording stopped
```

### Test 3: Rapid Reset Clicks
```
1. Click Reset Board twice quickly
2. Verify system handles gracefully
3. Check console for error messages
4. Verify recovery still works
```

### Test 4: Reset During Heavy Load
```
1. Move person around (high CoP activity)
2. Click Reset Board
3. Verify reset completes even with busy data flow
4. Check no data loss after recovery
```

---

## Success Criteria

### ✅ System is working correctly if:

1. **Godot UI**
   - Reset button appears without errors
   - Recording buttons create dynamically
   - All visualizations hide on reset
   - All visualizations reappear after reset
   - No console errors

2. **Python Reset Sequence**
   - Reset command detected within 100ms of click
   - Threads stop cleanly within 1 second
   - Board redetects within 2-5 seconds
   - Godot bridge reconnects
   - Normal operation resumes

3. **Data Continuity**
   - No crash or hang
   - CoP data flows continuously after reset
   - Board poses update correctly
   - No coordinate frame errors

4. **User Experience**
   - Clear console feedback
   - Loading dialog shows progress
   - System responds to commands
   - No data artifacts or glitches

---

## Performance Notes

### Expected Timings
- Reset detection: < 100ms
- Thread shutdown: ~1000ms
- Sleep period: 1000ms
- Board redetection: 2-5 seconds (varies by scene)
- Visualization recovery: ~100ms after data arrives
- **Total reset time: 3-7 seconds**

### Performance is OK if:
- Reset completes within 10 seconds
- No repeated error messages
- System responsive during reset
- Loading dialog shows progress

---

## When to Report Issues

Report an issue if:
- Reset doesn't complete within 10 seconds
- System crashes or freezes permanently
- Console shows error messages
- Visualizations don't reappear
- Board doesn't redetect
- Godot bridge doesn't reconnect

Include:
- Console output (both Python and Godot)
- Time from reset click to recovery
- Error messages (exact text)
- System state at failure

---

## Testing Conclusion

Once you can:
1. ✅ Click "Reset Board" button
2. ✅ See Godot visualizations disappear
3. ✅ See Python reset messages
4. ✅ See visualizations reappear
5. ✅ See system return to normal operation

**The implementation is successful!** 🎉

---

**Ready to test?** Start with the Quick Test above!
