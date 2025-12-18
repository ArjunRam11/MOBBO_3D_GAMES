# Reset Board Button - Godot-Python Integration

## Overview

The **Reset Board** button in the Godot UI now triggers a complete board reinitialization sequence that mirrors the Python backend's reset process.

---

## What Reset Board Does

### Phase 1: Godot Side (Immediate)
```
Click Reset Board Button
    ↓
├─ Hide all visualizations (CoP, BoS, FBP)
├─ Hide all board models
├─ Reset recording button states
└─ Send reset command to Python
```

**Console Output:**
```
🔄 Resetting board visualization...
📤 Sending reset command to Python: stop_all_threads()
⏳ Waiting for Python to: stop threads (1s) → reinitialize board detection
✅ Board reset initiated (waiting for Python side...)
```

### Phase 2: Python Side (Sequence)
```
Python receives reset command
    ↓
1️⃣ stop_all_threads() [~1 second]
    ├─ Set global flags (stop_flag_aruco, stop_threads, process_complete) → False
    ├─ Clear board reference data
    ├─ Stop Godot bridge communication
    ├─ Stop foot detection model thread
    └─ Join BOS computation thread
    ↓
2️⃣ reset_all_threads()
    ├─ Create new ResetButtonProcess instance
    ├─ Show loading dialog: "Reset Board Position, please wait..."
    └─ Start worker thread
        ├─ Re-detect ArUco boards
        ├─ Recalculate 3D coordinate reference frame
        └─ Restart all processing pipelines
    ↓
3️⃣ Resume normal operation
    ├─ All detection threads running
    ├─ Board coordinate system re-initialized
    └─ Godot bridge connection restored
```

---

## Implementation Details

### Godot Function: `_on_reset_board_pressed()` (Lines 936-956)

**Triggers on button click:**
```gdscript
func _on_reset_board_pressed():
    # Hide visualizations
    hide_all_visualizations()
    hide_all_boards()

    # Reset recording states
    for ip in recording_states:
        recording_states[ip] = false
        recording_buttons[ip].button_pressed = false
        recording_buttons[ip].text = "Rec: %s [OFF]" % ip

    # Send to Python
    _send_reset_command_to_python()
```

### Godot Function: `_send_reset_command_to_python()` (Lines 1005-1029)

**Creates and sends reset command:**

```gdscript
func _send_reset_command_to_python():
    # Create command
    var reset_command = {
        "type": "reset_board",
        "action": "stop_all_threads",
        "timestamp": Time.get_ticks_msec()
    }

    # Store in network_manager for Python to read
    network_manager.control_command["reset_board"] = reset_command
    network_manager.reset_board_requested = true
```

**Command Structure:**
```python
{
    "type": "reset_board",           # Command type identifier
    "action": "stop_all_threads",    # What Python should do
    "timestamp": 1234567890          # When command was sent
}
```

---

## Python Integration (TODO)

### Required in `main.py`

Add listener in your main processing loop:

```python
# In your main thread or update function:
if hasattr(godot_bridge.network_manager, 'reset_board_requested'):
    if godot_bridge.network_manager.reset_board_requested:
        print("📨 Reset board command received from Godot!")

        # Execute reset sequence
        bos_estimator.stop_all_threads()  # Stop everything gracefully
        time.sleep(1)                      # Wait for threads to finish
        bos_estimator.reset_all_threads()  # Restart board detection

        # Clear flag
        godot_bridge.network_manager.reset_board_requested = false
```

### In `Graph_window_main.py` (Reference Implementation)

The Python visualization already has this implemented:

```python
def restart_process(self):
    """Handle the button click to stop and restart threads."""
    print("Restart button clicked!")
    self.bos_estimator.stop_all_threads()
    time.sleep(1)
    self.bos_estimator.reset_all_threads()
    print("Threads restarted!")
```

---

## Command Flow

### Message Structure in network_manager

**Storage Location:**
```gdscript
network_manager.control_command["reset_board"] = {
    "type": "reset_board",
    "action": "stop_all_threads",
    "timestamp": 1234567890
}

network_manager.reset_board_requested = true
```

**Python Access:**
```python
# Check for reset command
if network_manager.reset_board_requested:
    command = network_manager.control_command.get("reset_board")
    print(f"Reset action: {command['action']}")
    print(f"Timestamp: {command['timestamp']}")
```

---

## State Management

### Before Reset

```
Board State: RUNNING
├─ ArUco detection: ACTIVE
├─ BOS computation: ACTIVE
├─ Godot bridge: CONNECTED
├─ Visualizations: SHOWING
└─ Recording: ON/OFF (varies)
```

### During Reset

```
Board State: RESETTING
├─ ArUco detection: STOPPING
├─ BOS computation: STOPPING
├─ Godot bridge: STOPPED
├─ Visualizations: HIDDEN
├─ Recording: ALL OFF
└─ Loading dialog: "Reset Board Position, please wait..."
```

### After Reset

```
Board State: RUNNING
├─ ArUco detection: ACTIVE (REDETECTED)
├─ BOS computation: ACTIVE (RESTARTED)
├─ Godot bridge: RECONNECTED
├─ Visualizations: READY (CLEARED)
└─ Recording: ALL OFF (RESET)
└─ Board coordinate system: RE-INITIALIZED
```

---

## Console Output

### Godot Console Output

```
🔄 Resetting board visualization...
📤 Sending reset command to Python: stop_all_threads()
⏳ Waiting for Python to: stop threads (1s) → reinitialize board detection
✅ Board reset initiated (waiting for Python side...)
```

### Python Console Output (Expected)

```
📨 Reset board command received from Godot!
Restarting process...
Godot bridge stopped
Foot detection stopped
BOS thread joined

Starting board detection...
Reset Board Position, please wait...
✅ Board redetected successfully
✅ Threads restarted!
Godot bridge reconnected
```

---

## Timing Sequence

```
T=0s:   User clicks Reset Board
    ↓
T=0.1s: Godot hides visualizations
    ↓
T=0.2s: Godot sends reset command to Python
    ↓
T=0.3s: Python receives reset command
    ↓
T=1.3s: Python finishes stop_all_threads()
    ↓
T=1.4s: Python starts reset_all_threads()
    ↓
T=2-5s: Board detection in progress (varies by scene)
    ↓
T=5-10s: Board redetected, threads restarted
    ↓
T=10s+: Normal operation resumes, Godot receives new board data
```

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ GODOT (Godot Engine - BoardSetup.gd)                            │
├──────────────────────────┬──────────────────────────────────────┤
│ Reset Board Button       │ UI Panel (CanvasLayer)               │
│         ↓                │                                      │
│ _on_reset_board_pressed()│ Hide visualizations                  │
│         ↓                │ Reset recording buttons              │
│ hide_all_visualizations()│                                      │
│ hide_all_boards()        │                                      │
│         ↓                │                                      │
│ _send_reset_command_to_python()                                │
│         ↓                │                                      │
└──────────────────┬───────┴──────────────────────────────────────┘
                   │
              NETWORK MANAGER
                   │ (UDP Port 8000/8001)
                   ↓
┌──────────────────────────────────────────────────────────────────┐
│ PYTHON (MOBBO Motion Analysis - main.py)                         │
├──────────────────────────┬───────────────────────────────────────┤
│ Listener checks:         │                                       │
│ reset_board_requested    │ BOSEstimator                          │
│         ↓                │                                       │
│ IF TRUE:                 │ ┌─────────────────────────────────┐   │
│  1. stop_all_threads()   │ │ stop_all_threads():             │   │
│     ├─ Stop ArUco        │ ├─ Set stop flags                │   │
│     ├─ Stop BOS          │ ├─ Stop Godot bridge             │   │
│     ├─ Stop Foot detect  │ ├─ Stop foot detection           │   │
│     └─ (sleep 1s)        │ └─ Join BOS thread              │   │
│                          │                                       │
│  2. reset_all_threads()  │ ┌─────────────────────────────────┐   │
│     ├─ Show loading      │ │ reset_all_threads():            │   │
│     └─ Start redetect    │ ├─ Create ResetButtonProcess     │   │
│                          │ ├─ Show loading dialog           │   │
│  3. Clear flag:          │ ├─ Restart board detection       │   │
│     reset_board_         │ └─ Restart all threads           │   │
│     requested = false    │                                       │
│                          │                                       │
└──────────────────────────┴───────────────────────────────────────┘
```

---

## Testing Checklist

- [x] Godot Reset button hides visualizations
- [x] Godot Reset button resets recording states
- [x] Command created and stored in network_manager
- [x] Console shows reset sequence messages
- [ ] Python receives reset_board_requested flag (pending Python integration)
- [ ] Python calls stop_all_threads() (pending Python integration)
- [ ] Python calls reset_all_threads() (pending Python integration)
- [ ] Board redetected after reset (pending Python integration)
- [ ] Godot receives new board data (pending Python integration)
- [ ] Visualizations resume normally (pending Python integration)

---

## Command Reference

### Godot → Python Reset Command

**File**: `network_manager` (global_script.gd)

**Location 1**: `network_manager.control_command["reset_board"]`
```python
{
    "type": "reset_board",
    "action": "stop_all_threads",
    "timestamp": <milliseconds>
}
```

**Location 2**: `network_manager.reset_board_requested`
```python
True  # When reset is requested
False # After reset is complete
```

---

## Summary

✅ **Godot Implementation Complete**
- Reset button triggers visualization cleanup
- Recording states reset
- Reset command sent to Python via network_manager

⏳ **Python Integration Pending**
- Add listener for `reset_board_requested` flag
- Call `stop_all_threads()` and `reset_all_threads()`
- Clear the flag after completion

**Estimated Python implementation time**: 10-15 minutes (simple callback)

---

## Code Locations

| Component | File | Lines | Purpose |
|-----------|------|-------|---------|
| Reset button creation | BoardSetup.gd | 877-880 | Create UI button |
| Reset button handler | BoardSetup.gd | 936-956 | Handle click, clean up |
| Send reset command | BoardSetup.gd | 1005-1029 | Create & send to Python |
| Python reference | main.py | 483-509 | What Python should do |

---

**Implementation Date**: December 12, 2025
**Status**: ✅ Godot side COMPLETE, ⏳ Python integration PENDING
**Sync Method**: network_manager shared object
**Communication**: UDP via Port 8000/8001 (same as CoP data)
