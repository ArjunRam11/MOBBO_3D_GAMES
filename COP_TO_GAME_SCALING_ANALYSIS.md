# CoP Position Scaling Analysis & Board Layout Mapping

## Overview
All games use the global CoP position received from Python to control game object movement. The scaling is done through predefined variables in `global_script.gd` that map the raw CoP coordinates to screen positions.

---

## Current Game Implementation Analysis

### 1. **Flappy Bird** (`flappy_bird/Scripts/pilot.gd`)
**Lines 25-42: Movement Logic**
```gdscript
func _physics_process(delta: float) -> void:
    if debug_mode:
        network_position = get_global_mouse_position()
    elif adapt_toggle:
        if flappy.is_3d_mode:
           network_position = GlobalScript.scaled_network_position3D  # ← SCALED
        else:
            network_position = GlobalScript.scaled_network_position   # ← SCALED
    else:
        network_position = GlobalScript.network_position3D if flappy.is_3d_mode else GlobalScript.network_position

    if network_position != Vector2.ZERO:
        network_position = network_position - zero_offset + Vector2(600, 100)  # ← OFFSET ADJUSTMENT
        position = position.lerp(network_position, 0.8)  # ← SMOOTH MOVEMENT
    position.x = 100
    position.y = clamp(position.y, MIN_BOUNDS.y, MAX_BOUNDS.y)
```

**Key Variables:**
- `GlobalScript.network_position3D` - Unscaled CoP position (3D mode)
- `GlobalScript.scaled_network_position3D` - Scaled CoP position (3D mode)
- `zero_offset` - Calibration offset
- Movement smoothing: 0.8 (lerp factor)

---

### 2. **Fruit Catcher** (`fruit_catcher/Scenes/Paddle/paddle.gd`)
**Lines 46-76: Movement Logic**
```gdscript
func _physics_process(delta: float) -> void:
    _update_network_position()
    _update_paddle_position()

func _update_network_position() -> void:
    if debug_mode:
        network_position = get_global_mouse_position()
    elif adapt_toggle:
        network_position = GlobalScript.scaled_network_position  # ← SCALED
    else:
        network_position = GlobalScript.network_position  # ← UNSCALED

func _update_paddle_position() -> void:
    if network_position != Vector2.ZERO:
        var movement_distance = network_position.distance_to(last_network_position)
        if movement_distance > MOVEMENT_THRESHOLD:  # 2.0
            var adjusted_position = network_position - zero_offset + centre  # ← OFFSET + CENTER
            position.x = lerp(position.x, adjusted_position.x, POSITION_LERP_SPEED)  # 0.8
            last_network_position = network_position

    position.x = clampf(position.x, MIN_X_VALUE, MAX_X_VALUE)
    position.y = 615.0  # FIXED Y POSITION
```

**Key Variables:**
- `GlobalScript.network_position` - Unscaled CoP position (2D mode)
- `GlobalScript.scaled_network_position` - Scaled CoP position (2D mode)
- `centre` - Center offset: `Vector2(120, 200)`
- Movement smoothing: 0.8 (POSITION_LERP_SPEED)

---

### 3. **Jumpify** (`Jumpify/Scripts/2Dplayer.gd`)
**Lines 176-242: Movement Logic**
```gdscript
func update_player_position() -> void:
    if debug_mode:
        network_position = get_global_mouse_position()
    elif adapt_toggle:
        network_position = GlobalScript.scaled_network_position3D  # ← SCALED
    else:
        network_position = GlobalScript.network_position3D  # ← UNSCALED

    if network_position != Vector2.ZERO:
        network_position = network_position - zero_offset  # ← APPLY OFFSET
        position = position.lerp(network_position, movement_smoothing)  # 1.0 (DIRECT)
        position.x = clamp(position.x, MIN_BOUNDS.x, MAX_BOUNDS.x)
        position.y = clamp(position.y, MIN_BOUNDS.y, MAX_BOUNDS.y)
        update_position_tracking()

func update_position_tracking() -> void:
    pos_x = GlobalScript.raw_x
    pos_y = GlobalScript.raw_y
    pos_z = GlobalScript.raw_z

    if not adapt_toggle:
        # IMPORTANT: Converts pixel position back to game coordinates
        game_x = (position.x - GlobalScript.X_SCREEN_OFFSET) / GlobalScript.PLAYER_POS_SCALER_X
        game_y = 0.0
        game_z = (position.y - GlobalScript.Y_SCREEN_OFFSET) / GlobalScript.PLAYER_POS_SCALER_Z
    else:
        game_x = (position.x - GlobalScript.X_SCREEN_OFFSET) / (GlobalScript.PLAYER_POS_SCALER_X * GlobalSignals.global_scalar_x)
        game_y = 0.0
        game_z = (position.y - GlobalScript.Y_SCREEN_OFFSET) / (GlobalScript.PLAYER_POS_SCALER_Z * GlobalSignals.global_scalar_y)
```

**Key Variables:**
- `GlobalScript.network_position3D` - Unscaled CoP position
- `GlobalScript.raw_x`, `raw_y`, `raw_z` - Raw CoP values from Python
- `GlobalScript.X_SCREEN_OFFSET`, `Y_SCREEN_OFFSET` - Screen position offsets
- `GlobalScript.PLAYER_POS_SCALER_X`, `PLAYER_POS_SCALER_Z` - Scaling factors
- Movement smoothing: 1.0 (DIRECT, no lerp)

---

## Scaling Variables in global_script.gd (Lines 40-105)

### Current Scaling Configuration
```gdscript
# 2D Game positions
@export var PLAYER_POS_SCALER_X: int = 20 * 100      # 2000 pixels per unit
@export var PLAYER_POS_SCALER_Z: int = 20 * 100      # 2000 pixels per unit

# 3D Game positions
@export var PLAYER3D_POS_SCALER_X: int = 20 * 100    # 2000 pixels per unit
@export var PLAYER3D_POS_SCALER_Y: int = 30 * 100    # 3000 pixels per unit

# Screen offsets
var X_SCREEN_OFFSET: int                   # Initialized in _ready()
var Y_SCREEN_OFFSET: int                   # Initialized in _ready()
var Y_SCREEN_OFFSET3D: int                 # Initialized in _ready()

# Raw CoP values from Python (lines 89-95)
var raw_x: float = 0.0      # ← FROM PYTHON
var raw_y: float = 0.0      # ← FROM PYTHON
var raw_z: float = 0.0      # ← FROM PYTHON

# Calculated screen positions (lines 101-108)
var network_position: Vector2 = Vector2.ZERO           # 2D calculated
var network_position3D: Vector2 = Vector2.ZERO         # 3D calculated
var scaled_network_position: Vector2 = Vector2.ZERO    # 2D with adaptive scaling
var scaled_network_position3D: Vector2 = Vector2.ZERO  # 3D with adaptive scaling
```

---

## How Scaling Works (Current Implementation - Lines 393-407)

**In `handle_cop_data_safe()` function:**
```gdscript
# STEP 1: Get raw CoP from Python (line 381-384)
raw_x = float(gc_x)
raw_y = float(gc_y)
raw_z = float(gc_z)

# STEP 2: Calculate screen positions using SCALERS (lines 393-401)
net_x = raw_x * PLAYER_POS_SCALER_X + X_SCREEN_OFFSET
net_y = raw_y * PLAYER3D_POS_SCALER_Y + Y_SCREEN_OFFSET3D
net_z = raw_z * PLAYER_POS_SCALER_Z + Y_SCREEN_OFFSET

# STEP 3: Store as Vector2 for 2D/3D games (lines 399-401)
network_position = Vector2(net_x, net_z)
network_position3D = Vector2(net_x, net_y)
```

---

## Board Layout Information

**Received from Python in `board_pose_data`:**
```gdscript
# Line 545-549 in global_script.gd
if data_content.has("layout"):
    var layout_container = data_content["layout"]
    if typeof(layout_container) == TYPE_DICTIONARY:
        print("📐 Board Layout: %s" % str(layout_container))
```

**Layout values:**
- `layout_container["Board_Layout"]` = "1x2" or "2x1"

---

## CoP Scaling Configuration by Board Layout

### Board Layout 1x2 (1 board vertically, 2 boards horizontally)
**User stands facing LEFT-RIGHT axis**

| Parameter | Value | Explanation |
|-----------|-------|-------------|
| CoP X Range | -0.90 to 0.30 | Left to Right movement |
| CoP Y Range | -0.225 to 0.225 | Forward to Backward movement |
| Board Height | 2 units (1x2) | 2 boards stacked vertically |
| Board Width | 1 unit | 1 board horizontally |

### Board Layout 2x1 (2 boards horizontally, 1 board vertically)
**User stands facing FORWARD-BACKWARD axis**

| Parameter | Value | Explanation |
|-----------|-------|-------------|
| CoP X Range | 0.30 to -0.30 | Right to Left movement (reversed) |
| CoP Y Range | -0.225 to 0.675 | Back to Front movement |
| Board Height | 1 unit | 1 board vertically |
| Board Width | 2 units (2x1) | 2 boards stacked horizontally |

---

## Implementation Strategy

### Step 1: Define Board Layout Variables in global_script.gd

Add these variables after line 95:
```gdscript
# ============================================================
# BOARD LAYOUT SCALING CONFIGURATION
# ============================================================
var board_layout: String = "2x1"  # Default layout

# Scaling ranges based on board layout
var cop_x_min: float = -0.30
var cop_x_max: float = 0.30
var cop_y_min: float = -0.225
var cop_y_max: float = 0.675

func set_scaling_for_layout(layout: String) -> void:
    """Update scaling variables based on board layout"""
    board_layout = layout

    if layout == "1x2":
        # Layout: 1 board wide, 2 boards tall (vertical stacking)
        cop_x_min = -0.90
        cop_x_max = 0.30
        cop_y_min = -0.225
        cop_y_max = 0.225
        print("📐 Scaling configured for 1x2 layout")

    elif layout == "2x1":
        # Layout: 2 boards wide, 1 board tall (horizontal stacking)
        cop_x_min = 0.30
        cop_x_max = -0.30  # REVERSED
        cop_y_min = -0.225
        cop_y_max = 0.675
        print("📐 Scaling configured for 2x1 layout")
    else:
        print("⚠️ Unknown layout: %s, using default 2x1" % layout)
        cop_x_min = 0.30
        cop_x_max = -0.30
        cop_y_min = -0.225
        cop_y_max = 0.675
```

### Step 2: Extract Layout from Board Pose Data

Modify `handle_board_pose_data_safe()` function (around line 545-549):
```gdscript
# Extract and store board layout if included
if data_content.has("layout"):
    var layout_container = data_content["layout"]
    if typeof(layout_container) == TYPE_DICTIONARY:
        var layout_str = layout_container.get("Board_Layout", "2x1")
        print("📐 Board Layout: %s" % layout_str)
        # CRITICAL: Call the scaling update function
        set_scaling_for_layout(layout_str)
```

### Step 3: Update CoP Scaling in handle_cop_data_safe()

Modify the calculation logic (around lines 393-401):
```gdscript
# CRITICAL: Scale raw CoP values based on board layout ranges
# Normalize raw CoP from board range to screen range

# Determine actual x range (2x1 is reversed)
var actual_x_min = min(cop_x_min, cop_x_max)
var actual_x_max = max(cop_x_min, cop_x_max)
var actual_y_min = min(cop_y_min, cop_y_max)
var actual_y_max = max(cop_y_min, cop_y_max)

# Normalize CoP value to 0.0-1.0 range based on board layout
var normalized_x = (raw_x - actual_x_min) / (actual_x_max - actual_x_min)
var normalized_y = (raw_y - actual_y_min) / (actual_y_max - actual_y_min)

# Clamp to valid range
normalized_x = clampf(normalized_x, 0.0, 1.0)
normalized_y = clampf(normalized_y, 0.0, 1.0)

# Map to screen coordinates
# For 2x1 layout with reversed X, invert the normalized_x
if board_layout == "2x1" and cop_x_min > cop_x_max:
    normalized_x = 1.0 - normalized_x

# Screen width/height for mapping
var screen_width = float(MAX_X - MIN_X)
var screen_height = float(MAX_Y - MIN_Y)

# Calculate final screen positions
net_x = MIN_X + (normalized_x * screen_width)
net_y = MIN_Y + (normalized_y * screen_height)

# Alternative: Keep existing offset-based scaling
# net_x = raw_x * PLAYER_POS_SCALER_X + X_SCREEN_OFFSET
# net_z = raw_z * PLAYER_POS_SCALER_Z + Y_SCREEN_OFFSET

network_position = Vector2(net_x, net_z)
network_position3D = Vector2(net_x, net_y)
```

---

## Variables to Modify

### Primary Variables (Lines 40-56, 89-108)

| Variable | Current Value | Purpose | Location |
|----------|---------------|---------|----------|
| `PLAYER_POS_SCALER_X` | 2000 | Pixels per unit X | Line 51 |
| `PLAYER_POS_SCALER_Z` | 2000 | Pixels per unit Z | Line 52 |
| `PLAYER3D_POS_SCALER_X` | 2000 | Pixels per unit X (3D) | Line 55 |
| `PLAYER3D_POS_SCALER_Y` | 3000 | Pixels per unit Y (3D) | Line 56 |
| `X_SCREEN_OFFSET` | auto | X center offset | Line 40 |
| `Y_SCREEN_OFFSET` | auto | Y center offset | Line 41 |
| `Y_SCREEN_OFFSET3D` | auto | Y center offset (3D) | Line 44 |
| `raw_x` | from Python | Raw CoP X | Line 93 |
| `raw_y` | from Python | Raw CoP Y | Line 94 |
| `raw_z` | from Python | Raw CoP Z | Line 95 |

### New Variables to Add (After Line 95)

```gdscript
# Board layout configuration
var board_layout: String = "2x1"
var cop_x_min: float = 0.30
var cop_x_max: float = -0.30
var cop_y_min: float = -0.225
var cop_y_max: float = 0.675
```

### Calculated Output Variables

| Variable | Type | Used By | Purpose |
|----------|------|---------|---------|
| `network_position` | Vector2 | Fruit Catcher, Flappy Bird (2D) | Unscaled CoP→screen position (X, Z) |
| `network_position3D` | Vector2 | Jumpify, Flappy Bird (3D) | Unscaled CoP→screen position (X, Y) |
| `scaled_network_position` | Vector2 | Games with Adapt toggle | Scaled CoP (2D) |
| `scaled_network_position3D` | Vector2 | Games with Adapt toggle | Scaled CoP (3D) |

---

## Game Switching Recommendations

**Update each game to:**
1. Accept board layout from global_script
2. Use appropriate scaler variables
3. Handle layout changes during gameplay

**Add to each game's _ready() function:**
```gdscript
func _ready() -> void:
    # Connect to board layout changes if needed
    if GlobalScript.board_layout == "1x2":
        # Adjust game boundaries for vertical layout
        pass
    elif GlobalScript.board_layout == "2x1":
        # Adjust game boundaries for horizontal layout
        pass
```

---

## Testing Checklist

- [ ] Verify board layout is detected and printed
- [ ] Verify scaling ranges are set correctly per layout
- [ ] Test CoP movement maps to correct game object movement
- [ ] Test 1x2 layout: X range -0.90 to 0.30, Y range -0.225 to 0.225
- [ ] Test 2x1 layout: X range 0.30 to -0.30 (reversed), Y range -0.225 to 0.675
- [ ] Verify no game crashes on layout change
- [ ] Verify smooth movement with lerp values (0.8 for smooth, 1.0 for responsive)

---

## Example Usage

```gdscript
# When board pose data arrives with layout:
func handle_board_pose_data_safe(board_data) -> bool:
    # ... existing code ...

    if data_content.has("layout"):
        var layout_container = data_content["layout"]
        if typeof(layout_container) == TYPE_DICTIONARY:
            var layout_str = layout_container.get("Board_Layout", "2x1")
            set_scaling_for_layout(layout_str)
            print("✅ Board layout updated: %s" % layout_str)
            print("   CoP X Range: %.2f to %.2f" % [cop_x_min, cop_x_max])
            print("   CoP Y Range: %.2f to %.2f" % [cop_y_min, cop_y_max])

    return true
```

---

## Summary

- **All games use**: `GlobalScript.network_position` or `GlobalScript.network_position3D`
- **Key scaling variables**: `PLAYER_POS_SCALER_X`, `PLAYER_POS_SCALER_Z`, offsets
- **Raw CoP values**: `raw_x`, `raw_y`, `raw_z` (from Python)
- **Board layout determines**: CoP scaling ranges and orientation
- **Implementation location**: `global_script.gd` lines 393-407 (CoP→screen conversion)
