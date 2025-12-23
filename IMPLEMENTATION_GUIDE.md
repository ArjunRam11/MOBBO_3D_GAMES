# Implementation Guide: Fix FBP/BoS Race Conditions

## Quick Summary

**Problem:** Godot crashes reading nested FBP/BoS dicts while Python modifies them

**Solution:** Send individual points instead of nested arrays (like CoP)

**Effort:** ~30 minutes to implement & test

---

## Step 1: Modify godot_bridge.py

### 1.1 Update GodotBridgeHelper.__init__()

**Location:** [godot_bridge.py:159-192]

**Current Code:**
```python
def __init__(self, gcop_array, data_lock, ...):
    # ...
    self.fbp_data = {}          # ← Nested dict
    self.bos_data = {}          # ← Nested dict
```

**New Code:**
```python
def __init__(self, gcop_array, data_lock, ...):
    # ...
    # FIXED: Use flat arrays instead of nested dicts
    self.fbp_points = [None] * 18      # Array of 18 individual points
    self.bos_left_points = []           # Dynamic array for left foot
    self.bos_right_points = []          # Dynamic array for right foot

    # Keep old structure for backward compatibility (optional)
    self.fbp_data = {}                  # Deprecated: for transition
    self.bos_data = {}                  # Deprecated: for transition
```

### 1.2 Add Helper Method to GodotBridgeHelper

**Add after `update_BoS_data()` method:**

```python
def update_FBP_point(self, point_index: int, point_data: dict):
    """
    Update a single FBP point atomically.

    Args:
        point_index: 0-17 (18 MediaPipe keypoints)
        point_data: {'x': float, 'y': float, 'z': float}
    """
    with self.data_lock:
        if 0 <= point_index < 18 and isinstance(point_data, dict):
            self.fbp_points[point_index] = copy.deepcopy(point_data)

def update_FBP_points_batch(self, keypoints_list):
    """
    Update all FBP points at once from a list.

    Args:
        keypoints_list: List of 18 dicts or None values
    """
    with self.data_lock:
        for i in range(min(len(keypoints_list), 18)):
            kp = keypoints_list[i]
            self.fbp_points[i] = copy.deepcopy(kp) if kp else None

        # Clear remaining slots
        for i in range(len(keypoints_list), 18):
            self.fbp_points[i] = None

def update_BoS_points(self, left_foot_list, right_foot_list):
    """
    Update BoS points as flat arrays.

    Args:
        left_foot_list: List of [x, y, z] arrays
        right_foot_list: List of [x, y, z] arrays
    """
    with self.data_lock:
        self.bos_left_points = copy.deepcopy(left_foot_list) if left_foot_list else []
        self.bos_right_points = copy.deepcopy(right_foot_list) if right_foot_list else []
```

### 1.3 Update _get_camera_data()

**Location:** [godot_bridge.py:246-271]

**Current Code:**
```python
def _get_camera_data(self) -> Optional[dict]:
    """Callback for SECONDARY UDP port - FBP + BoS"""
    try:
        with self.data_lock:
            data = {"timestamp": time.time()}

            # ATOMIC READ: Get immutable references
            if self.bos_data:
                if isinstance(self.bos_data, dict) and "data" in self.bos_data:
                    data["bos"] = self.bos_data["data"]
                else:
                    data["bos"] = self.bos_data

            if self.fbp_data:
                if isinstance(self.fbp_data, dict) and "data" in self.fbp_data:
                    data["fbp"] = self.fbp_data["data"]
                else:
                    data["fbp"] = self.fbp_data

            return data if len(data) > 1 else None
```

**New Code:**
```python
def _get_camera_data(self) -> Optional[dict]:
    """Callback for SECONDARY UDP port - FBP + BoS"""
    try:
        with self.data_lock:
            data = {"timestamp": time.time()}

            # FIXED: Send flat arrays (no nested dicts)

            # FBP: Check if ANY point is valid
            fbp_has_valid = any(p is not None for p in self.fbp_points)
            if fbp_has_valid:
                # Send all 18 points as flat array
                fbp_array = list(self.fbp_points)  # Copy the array
                data["fbp"] = {"keypoints": fbp_array}

            # BoS: Check if ANY point is valid
            bos_has_valid = (len(self.bos_left_points) > 0 or
                            len(self.bos_right_points) > 0)
            if bos_has_valid:
                data["bos"] = {
                    "left_foot": list(self.bos_left_points),
                    "right_foot": list(self.bos_right_points)
                }

            return data if len(data) > 1 else None

    except Exception as e:
        logger.error(f"Error getting camera data: {e}")
    return None
```

---

## Step 2: Modify main.py

### 2.1 Update foot_shape_get_numpy_and_scatter_points()

**Location:** [main.py:950-1001]

**Current Code:**
```python
def foot_shape_get_numpy_and_scatter_points(self, foot_keys, right_heel,
                                            right_toe, left_heel, left_toe):
    # ...
    bos_data = {
        'left_foot': left_foot_clean,
        'right_foot': right_foot_clean
    }

    if left_foot_clean is not None or right_foot_clean is not None:
        self.godot_bridge.update_BoS_data(bos_data)
```

**New Code:**
```python
def foot_shape_get_numpy_and_scatter_points(self, foot_keys, right_heel,
                                            right_toe, left_heel, left_toe):
    # ...
    # Validate and clean polygon data before sending
    left_foot_clean = validate_polygon_data(self.foot_numpy_points[1])
    right_foot_clean = validate_polygon_data(self.foot_numpy_points[0])

    # FIXED: Send flat arrays instead of nested dict
    if left_foot_clean is not None or right_foot_clean is not None:
        self.godot_bridge.update_BoS_points(
            left_foot_clean,
            right_foot_clean
        )
```

### 2.2 Update run_aruco() - FBP sending

**Location:** [main.py:1143-1150]

**Current Code:**
```python
# FIXED: Simple FBP data structure (no "type" wrapper)
fbp_data = {
    'keypoints_3d': sanitize_fbp_data(keypoints_from_ref_board),
}

# Only send if valid
if fbp_data['keypoints_3d'] is not None:
    self.godot_bridge.update_FBP_data(fbp_data)
```

**New Code:**
```python
# FIXED: Send as flat array of individual points (no nested dicts)
fbp_keypoints = sanitize_fbp_data(keypoints_from_ref_board)

# Only send if valid
if fbp_keypoints is not None and len(fbp_keypoints) > 0:
    # Send all 18 points atomically
    self.godot_bridge.update_FBP_points_batch(fbp_keypoints)
```

---

## Step 3: Modify global_script.gd

### 3.1 Update Variable Declarations

**Location:** [global_script.gd:1-71]

**Current Code:**
```gdscript
var board_pose_data: Dictionary = {}
var bos_data: Dictionary = {}
var fbp_data: Dictionary = {}
```

**New Code:**
```gdscript
var board_pose_data: Dictionary = {}
var bos_data: Dictionary = {}
var fbp_data: Dictionary = {}  # Deprecated: for backward compatibility

# FIXED: Flat arrays for FBP and BoS (no nested dicts)
var fbp_points: Array = [null] * 18    # Array of 18 individual keypoints
var bos_left_points: Array = []         # Array of [x, y, z] points
var bos_right_points: Array = []        # Array of [x, y, z] points
```

### 3.2 Update handle_fbp_data_safe()

**Location:** [global_script.gd:581-683]

**Current Code:**
```gdscript
func handle_fbp_data_safe(fbp_dict) -> bool:
    # ... validation ...

    # Store validated data
    fbp_data = data_content

    # Debug log
    if Engine.get_process_frames() % 50 == 0:
        if keypoints.size() > 0:
            print("🧍 Body Pose: %d keypoints detected" % keypoints.size())

    return true
```

**New Code:**
```gdscript
func handle_fbp_data_safe(fbp_dict) -> bool:
    """Safely process Full Body Pose data with validation"""
    if typeof(fbp_dict) != TYPE_DICTIONARY:
        return false

    var data_content
    if fbp_dict.has("data"):
        data_content = fbp_dict["data"]
    else:
        data_content = fbp_dict

    if typeof(data_content) != TYPE_DICTIONARY:
        return false

    # Get keypoints - now as flat array
    var keypoints = data_content.get("keypoints", null)
    if keypoints == null or typeof(keypoints) != TYPE_ARRAY:
        return false

    # FIXED: Update flat FBP points array
    fbp_points.clear()
    fbp_points.resize(18)  # Ensure 18 slots

    for i in range(min(keypoints.size(), 18)):
        var kp = keypoints[i]
        fbp_points[i] = kp  # Store individual point

    # Store as before for backward compatibility
    fbp_data = data_content

    # Debug log
    if Engine.get_process_frames() % 50 == 0:
        var valid_count = 0
        for p in fbp_points:
            if p != null:
                valid_count += 1
        if valid_count > 0:
            print("🧍 Body Pose: %d keypoints detected" % valid_count)

    return true
```

### 3.3 Update handle_bos_data_safe()

**Location:** [global_script.gd:510-578]

**Current Code:**
```gdscript
func handle_bos_data_safe(bos_dict) -> bool:
    # ...
    # Store validated data
    bos_data = data_content

    # Debug log
    if Engine.get_process_frames() % 50 == 0:
        var has_left = data_content.get("left_foot") != null
        var has_right = data_content.get("right_foot") != null
        if has_left or has_right:
            print("👣 BoS Data: Left=%s, Right=%s" % [has_left, has_right])

    return true
```

**New Code:**
```gdscript
func handle_bos_data_safe(bos_dict) -> bool:
    """Safely process Base of Support data with validation"""
    if typeof(bos_dict) != TYPE_DICTIONARY:
        return false

    var data_content
    if bos_dict.has("data"):
        data_content = bos_dict["data"]
    else:
        data_content = bos_dict

    if typeof(data_content) != TYPE_DICTIONARY:
        return false

    # FIXED: Get flat arrays directly
    var left_foot = data_content.get("left_foot", null)
    var right_foot = data_content.get("right_foot", null)

    # Basic validation of structure
    if left_foot != null and typeof(left_foot) != TYPE_ARRAY:
        return false
    if right_foot != null and typeof(right_foot) != TYPE_ARRAY:
        return false

    # Update flat BoS points arrays
    bos_left_points = left_foot if left_foot != null else []
    bos_right_points = right_foot if right_foot != null else []

    # Store as before for backward compatibility
    bos_data = data_content

    # Debug log
    if Engine.get_process_frames() % 50 == 0:
        var has_left = left_foot != null and left_foot.size() > 0
        var has_right = right_foot != null and right_foot.size() > 0
        if has_left or has_right:
            print("👣 BoS Data: Left=%s, Right=%s" % [has_left, has_right])

    return true
```

---

## Step 4: Modify boardsetup.gd

### 4.1 Update update_fbp_from_network()

**Location:** [boardsetup.gd:485-534]

**Current Code:**
```gdscript
func update_fbp_from_network(global_script: Node) -> void:
    """ULTRA-SAFE FBP update - Fixed version with proper type checking"""
    if not global_script or not is_instance_valid(global_script):
        hide_fbp()
        return

    if not "fbp_data" in global_script:
        hide_fbp()
        return

    var fbp_data = global_script.fbp_data
    # ... 10 more validation steps ...
    fbp_data = fbp_data.duplicate()
    if not fbp_data.has("keypoints_3d"):
        hide_fbp()
        return

    var keypoints = fbp_data.get("keypoints_3d", null)
    # ... more validation ...
    plot_fbp_points(keypoints)
```

**New Code - Much Simpler:**
```gdscript
func update_fbp_from_network(global_script: Node) -> void:
    """ULTRA-SAFE FBP update - Simplified with flat array"""
    if not global_script or not is_instance_valid(global_script):
        hide_fbp()
        return

    # Check for flat points array
    if not "fbp_points" in global_script:
        hide_fbp()
        return

    var fbp_points = global_script.fbp_points
    if fbp_points == null or typeof(fbp_points) != TYPE_ARRAY:
        hide_fbp()
        return

    # Direct update from flat array (no nested dict access!)
    plot_fbp_points(fbp_points)
```

### 4.2 Update plot_fbp_points()

**Location:** [boardsetup.gd:536-599]

**Current Code:**
```gdscript
func plot_fbp_points(fbp_keypoints_array):
    """Plot FBP keypoints as simple points"""
    if fbp_keypoints_array == null or typeof(fbp_keypoints_array) != TYPE_ARRAY or fbp_keypoints_array.is_empty():
        hide_fbp()
        return

    var keypoints_snapshot: Array = fbp_keypoints_array.duplicate(false)
    var num_keypoints: int = min(keypoints_snapshot.size(), 18)

    while fbp_joint_indicators.size() < num_keypoints:
        var new_indicator = create_fbp_joint_indicator(fbp_joint_indicators.size())
        fbp_joint_indicators.append(new_indicator)

    for i in range(num_keypoints):
        if i >= fbp_joint_indicators.size():
            break

        var kp = keypoints_snapshot[i]  # ⚠️ This was the crash point

        if kp == null:
            fbp_joint_indicators[i].visible = false
            continue

        if typeof(kp) != TYPE_DICTIONARY:
            fbp_joint_indicators[i].visible = false
            continue
        # ...
```

**New Code - Fixed:**
```gdscript
func plot_fbp_points(fbp_points_array):
    """Plot FBP points from flat array - MUCH SIMPLER"""
    if fbp_points_array == null or typeof(fbp_points_array) != TYPE_ARRAY:
        hide_fbp()
        return

    var num_keypoints: int = min(fbp_points_array.size(), 18)

    # Ensure enough indicators
    while fbp_joint_indicators.size() < num_keypoints:
        var new_indicator = create_fbp_joint_indicator(fbp_joint_indicators.size())
        fbp_joint_indicators.append(new_indicator)

    # Process each keypoint (no race condition - atomic access)
    for i in range(num_keypoints):
        if i >= fbp_joint_indicators.size():
            break

        var kp = fbp_points_array[i]  # ✅ Safe: atomic single-point access

        # Validate point
        if kp == null:
            fbp_joint_indicators[i].visible = false
            continue

        if typeof(kp) != TYPE_DICTIONARY:
            fbp_joint_indicators[i].visible = false
            continue

        # Get coordinates
        var x = kp.get("x", null)
        var y = kp.get("y", null)
        var z = kp.get("z", null)

        if x == null or y == null or z == null:
            fbp_joint_indicators[i].visible = false
            continue

        var fx: float = float(x)
        var fy: float = float(y)
        var fz: float = float(z)

        if not is_finite(fx) or not is_finite(fy) or not is_finite(fz):
            fbp_joint_indicators[i].visible = false
            continue

        var kp_pos: Vector3 = Vector3(fx * POSITION_SCALE, fz * POSITION_SCALE, -fy * POSITION_SCALE)

        if not is_position_valid(kp_pos):
            fbp_joint_indicators[i].visible = false
            continue

        kp_pos.y = kp_pos.y + 0.01

        fbp_joint_indicators[i].position = kp_pos
        fbp_joint_indicators[i].visible = true

    # Hide remaining indicators
    for i in range(num_keypoints, fbp_joint_indicators.size()):
        fbp_joint_indicators[i].visible = false

    # Debug logging
    if Engine.get_process_frames() % 100 == 0:
        var visible_count = 0
        for indicator in fbp_joint_indicators:
            if indicator and is_instance_valid(indicator) and indicator.visible:
                visible_count += 1
        if visible_count > 0:
            print("  🧍 FBP: Rendered %d keypoints" % visible_count)
```

### 4.3 Update update_bos_from_network()

**Location:** [boardsetup.gd:648-684]

**Current Code:**
```gdscript
func update_bos_from_network(global_script: Node) -> void:
    """ULTRA-SAFE BoS update - Fixed version with proper type checking"""
    if not global_script or not is_instance_valid(global_script):
        hide_bos()
        return

    if not "bos_data" in global_script:
        hide_bos()
        return

    var bos_data = global_script.bos_data
    # ...
    bos_data = bos_data.duplicate()

    var left_foot = bos_data.get("left_foot", null)
    var right_foot = bos_data.get("right_foot", null)

    if left_foot == null and right_foot == null:
        hide_bos()
        return

    plot_bos_points(left_foot, right_foot)
```

**New Code - Simplified:**
```gdscript
func update_bos_from_network(global_script: Node) -> void:
    """ULTRA-SAFE BoS update - Simplified with flat arrays"""
    if not global_script or not is_instance_valid(global_script):
        hide_bos()
        return

    # Check for flat points arrays
    if not "bos_left_points" in global_script or not "bos_right_points" in global_script:
        hide_bos()
        return

    var left_foot = global_script.bos_left_points
    var right_foot = global_script.bos_right_points

    if (left_foot == null or typeof(left_foot) != TYPE_ARRAY) and \
       (right_foot == null or typeof(right_foot) != TYPE_ARRAY):
        hide_bos()
        return

    # Direct update from flat arrays (no nested dict!)
    plot_bos_points(left_foot, right_foot)
```

### 4.4 Update plot_bos_points()

The loop structure remains mostly the same, but with simpler array access:

```gdscript
func plot_bos_points(left_foot_points, right_foot_points):
    """Plot BoS foot points as simple spheres - SIMPLIFIED"""

    # Process left foot
    if left_foot_points != null and typeof(left_foot_points) == TYPE_ARRAY and \
       not left_foot_points.is_empty():

        var num_left = left_foot_points.size()

        while bos_point_indicators_left.size() < num_left:
            var new_indicator = create_bos_point_indicator(true, bos_point_indicators_left.size())
            bos_point_indicators_left.append(new_indicator)

        for i in range(num_left):
            if i >= bos_point_indicators_left.size():
                break

            var indicator = bos_point_indicators_left[i]
            if indicator == null or not is_instance_valid(indicator):
                continue

            var point = left_foot_points[i]  # ✅ Safe: flat array access

            # ... rest of validation (unchanged)
    else:
        for indicator in bos_point_indicators_left:
            if indicator and is_instance_valid(indicator):
                indicator.visible = false

    # Process right foot (similar structure)
    # ... (same pattern as left foot)
```

---

## Step 5: Testing

### 5.1 Unit Test in Python

Add this to test the changes:

```python
# In main.py, after initializing bos_estimator:
def test_fbp_points():
    """Test that FBP points are properly updated"""
    # Create test data
    test_points = [
        {'x': 0.1 * i, 'y': 0.2 * i, 'z': 0.3 * i}
        for i in range(18)
    ]

    # Update via bridge
    bos_estimator.godot_bridge.update_FBP_points_batch(test_points)

    # Verify each point was set
    for i in range(18):
        assert bos_estimator.godot_bridge.fbp_points[i] is not None
        print(f"✅ FBP Point {i}: {bos_estimator.godot_bridge.fbp_points[i]}")

    print("✅ FBP points test passed")

# Call after initialization:
# test_fbp_points()
```

### 5.2 Godot Console Monitoring

Watch for these messages:

```
✅ No FBP/BoS errors in console
✅ Messages like "🧍 FBP: Rendered 18 keypoints"
✅ Messages like "👣 BoS: Left=True, Right=True"
❌ NO "Invalid type in function 'get'" errors
❌ NO "Null reference" errors
```

### 5.3 Visual Validation

- ✅ FBP skeleton appears and follows movement
- ✅ BoS polygons appear and follow foot movement
- ✅ No visual glitches or gaps
- ✅ Smooth continuous rendering

---

## Rollback Plan

If issues arise, you can revert to old structure:

```gdscript
# In boardsetup.gd, fallback to old code:
if not "fbp_points" in global_script:
    # Try old structure
    if "fbp_data" in global_script:
        update_fbp_from_network_old(global_script)
    else:
        hide_fbp()
```

---

## Checklist

- [ ] Step 1: Modify godot_bridge.py
- [ ] Step 2: Modify main.py
- [ ] Step 3: Modify global_script.gd
- [ ] Step 4: Modify boardsetup.gd
- [ ] Step 5: Run and test for 10+ minutes
- [ ] Verify no crashes in Godot console
- [ ] Verify FBP/BoS rendering properly
- [ ] Test reset board functionality
- [ ] Commit changes to git

---

## Verification Commands

```bash
# Check for any remaining nested dict patterns:
grep -r "fbp_data\[" .
grep -r "bos_data\[" .

# Should return only old/deprecated references

# In Godot, run this in console after connecting:
print(GlobalScript.fbp_points.size())  # Should print 18
print(GlobalScript.bos_left_points.size())  # Should print number of points
```

