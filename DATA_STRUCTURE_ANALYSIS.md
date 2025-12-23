# MOBBO Data Structure Analysis: Race Conditions in FBP/BoS

## Executive Summary

You've correctly identified a **race condition between Python and Godot** affecting **FBP (Full Body Pose)** and **BoS (Base of Support)** data. The issue stems from:

1. **Nested dictionary structures** being sent from Python
2. **Shallow copying in Godot** causing concurrent access conflicts
3. **Thread-safe atomic replacement in Python** that doesn't protect the nested content

**YES, sending individual points separately will fix this issue.** This document explains why and how.

---

## Part 1: Current Data Architecture

### 1.1 Working Data (CoP/GCoP) - WHY IT WORKS

**Python Side** [main.py:916-944]:
```python
gcop_data = {
    'x': float,              # Single value
    'y': float,              # Single value
    'z': float,              # Single value
    'weight': float          # Single value
}

self.godot_bridge.update_cop_data(
    local_cops=local_cops_data,
    gcop=gcop_data,
    total_weight=total_weight
)
```

**Godot Bridge** [godot_bridge.py:273-283]:
```python
def update_cop_data(self, local_cops: list, gcop: dict, total_weight: float):
    with self.data_lock:
        # ATOMIC: Replace entire reference atomically
        self.local_cops = copy.deepcopy(local_cops) if local_cops else []
        self.gcop = copy.deepcopy(gcop) if gcop else {}
        self.total_weight = total_weight
```

**Godot Side** [global_script.gd:271-407]:
```gdscript
func handle_cop_data_safe(cop_data) -> bool:
    if typeof(cop_data) != TYPE_DICTIONARY:
        return false

    # Process local CoPs - simple array of dictionaries
    if cop_data.has("local_cops"):
        var local_cops_array = cop_data["local_cops"]
        if typeof(local_cops_array) == TYPE_ARRAY:
            local_cops.clear()
            for local_cop in local_cops_array:
                local_cops.append({...})

    # Process global CoP - simple dictionary
    if cop_data.has("gcop"):
        var gcop = cop_data["gcop"]
        raw_x = float(gcop.get("x", null))
        raw_y = float(gcop.get("y", null))
        raw_z = float(gcop.get("z", null))
```

**Why CoP/GCoP Works:**
- ✅ Single-level dictionaries (no nesting)
- ✅ Atomic replacement: old reference stays valid during swap
- ✅ No complex iteration needed
- ✅ All values accessed immediately, not deferred

---

### 1.2 Broken Data (FBP) - THE PROBLEM

**Python Side** [main.py:1143-1150]:
```python
fbp_data = {
    'keypoints_3d': sanitize_fbp_data(keypoints_from_ref_board),
    # sanitize_fbp_data returns a LIST of 18 dictionaries:
    # [{'x': float, 'y': float, 'z': float}, {...}, ...]
}

self.godot_bridge.update_FBP_data(fbp_data)
```

**Godot Bridge** [godot_bridge.py:313-317]:
```python
def update_FBP_data(self, FBP_XYZ):
    """Update FBP data - ATOMIC REPLACEMENT"""
    with self.data_lock:
        # Atomic replacement - looks safe...
        self.fbp_data = copy.deepcopy(FBP_XYZ) if isinstance(FBP_XYZ, dict) else {}
```

**Godot Side** [boardsetup.gd:485-533]:
```gdscript
func update_fbp_from_network(global_script: Node) -> void:
    # Step 2: Get reference (single atomic operation)
    var fbp_data = global_script.fbp_data  # ⚠️ Gets reference to dict

    # Step 5: NOW safe to duplicate
    fbp_data = fbp_data.duplicate()  # ⚠️ SHALLOW COPY!

    # Step 6: Check for keypoints
    if not fbp_data.has("keypoints_3d"):
        return

    var keypoints = fbp_data.get("keypoints_3d", null)  # ⚠️ Still a reference!

    # Step 8: Iterate through all 18 keypoints
    plot_fbp_points(keypoints)  # ⚠️ Array might change during iteration
```

**plot_fbp_points** [boardsetup.gd:536-599]:
```gdscript
func plot_fbp_points(fbp_keypoints_array):
    var keypoints_snapshot: Array = fbp_keypoints_array.duplicate(false)  # Shallow copy!
    var num_keypoints: int = min(keypoints_snapshot.size(), 18)

    for i in range(num_keypoints):
        var kp = keypoints_snapshot[i]  # ⚠️ Reading from array

        if kp == null:
            fbp_joint_indicators[i].visible = false
            continue

        if typeof(kp) != TYPE_DICTIONARY:  # ⚠️ CRASH: kp might be None or corrupted!
            fbp_joint_indicators[i].visible = false
            continue
```

**Why FBP Fails - THE RACE CONDITION:**

```
Timeline of the Race Condition:

Python Thread (compute_COP):
T1: Create new fbp_keypoints array: [kp0, kp1, kp2, ..., kp17]
T2: Copy into fbp_data: {'keypoints_3d': [kp0, kp1, ...]}
T3: Replace self.fbp_data with new dict (ATOMIC)
    ✓ OLD fbp_data reference becomes invalid
    ✓ NEW fbp_data reference is valid

Godot Thread (boardsetup._process):
T1: Get reference: var fbp_data = global_script.fbp_data
T2: Shallow copy: fbp_data.duplicate()
    ⚠️ NEW dict created, but fbp_data["keypoints_3d"] is SAME ARRAY REFERENCE
T3: Get array reference: var keypoints = fbp_data.get("keypoints_3d")
T4: Loop: for i in range(18):
T5:   Read: var kp = keypoints[i]

    PROBLEM SEQUENCE:
    Between T4 and T5, Python might:
    - Create NEW fbp_data with NEW keypoints array
    - Godot's keypoints reference now points to OLD array
    - Python deletes old array while Godot reads it
    - Godot reads garbage, tries to access .get("x")
    - CRASH: "Invalid type in function 'get'"
```

---

### 1.3 Similar Problem with BoS Data

**Python Side** [main.py:994-1001]:
```python
bos_data = {
    'left_foot': left_foot_clean,   # Array of [x, y, z] arrays
    'right_foot': right_foot_clean  # Array of [x, y, z] arrays
}

if left_foot_clean is not None or right_foot_clean is not None:
    self.godot_bridge.update_BoS_data(bos_data)
```

**Godot Side** [boardsetup.gd:648-684]:
```gdscript
func update_bos_from_network(global_script: Node) -> void:
    var bos_data = global_script.bos_data
    bos_data = bos_data.duplicate()  # SHALLOW COPY!

    var left_foot = bos_data.get("left_foot", null)
    var right_foot = bos_data.get("right_foot", null)

    # Problem: left_foot and right_foot are still references
    plot_bos_points(left_foot, right_foot)  # ⚠️ Might be invalid during iteration
```

**Godot Side** [boardsetup.gd:687-803]:
```gdscript
func plot_bos_points(left_foot_points, right_foot_points):
    if left_foot_points != null and typeof(left_foot_points) == TYPE_ARRAY:
        var left_snapshot = left_foot_points.duplicate(false)  # Shallow!
        var num_left = left_snapshot.size()

        for i in range(num_left):
            var point = left_snapshot[i]  # ⚠️ Could be None or corrupted

            if point == null or typeof(point) != TYPE_ARRAY or point.size() < 3:
                ⚠️ CRASH: Null dereference
```

---

## Part 2: Why This Happens

### 2.1 The Shallow Copy Problem

In Godot, `.duplicate(false)` = **shallow copy** only:

```gdscript
# Python sends:
fbp_data = {
    'keypoints_3d': [
        {'x': 0.1, 'y': 0.2, 'z': 0.3},
        {'x': 0.4, 'y': 0.5, 'z': 0.6},
        ...
    ]
}

# Godot receives and does:
var fbp_copy = fbp_data.duplicate()  # Creates new dict, but...

# The array reference is copied, not the array itself:
fbp_copy['keypoints_3d']  # ← Points to SAME array object as original!
```

When Python replaces the entire `fbp_data` with a new dict:
- Old dict is dereferenced
- Old array might be garbage collected
- Godot still holds reference to old array
- **Reading from garbage = CRASH**

### 2.2 Thread Timing

Python's `copy.deepcopy()` in `update_FBP_data()` helps but doesn't solve the problem:

```python
# Python (godot_bridge.py line 315-317):
with self.data_lock:
    self.fbp_data = copy.deepcopy(FBP_XYZ)  # Creates deep copy
    # Replaces old dict reference
```

But Godot's shallow copy means:
- ✅ NEW dict is created from the deep copy
- ✅ References are atomic in Python
- ❌ Godot still gets shallow copy
- ❌ Inner arrays are still shared references
- ❌ Race condition STILL exists

---

## Part 3: The Solution - Individual Point Architecture

### 3.1 Proposed Architecture

Instead of:
```python
# ❌ CURRENT (nested dict)
fbp_data = {
    'keypoints_3d': [
        {'x': 0.1, 'y': 0.2, 'z': 0.3},
        {'x': 0.4, 'y': 0.5, 'z': 0.6},
        ...
    ]
}
```

Send individual points:
```python
# ✅ PROPOSED (atomic points)
# Send each as separate update:
fbp_point_0 = {'x': 0.1, 'y': 0.2, 'z': 0.3}
fbp_point_1 = {'x': 0.4, 'y': 0.5, 'z': 0.6}
...
fbp_point_17 = {'x': 1.2, 'y': 1.3, 'z': 1.4}
```

Or batch by shoulder/keypoint index:
```python
# OR: Send grouped by body part
upper_body_points = {
    'shoulder_l': {'x': ..., 'y': ..., 'z': ...},
    'shoulder_r': {'x': ..., 'y': ..., 'z': ...},
    'elbow_l': {'x': ..., 'y': ..., 'z': ...},
    ...
}
```

### 3.2 WHY Individual Points Fix The Race Condition

**Each point is atomic:**
```python
# When updating point 0:
self.fbp_point_0 = copy.deepcopy({'x': 0.1, 'y': 0.2, 'z': 0.3})
# No nested structure to cause race conditions
```

**Godot receives single points:**
```gdscript
# No iteration over shared arrays
var fbp_point_0 = global_script.fbp_point_0
if fbp_point_0 != null:
    var x = fbp_point_0.get("x", null)  # Direct access
    var y = fbp_point_0.get("y", null)  # No shared state
    var z = fbp_point_0.get("z", null)
```

**Same pattern as CoP (which works):**
- ✅ Single-level dict: `{'x': ..., 'y': ..., 'z': ...}`
- ✅ No nested arrays or complex nesting
- ✅ Atomic replacement
- ✅ No shared references

---

## Part 4: Implementation Comparison

### 4.1 Current (Broken) Architecture

| Aspect | CoP | FBP | BoS |
|--------|-----|-----|-----|
| **Structure** | Simple dict | Nested list | Nested list |
| **Atomicity** | ✅ Yes | ✅ Replace dict, ❌ Inner array | ✅ Replace dict, ❌ Inner array |
| **Shallow Copy Safe** | ✅ Yes | ❌ No (array ref) | ❌ No (array ref) |
| **Status** | ✅ Works | ❌ Crashes | ❌ Crashes |
| **Keypoint Count** | N/A | 18 | ~6-10 per foot |

### 4.2 Proposed (Fixed) Architecture

| Aspect | CoP | FBP | BoS |
|--------|-----|-----|-----|
| **Structure** | Single point | Individual points | Individual points |
| **Atomicity** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Shallow Copy Safe** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Status** | ✅ Works | ✅ Will work | ✅ Will work |
| **Update Frequency** | Low (~50 Hz) | Medium (~100 Hz) | Low (~50 Hz) |

---

## Part 5: Implementation Steps

### 5.1 Option A: Array-Indexed Approach (Recommended)

**Python Side** [main.py modifications]:

```python
# Replace the nested FBP dict with indexed properties
class GodotBridgeHelper:
    def __init__(self, ...):
        # Instead of:
        # self.fbp_data = {}

        # Use individual slots:
        self.fbp_points = [None] * 18  # Array of 18 individual points
        self.bos_left_points = []  # Dynamic array
        self.bos_right_points = []  # Dynamic array
```

Then in `update_FBP_data()`:

```python
def update_FBP_data(self, FBP_XYZ):
    """Update FBP data - Each point is atomic"""
    with self.data_lock:
        if FBP_XYZ and isinstance(FBP_XYZ, dict):
            keypoints = FBP_XYZ.get('keypoints_3d', [])

            # Replace individual points atomically
            for i, kp in enumerate(keypoints):
                if i < 18:  # 18 keypoints max
                    self.fbp_points[i] = copy.deepcopy(kp) if kp else None
                else:
                    break

            # Clear remaining slots
            for i in range(len(keypoints), 18):
                self.fbp_points[i] = None
```

Then in `_get_camera_data()`:

```python
def _get_camera_data(self) -> Optional[dict]:
    """Send individual FBP points"""
    try:
        with self.data_lock:
            data = {"timestamp": time.time()}

            # Send all 18 FBP points in array format
            fbp_array = []
            for i in range(18):
                point = self.fbp_points[i]
                if point:
                    fbp_array.append(point)
                else:
                    fbp_array.append(None)

            if any(p is not None for p in fbp_array):
                data["fbp"] = {"keypoints": fbp_array}

            # Similar for BoS
            if self.bos_left_points or self.bos_right_points:
                data["bos"] = {
                    "left_foot": self.bos_left_points,
                    "right_foot": self.bos_right_points
                }

            return data if len(data) > 1 else None
    except Exception as e:
        logger.error(f"Error getting camera data: {e}")
    return None
```

**Godot Side** [global_script.gd modifications]:

```gdscript
# Instead of nested dict:
var fbp_data: Dictionary = {}

# Use flat array:
var fbp_points: Array = [null] * 18

func handle_fbp_data_safe(fbp_dict) -> bool:
    if typeof(fbp_dict) != TYPE_DICTIONARY:
        return false

    var keypoints = fbp_dict.get("keypoints", null)
    if keypoints == null or typeof(keypoints) != TYPE_ARRAY:
        return false

    # Update individual slots
    for i in range(min(keypoints.size(), 18)):
        fbp_points[i] = keypoints[i]

    # Store as before for backward compatibility
    fbp_data = {"keypoints_3d": keypoints}

    return true
```

**Godot Side** [boardsetup.gd modifications]:

```gdscript
func update_fbp_from_network(global_script: Node) -> void:
    """Update FBP from flat array - NO NESTED ITERATION"""
    if not global_script or not is_instance_valid(global_script):
        hide_fbp()
        return

    if not "fbp_points" in global_script:
        hide_fbp()
        return

    var fbp_points = global_script.fbp_points
    if fbp_points == null or typeof(fbp_points) != TYPE_ARRAY:
        hide_fbp()
        return

    # Direct point-by-point update (no iteration of shared array!)
    plot_fbp_points(fbp_points)

func plot_fbp_points(fbp_points_array):
    """Plot FBP from flat array - MUCH SIMPLER"""
    if fbp_points_array == null:
        hide_fbp()
        return

    var num_keypoints = min(fbp_points_array.size(), 18)

    for i in range(num_keypoints):
        # Each point is accessed ONCE, atomically
        var kp = fbp_points_array[i]

        if i >= fbp_joint_indicators.size():
            break

        if kp == null:
            fbp_joint_indicators[i].visible = false
            continue

        if typeof(kp) != TYPE_DICTIONARY:
            fbp_joint_indicators[i].visible = false
            continue

        # ... rest of validation
```

### 5.2 Option B: Named Properties Approach

Instead of arrays, use individual properties:

```python
# Python
def update_FBP_point(self, point_index: int, point_data: dict):
    """Update single FBP point"""
    with self.data_lock:
        if 0 <= point_index < 18:
            self.fbp_point_{point_index} = copy.deepcopy(point_data)
```

**Pros:**
- Very explicit
- No array indexing confusion

**Cons:**
- More code (18 properties)
- Harder to maintain
- Harder to loop

**Recommendation: Use Option A (Array-Indexed)**

---

## Part 6: Detailed Comparison: CoP vs FBP

### Why CoP Works Fine

```python
# PYTHON - Simple atomic dict
gcop_data = {'x': 0.1, 'y': 0.2, 'z': 0.3, 'weight': 10.0}

# GODOT - Gets it directly
var gcop = global_script.raw_x  # Simple float
var gcop = global_script.raw_y  # Simple float
var gcop = global_script.raw_z  # Simple float
```

**No nesting, no race condition.**

### Why FBP Fails

```python
# PYTHON - Nested array of dicts
fbp_data = {
    'keypoints_3d': [
        {'x': 0.1, 'y': 0.2, 'z': 0.3},  # Keypoint 0
        {'x': 0.4, 'y': 0.5, 'z': 0.6},  # Keypoint 1
        # ... 16 more
    ]
}

# GODOT - Accesses nested structure with race condition
var kp = fbp_data['keypoints_3d'][i]  # ⚠️ Array might change
```

**Nesting creates race condition window.**

### Fix: FBP Like CoP

```python
# PYTHON - Flat array of simple dicts (like local_cops)
fbp_points = [
    {'x': 0.1, 'y': 0.2, 'z': 0.3},  # Keypoint 0
    {'x': 0.4, 'y': 0.5, 'z': 0.6},  # Keypoint 1
    # ... 16 more
]

# GODOT - Direct access, no race condition
var kp = fbp_points[i]  # ✅ Simple array, not nested dict
```

**Same pattern as working CoP.**

---

## Part 7: Testing Strategy

### Before Implementation

Test current (broken) state:
```bash
python main.py
# Check Godot console for:
# - "Invalid type in function 'get'" - FBP crash
# - "Null reference" - BoS crash
# - Count of successful cycles vs crashes
```

### After Implementation

Test fixed state:
```bash
python main.py
# Check Godot console for:
# - No FBP/BoS errors
# - Consistent point updates
# - Smooth visualization
```

Validation:
1. ✅ No type errors in Godot console
2. ✅ FBP skeleton renders without gaps
3. ✅ BoS polygons render without corruption
4. ✅ 100+ consecutive frames without crash

---

## Part 8: Summary & Recommendation

### Root Cause
- **Nested dictionaries** with **shallow copying** in Godot
- **Thread race condition** between Python (modifying) and Godot (reading)
- **Shared array references** survive `.duplicate(false)`

### Solution
**YES, send each individual point separately** like you do with CoP. This:
- ✅ Eliminates nested structures
- ✅ Makes each update atomic
- ✅ Matches the working CoP pattern
- ✅ Simplifies Godot code
- ✅ Reduces bandwidth (individual updates only when changed)
- ✅ Removes race condition window

### Implementation Effort
- **Low effort** - Mostly reorganizing existing data
- **Low risk** - CoP already uses this pattern
- **High impact** - Fixes both FBP and BoS crashes

### Recommended Path
1. Modify `godot_bridge.py`: Use arrays of individual points
2. Update `main.py`: Send point arrays instead of nested dicts
3. Update `global_script.gd`: Store flat arrays
4. Update `boardsetup.gd`: Iterate flat arrays directly
5. Test with 10+ minute session
6. Verify no crashes in Godot console

---

## Appendix: Key Code Locations

| File | Purpose | Issue |
|------|---------|-------|
| [main.py:1143-1150](main.py#L1143-L1150) | FBP dict creation | Nested structure |
| [main.py:994-1001](main.py#L994-L1001) | BoS dict creation | Nested structure |
| [godot_bridge.py:313-317](godot_bridge.py#L313-L317) | FBP atomic update | Can't protect nested arrays |
| [global_script.gd:581-683](global_script.gd#L581-L683) | FBP parsing | Shallow copy issue |
| [boardsetup.gd:485-599](boardsetup.gd#L485-L599) | FBP rendering | Reads from corrupted array |
| [boardsetup.gd:648-803](boardsetup.gd#L648-L803) | BoS rendering | Reads from corrupted array |

