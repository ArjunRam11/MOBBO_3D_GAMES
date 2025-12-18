# MOBBO UI Control System - Implementation Guide

## Overview

A CanvasLayer-based UI control panel has been implemented in [BoardSetup.gd](NOARKGames/Games/BoardViz/BoardSetup.gd) that provides:

1. **Reset Board Button** - Reset all visualizations and board state
2. **Per-IP CoP Recording Buttons** - Toggle recording for each connected force plate
3. **Real-time UI Updates** - Dynamic button creation as boards are detected
4. **Godot-Python Communication** - Send recording commands to Python backend

---

## Architecture

### UI Layer (CanvasLayer - Option 2)

```
Node3D (BoardSetup.gd - 3D Scene Root)
├── Platform (3D board models)
├── FBP_Skeleton (3D body visualization)
└── CanvasLayer (UI Overlay - Layer 1)
    └── Panel (Dark background sidebar)
        └── VBoxContainer (Button container)
            ├── Title Label
            ├── Visualization Section
            │   └── Reset Board Button
            └── CoP Recording Section
                ├── Recording Label
                └── Dynamic IP Buttons (192.168.x.x)
```

### Key Features

**Non-Intrusive Design:**
- CanvasLayer renders on top of 3D scene
- 12% of screen width sidebar on left
- Semi-transparent dark background
- 3D scene fully interactive underneath

**Responsive Layout:**
- VBoxContainer handles button stacking automatically
- Buttons scale to container width
- Minimum 30px button height
- Spacer at bottom for visual balance

---

## Implementation Details

### 1. UI Initialization (Lines 830-907)

**create_ui_controls()** - Called in _ready()

```gdscript
# Creates CanvasLayer
canvas_layer = CanvasLayer.new()
canvas_layer.layer = 1

# Creates Panel for background
ui_panel = Panel.new()
ui_panel.anchor_right = 0.12  # 12% of screen width

# Creates VBoxContainer for buttons
vbox = VBoxContainer.new()

# Adds sections and Reset button
title = Label.new()
reset_btn = Button.new()
reset_btn.pressed.connect(_on_reset_board_pressed)
```

### 2. Dynamic Button Creation (Lines 910-933)

**add_recording_button(ip_address: String)** - Called when board is detected

```gdscript
# Creates toggle button for IP address
btn = Button.new()
btn.text = "Rec: 192.168.x.x [OFF]"
btn.toggle_mode = true
btn.pressed.connect(_on_recording_button_toggled.bindv([ip_address]))

# Stores in dictionaries for state management
recording_buttons[ip_address] = btn
recording_states[ip_address] = false
```

**State Management:**
- `recording_buttons` - Dictionary mapping IP → Button node
- `recording_states` - Dictionary mapping IP → bool (recording active)
- `detected_boards` - Array of board IP addresses found

### 3. Button Handlers (Lines 936-1007)

**_on_reset_board_pressed()** - Reset Board button clicked

```gdscript
# Hides all visualizations
hide_all_visualizations()
hide_all_boards()

# Resets recording state for all IPs
for ip in recording_states:
    recording_states[ip] = false
    recording_buttons[ip].button_pressed = false
    recording_buttons[ip].text = "Rec: %s [OFF]" % ip
```

**_on_recording_button_toggled(pressed, ip_address)** - Recording toggle clicked

```gdscript
# Update state
recording_states[ip_address] = pressed

# Update button appearance
if pressed:
    btn.text = "Rec: %s [ON]" % ip_address
    btn.add_theme_color_override("font_color", Color.RED)
    _send_recording_command(ip_address, true)
else:
    btn.text = "Rec: %s [OFF]" % ip_address
    btn.remove_theme_color_override("font_color")
    _send_recording_command(ip_address, false)
```

### 4. Godot-Python Communication (Lines 978-999)

**_send_recording_command(ip_address, start_recording)** - Send to Python backend

```gdscript
# Create command dictionary
command = {
    "type": "recording_control",
    "ip_address": ip_address,
    "action": "start" if start_recording else "stop"
}

# Store in network_manager for Python to read
network_manager.recording_command[ip_address] = command

# Print confirmation
print("📤 Sending recording command: START/STOP for IP %s" % ip_address)
```

### 5. Board Detection Integration (Lines 1002-1007)

**update_detected_boards(board_ips: Array)** - Called when boards detected

```gdscript
for ip in board_ips:
    if ip not in detected_boards:
        detected_boards.append(ip)
        add_recording_button(ip)
```

---

## UI Appearance

### Visual Layout

```
┌─────────────────────┐
│ MOBBO Controls      │  ← Title
├─────────────────────┤
│ Visualization       │  ← Section Header
├─────────────────────┤
│ Reset Board         │  ← Button
├─────────────────────┤
│ CoP Recording       │  ← Section Header
├─────────────────────┤
│ Rec: 192.168.0.102  │  ← Dynamic IP button
│ [OFF]               │
├─────────────────────┤
│ Rec: 192.168.0.103  │  ← Dynamic IP button
│ [OFF]               │
├─────────────────────┤
│                     │  ← Spacer
│                     │
└─────────────────────┘
```

### Button States

**Recording OFF:**
```
Rec: 192.168.x.x [OFF]
[Normal appearance]
```

**Recording ON:**
```
Rec: 192.168.x.x [ON]
[Red text color]
```

### Colors

| Element | Color | Hex |
|---------|-------|-----|
| Panel Background | Dark Gray (90% transparent) | #1a1a1a (E6) |
| Border | Gray | #4d4d4d |
| Text | White | #ffffff |
| Section Headers | Light Gray | #cccccc |
| Recording ON | Red | #ff0000 |
| Spacer Height | 200px | - |

---

## Integration with Python Backend

### Current State

The recording command is stored in `network_manager` for Python to read:

```gdscript
network_manager.recording_command[ip_address] = {
    "type": "recording_control",
    "ip_address": "192.168.x.x",
    "action": "start" | "stop"
}
```

### Python Side Integration (TODO)

To fully implement Python integration, add to `global_script.gd`:

```gdscript
# In network loop or main thread:
if "recording_command" in network_manager:
    for ip_address in network_manager.recording_command:
        command = network_manager.recording_command[ip_address]

        if command["action"] == "start":
            # Send start recording signal to Python
            # e.g., via UDP/TCP or external command
        elif command["action"] == "stop":
            # Send stop recording signal to Python
```

### Proposed Python Side Changes

In `COP_wifi_data.py`, add listener for recording commands:

```python
def set_recording_for_ip(ip_address: str, should_record: bool):
    """
    Control recording state for specific board IP
    Called from Godot UI
    """
    addr = (ip_address, 23000)  # Convert IP string to socket address

    if should_record:
        self.start_recording(addr)
    else:
        self.stop_recording(addr)
```

---

## Usage Instructions

### For Users

1. **Run Godot scene** - BoardSetup scene with 3D viewport
2. **Wait for detection** - UI will auto-populate as boards connect
3. **Reset Board** - Click "Reset Board" to clear all visualizations
4. **Record CoP** - Toggle individual "Rec: IP" buttons to start/stop recording
5. **Monitor console** - Check console for confirmation messages

### Example Workflow

```
1. Start scene
2. Boards detected:
   ✅ 192.168.0.102 connected
   ✅ 192.168.0.103 connected

3. Recording buttons appear:
   Rec: 192.168.0.102 [OFF]
   Rec: 192.168.0.103 [OFF]

4. Click first button:
   🔴 Recording CoP started for: 192.168.0.102
   Button changes to: Rec: 192.168.0.102 [ON] (red text)

5. Click Reset Board:
   🔄 Resetting board visualization...
   ⚪ Recording CoP stopped for: 192.168.0.102
   ✅ Board reset complete

6. All buttons reset to [OFF] state
```

---

## Console Output

### UI Creation

```
✅ UI controls created (CanvasLayer)
📍 Added recording button for: 192.168.0.102
📍 Added recording button for: 192.168.0.103
```

### Reset Button

```
🔄 Resetting board visualization...
✅ Board reset complete
```

### Recording Toggle

```
🔴 Recording CoP started for: 192.168.0.102
📤 Sending recording command: START for IP 192.168.0.102

⚪ Recording CoP stopped for: 192.168.0.102
📤 Sending recording command: STOP for IP 192.168.0.102
```

---

## Code Location Reference

| Function | File | Lines | Purpose |
|----------|------|-------|---------|
| `create_ui_controls()` | BoardSetup.gd | 830-907 | Create CanvasLayer and buttons |
| `add_recording_button()` | BoardSetup.gd | 910-933 | Add dynamic IP button |
| `_on_reset_board_pressed()` | BoardSetup.gd | 936-953 | Handle Reset button |
| `_on_recording_button_toggled()` | BoardSetup.gd | 956-975 | Handle recording toggle |
| `_send_recording_command()` | BoardSetup.gd | 978-999 | Send to Python |
| `update_detected_boards()` | BoardSetup.gd | 1002-1007 | Update UI with new IPs |

---

## Future Enhancements

### Phase 2: Python Integration

- [ ] Add listener in `global_script.gd` for recording commands
- [ ] Send recording start/stop signals to Python via TCP/UDP
- [ ] Add confirmation feedback from Python to Godot UI
- [ ] Show recording status indicators (recording/stopped)

### Phase 3: Advanced Features

- [ ] Add CoP visualization toggle per IP
- [ ] Add BoS visualization toggle per IP
- [ ] Add FBP visualization toggle
- [ ] Show data file paths in UI
- [ ] Display recording duration
- [ ] Add save/load session functionality

### Phase 4: Real-time Metrics

- [ ] Show CoP position per board
- [ ] Display force values (F1, F2, F3, F4)
- [ ] Show recording file size
- [ ] Display frame count recorded
- [ ] Real-time data quality indicators

---

## Testing Checklist

- [x] CanvasLayer renders without blocking 3D view
- [x] Reset Board button hides all visualizations
- [x] Reset Board button resets recording states
- [x] Dynamic buttons created for each IP detected
- [x] Recording toggle changes button appearance
- [x] Console shows correct messages
- [ ] Python receives recording commands (pending Python integration)
- [ ] Recording actually starts/stops in Python (pending Python integration)

---

## Troubleshooting

### Issue: UI not visible

**Check:**
1. Is CanvasLayer layer set to 1?
2. Is Panel anchored correctly (0.12 width)?
3. Check console for "UI controls created" message

### Issue: Buttons not appearing

**Check:**
1. Are boards being detected? (Check console for "192.168.x.x")
2. Is `update_detected_boards()` being called?
3. Check for errors in button creation

### Issue: Recording commands not received in Python

**Check:**
1. Is `network_manager` available? (Check console)
2. Is Python listening for commands on correct port?
3. Is command being stored in `network_manager.recording_command`?

---

## Summary

✅ **CanvasLayer UI System Implemented**

- Sidebar panel with Reset Board button
- Dynamic per-IP CoP recording buttons
- Real-time visual feedback (button colors)
- Godot-Python command interface (ready for integration)
- Console logging for debugging

**Next Step**: Implement Python side listener to receive and process recording commands from Godot UI.

---

**Implementation Date**: December 12, 2025
**System**: MOBBO 3D Motion Analysis
**Component**: BoardSetup.gd (NOARKGames/Games/BoardViz/)
