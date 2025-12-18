# Python Reset Board Integration Guide

## Quick Integration (5 Minutes)

Add this code to your main processing loop in **main.py** (around the game loop):

### Option 1: Simple Integration (Recommended)

Add to your main BOSEstimator class or wherever you have the main loop:

```python
# In your main processing loop (e.g., in main() or a run() method)
while True:
    try:
        # Check if Godot requested reset
        if hasattr(self, 'godot_bridge') and hasattr(self.godot_bridge, 'network_manager'):
            if getattr(self.godot_bridge.network_manager, 'reset_board_requested', False):
                print("\n📨 Reset board command received from Godot!")
                print("🔴 Stopping all threads...")

                # Execute reset sequence
                self.stop_all_threads()

                print("⏳ Waiting 1 second for graceful shutdown...")
                time.sleep(1)

                print("🟢 Restarting board detection...")
                self.reset_all_threads()

                # Clear the flag
                self.godot_bridge.network_manager.reset_board_requested = False

                print("✅ Board reset complete!\n")

        # Your normal processing continues...
        # ... rest of your loop code ...

    except Exception as e:
        print(f"Error in reset handler: {e}")
        logger.exception("Reset handler error")
```

### Option 2: Event-based Integration

If you have an event system, create a dedicated reset handler:

```python
def handle_reset_board_command(self):
    """Handle reset board command from Godot UI"""
    print("\n📨 === RESET BOARD SEQUENCE STARTED ===")

    try:
        # Phase 1: Stop all processing
        print("Phase 1️⃣: Stopping all threads...")
        self.stop_all_threads()

        # Phase 2: Wait for graceful shutdown
        print("Phase 2️⃣: Waiting for shutdown (1 second)...")
        time.sleep(1)

        # Phase 3: Restart board detection
        print("Phase 3️⃣: Restarting board detection...")
        self.reset_all_threads()

        print("✅ === RESET BOARD SEQUENCE COMPLETE ===\n")

    except Exception as e:
        print(f"❌ Error during reset: {e}")
        logger.exception("Reset sequence failed")

    finally:
        # Always clear the flag
        if hasattr(self.godot_bridge.network_manager, 'reset_board_requested'):
            self.godot_bridge.network_manager.reset_board_requested = False


# Call from main loop
def main():
    bos_estimator = BOSEstimator()
    # ... initialization ...

    while True:
        # Check for reset command
        if getattr(bos_estimator.godot_bridge.network_manager, 'reset_board_requested', False):
            bos_estimator.handle_reset_board_command()

        # Normal processing
        # ... rest of loop ...
```

---

## Expected Flow

```
GODOT SIDE (T=0ms)
    User clicks "Reset Board"
    ↓
    ├─ Hide visualizations
    ├─ Reset UI buttons
    └─ Send reset_board_requested = True
              ↓
NETWORK (T=50-100ms)
    Command stored in network_manager
              ↓
PYTHON SIDE (T=100-200ms)
    ├─ Detect reset_board_requested = True
    ├─ Call stop_all_threads() [takes ~1000ms]
    │   ├─ Stop ArUco detection
    │   ├─ Stop BOS computation
    │   ├─ Stop foot detection
    │   └─ Close Godot bridge
    ├─ Sleep 1 second
    ├─ Call reset_all_threads()
    │   ├─ Show loading dialog
    │   ├─ Detect ArUco boards again
    │   ├─ Recalculate coordinate frame
    │   └─ Restart all threads
    ├─ Set reset_board_requested = False
    └─ Resume normal operation
              ↓
GODOT SIDE (T=2000-5000ms)
    Receives new board_pose_data
    ├─ Updates visualizations
    ├─ Draws boards
    └─ CoP data starts flowing again
```

---

## Command Details

### What Godot Sends

**Flag**: `network_manager.reset_board_requested`
```python
# When reset requested
network_manager.reset_board_requested = True

# After Python handles it
network_manager.reset_board_requested = False
```

**Command**: `network_manager.control_command["reset_board"]`
```python
{
    "type": "reset_board",
    "action": "stop_all_threads",
    "timestamp": 1702383456789  # When command was created
}
```

### What Python Should Do

**Step 1: stop_all_threads()** (~1000ms)

The `BOSEstimator.stop_all_threads()` function already exists in your code. It:
- Sets global flags to stop detection
- Closes Godot bridge
- Stops foot detection thread
- Joins BOS thread

**Step 2: Wait** (1000ms)

`time.sleep(1)` - Allow threads to finish gracefully

**Step 3: reset_all_threads()** (2000-5000ms)

The `BOSEstimator.reset_all_threads()` function already exists. It:
- Creates ResetButtonProcess instance
- Shows loading dialog
- Detects ArUco boards again
- Restarts all processing threads

**Step 4: Clear Flag**

Set `reset_board_requested = False` to indicate completion

---

## Integration Checklist

- [ ] Add reset handler to main loop
- [ ] Check `reset_board_requested` flag periodically
- [ ] Call `self.stop_all_threads()` when True
- [ ] Sleep 1 second
- [ ] Call `self.reset_all_threads()`
- [ ] Set `reset_board_requested = False`
- [ ] Test with Godot reset button
- [ ] Verify board redetects
- [ ] Verify visualizations resume

---

## Debugging

### If reset doesn't work

**Check 1: Flag is being set**
```python
print(getattr(self.godot_bridge.network_manager, 'reset_board_requested', 'NOT SET'))
```

**Check 2: Handler is being called**
```python
if getattr(self.godot_bridge.network_manager, 'reset_board_requested', False):
    print("✅ Reset command detected!")
else:
    print("❌ Reset flag not set")
```

**Check 3: Threads are stopping**
```python
# In stop_all_threads(), add logging
print("Global flags before:", stop_flag_aruco, stop_threads)
self.stop_all_threads()
print("Global flags after:", stop_flag_aruco, stop_threads)
```

**Check 4: Threads are restarting**
```python
# In reset_all_threads(), add logging
print("Starting reset_all_threads()...")
self.reset_all_threads()
print("Finished reset_all_threads()")
```

---

## Console Output (Expected)

When reset is working correctly, you should see:

```
🔄 GODOT: [Button Click]
📤 GODOT: Sending reset command to Python
📨 PYTHON: Reset board command received from Godot!
🔴 PYTHON: Stopping all threads...
(ArUco detection stops)
(BOS computation stops)
(Foot detection stops)
(Godot bridge closes)
⏳ PYTHON: Waiting 1 second for graceful shutdown...
🟢 PYTHON: Restarting board detection...
(Loading dialog: "Reset Board Position, please wait...")
(Detecting ArUco boards...)
(Recalculating coordinate frame...)
(Restarting detection threads...)
✅ PYTHON: Board reset complete!
(Godot receives new board_pose_data)
📊 GODOT: Visualizations resume
```

---

## File Locations

| File | Function | Purpose |
|------|----------|---------|
| main.py | stop_all_threads() | Stop all processing |
| main.py | reset_all_threads() | Restart board detection |
| Graph_window_main.py | restart_process() | Reference implementation |
| loading_process_widget.py | ResetButtonProcess | Board redetection dialog |

---

## Existing Python Code Reference

Your Python code already has the reset functionality built in:

**From Graph_window_main.py (lines 527-533):**
```python
def restart_process(self):
    """Handle the button click to stop and restart threads."""
    print("Restart button clicked!")
    self.bos_estimator.stop_all_threads()
    time.sleep(1)
    self.bos_estimator.reset_all_threads()
    print("Threads restarted!")
```

Just apply this same pattern to your Godot integration!

---

## Testing Procedure

1. **Start Godot and Python**
   - Both systems running normally

2. **Click Reset Board in Godot**
   - Should see Godot UI reset
   - Should see reset command in console

3. **Check Python Console**
   - Should see "Reset board command received"
   - Should see threads stopping
   - Should see board detection restarting

4. **Check Godot Visualization**
   - Visualizations should reappear
   - CoP should start moving
   - BoS and FBP should render

5. **Verify State**
   - All recording buttons OFF
   - Board coordinate system re-initialized
   - All threads running normally

---

## Troubleshooting

**Problem**: Reset flag never received
- Solution: Check network_manager is accessible
- Check: `print(dir(self.godot_bridge.network_manager))`

**Problem**: Threads don't stop
- Solution: Check stop_all_threads() implementation
- Check: Global flags are actually being set

**Problem**: Board doesn't redetect
- Solution: Check reset_all_threads() is called
- Check: Loading dialog appears
- Check: ArUco cameras are working

**Problem**: Godot doesn't receive new board data
- Solution: Check Godot bridge reconnects
- Check: UDP ports are open
- Check: New board_pose_data is being generated

---

## Summary

✅ **Ready to implement**
- Add 10-15 lines of code to main loop
- Reuse existing stop/reset functions
- Same pattern as Python visualization

**Estimated implementation time**: 5-15 minutes
**Testing time**: 5-10 minutes
**Total**: ~20 minutes

**Next step**: Add reset handler to your main processing loop!

---

**Date**: December 12, 2025
**Godot Status**: ✅ COMPLETE
**Python Status**: ⏳ READY FOR INTEGRATION
