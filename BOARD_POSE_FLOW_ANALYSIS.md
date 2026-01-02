# Board Pose Data Flow Analysis

## WHERE BOARD POSE IS SENT

### 1. **INITIAL SETUP** (First time when Godot starts)
```
BOSEstimator.__init__()
  ↓
__init__ calls board_pose_detected_set(self.frame)  [Line 589 in reset_all_threads context]
  ↓
board_pose_detected_set() [Lines 674-869]
  - Detects boards from frame
  - Calls godot_bridge.update_Boardpose_data(board_xyz_data) at LINE 851
    ↓
    update_Boardpose_data() [Lines 320-354 in godot_bridge.py]
      - Sets send_board_pose_next = True
      - Sets board_pose_sent = True
      - Data stored in self.board_pose_data
    ↓
_get_general_data() [Lines 240-256 in godot_bridge.py]
  - Checks if send_board_pose_next == True
  - Includes board_pose in UDP packet to Godot
  - Sets send_board_pose_next = False after sending
  ↓
Godot receives board_pose ✅
```

---

### 2. **CONTINUOUS UPDATES** (During normal operation)
```
run_aruco() thread [Main processing loop]
  ↓
Every frame: checks board configuration at LINE 1205-1206
  - Calls godot_bridge.update_Boardpose_data(current_board_data)
  ↓
If board configuration changed:
  - update_Boardpose_data() sets send_board_pose_next = True
  ↓
_get_general_data() sends updated board data
  ↓
Godot receives board_pose ✅
```

---

### 3. **AFTER RESET BUTTON PRESSED** (Problem area)
```
Godot sends reset command via UDP
  ↓
main.py command receiver [Lines 920-945]
  - Parses reset command
  - Calls stop_all_threads() at LINE 930
  - Calls reset_all_threads() at LINE 935
    ↓
    reset_all_threads() [Lines 563-650]
      - Resets flags to True
      - Resets board_pose_sent = False at LINE 576
      - Resets previous_board_pose_hash = None at LINE 577
      - Calls board_pose_detected_set(self.frame) at LINE 589
        ↓
        board_pose_detected_set(self.frame) [Lines 674-869]
          - Line 680-683: If self.frame is None, RETURNS EARLY ❌
          - Line 685-686: frame1 = frame (expects numpy array, gets Frame_Process object)
          - Line 686: prints "Unknown" for shape (Frame_Process has no .shape)
          - Line 688: self.board_pose.board_pose(frame1) - attempts detection
          - Line 691-694: If no boards detected, RETURNS EARLY ❌
          - Line 851: IF boards found, calls godot_bridge.update_Boardpose_data()
        ↓
      - Restarts BOS thread
      - Restarts ArUco thread
  ↓
Godot receives... ??? (user reports NO board_pose in packets) ❌
```

---

## CRITICAL ISSUES FOUND

### Issue 1: Frame Type Mismatch
- **Location**: reset_all_threads() Line 589
- **Problem**: Passes `self.frame` (a Frame_Process OBJECT) to board_pose_detected_set()
- **Expected**: Should pass a numpy array (color frame)
- **Current Code**:
  ```python
  print("🔄 RESET: Calling board_pose_detected_set()...")
  self.board_pose_detected_set(self.frame)  # ← self.frame is Frame_Process object!
  ```
- **Fix**: Should extract actual numpy frame from Frame_Process:
  ```python
  color_frame, depth_frame = self.frame.get_Frames()
  self.board_pose_detected_set(color_frame)
  ```

### Issue 2: board_pose_detected_set() Expects Numpy Array
- **Location**: board_pose_detected_set() Line 685-688
- **Problem**: Function checks `frame1.shape` and passes to board_pose.board_pose()
- **Evidence**: Line 686 output would show "Unknown" (Frame_Process has no shape attribute)
- **Result**: Board detection fails silently, no boards detected, function returns early

### Issue 3: reset_all_threads() Called From Command Handler
- **Status**: ✅ CONFIRMED working (user saw "LED glow" = Python responding)
- **But**: Board pose_detected_set() logging never appears in console
- **Why**: Likely returns early due to frame issues before reaching line 851

---

## DATA FLOW COMPARISON

### Initial Setup (WORKS) ✅
1. BOSEstimator.__init__() receives Frame_Process object as `frame` parameter
2. Immediately calls board_pose_detected_set()
3. Board detection succeeds
4. Board data sent to Godot
5. Visualization renders

### Reset (BROKEN) ❌
1. reset_all_threads() calls board_pose_detected_set(self.frame)
2. board_pose_detected_set() receives Frame_Process object
3. Attempts to detect boards from Frame_Process object (wrong type)
4. Board detection returns empty or fails
5. No board data sent to Godot
6. Visualization stays hidden

---

## WHERE SELF.FRAME IS SET

- **Location**: BOSEstimator.__init__() Line 430
- **Code**: `self.frame = frame`
- **Type**: `frame` is a Frame_Process object (imported from Frame_Process.py)
- **Correct Method to Get Numpy Frames**: `self.frame.get_Frames()` returns `(color_frame, depth_frame)`

---

## RECOMMENDED FIX

**In reset_all_threads() around Line 589:**

Replace:
```python
print("🔄 RESET: Calling board_pose_detected_set()...")
self.board_pose_detected_set(self.frame)
print("🔄 RESET: board_pose_detected_set() returned")
```

With:
```python
print("🔄 RESET: Calling board_pose_detected_set()...")
# CRITICAL: Extract actual numpy frame from Frame_Process object
color_frame, depth_frame = self.frame.get_Frames()
if color_frame is not None:
    print(f"🔄 RESET: Got frame from Frame_Process, shape: {color_frame.shape}")
    self.board_pose_detected_set(color_frame)
else:
    print("❌ CRITICAL: Could not get color frame from Frame_Process during reset!")
print("🔄 RESET: board_pose_detected_set() returned")
```

This ensures board_pose_detected_set() receives a valid numpy array instead of a Frame_Process object.
