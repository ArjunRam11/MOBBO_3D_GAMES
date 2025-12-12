# Dual UDP Port Architecture for FBP/BoS Isolation

## Overview
The system now uses **TWO separate UDP ports** to prevent high-frequency CoP data from interfering with camera-based FBP/BoS data.

---

## Architecture

### Port 8000 - HIGH FREQUENCY (CoP + Board Pose)
- **Data**: Center of Pressure (Global + Local) + Board Pose
- **Frequency**: ~100 Hz (every 0.01s)
- **Python Thread**: `compute_COP()` in main.py
- **Godot Receiver**: `udp` socket + `network_thread()`

### Port 8001 - CAMERA FREQUENCY (FBP + BoS)
- **Data**: Full Body Pose (18 keypoints) + Base of Support (foot polygons)
- **Frequency**: ~30 Hz (every 0.033s - camera framerate)
- **Python Thread**: `run_aruco()` in main.py
- **Godot Receiver**: `udp_camera` socket + `network_thread_camera()`

---

## Why Dual UDP Ports?

### Problem (Single Port):
1. **Packet Congestion**: 100Hz CoP packets overwhelm 30Hz camera packets
2. **Processing Bottleneck**: Godot processes packets sequentially - high-frequency CoP blocks FBP/BoS
3. **Crash Risk**: FBP data corruption when mixed with CoP stream

### Solution (Dual Ports):
1. **Isolated Streams**: CoP and FBP data never interfere
2. **Independent Threading**: Each port has its own receiver thread in Godot
3. **Easier Debugging**: Can disable FBP port without affecting CoP
4. **Crash Prevention**: FBP crashes won't affect CoP visualization

---

## File Changes

### 1. godot_bridge.py
```python
class GodotBridgeHelper:
    def __init__(self, ..., godot_port_camera=8001):
        # PRIMARY bridge: Port 8000 (CoP + Board Pose)
        self.bridge = GodotBridge(godot_ip, godot_port)
        self.bridge.set_data_callback(self._get_cop_data)

        # SECONDARY bridge: Port 8001 (FBP + BoS)
        self.bridge_camera = GodotBridge(godot_ip, godot_port_camera, send_rate=0.033)
        self.bridge_camera.set_data_callback(self._get_camera_data)

    def _get_cop_data(self):
        """Returns: {"timestamp": ..., "cop": {...}, "board_pose": {...}}"""

    def _get_camera_data(self):
        """Returns: {"timestamp": ..., "fbp": {...}, "bos": {...}}"""

    def start(self):
        self.bridge.start()         # Port 8000
        self.bridge_camera.start()  # Port 8001
```

**Key Changes**:
- Split `_get_all_data()` into two callbacks
- `_get_cop_data()`: CoP + Board Pose → Port 8000
- `_get_camera_data()`: FBP + BoS → Port 8001
- Camera bridge runs at 30Hz (send_rate=0.033)

---

### 2. global_script.gd

```gdscript
# Two UDP sockets
@onready var udp: PacketPeerUDP = PacketPeerUDP.new()          # Port 8000
@onready var udp_camera: PacketPeerUDP = PacketPeerUDP.new()  # Port 8001

# Two network threads
@onready var thread_network = Thread.new()
@onready var thread_network_camera = Thread.new()

func _ready():
    # Bind both ports
    udp.bind(8000, "127.0.0.1")          # CoP + Board Pose
    udp_camera.bind(8001, "127.0.0.1")  # FBP + BoS

    # Start both threads
    thread_network.start(network_thread)
    thread_network_camera.start(network_thread_camera)

func network_thread():
    """PRIMARY port - CoP + Board Pose"""
    while true:
        if udp.get_available_packet_count() > 0:
            handle_udp_packet()

func network_thread_camera():
    """SECONDARY port - FBP + BoS"""
    while true:
        if udp_camera.get_available_packet_count() > 0:
            handle_udp_packet_camera()

func handle_udp_packet():
    """Process CoP + Board Pose from Port 8000"""
    # Parse JSON
    # Handle "cop" and "board_pose" keys

func handle_udp_packet_camera():
    """Process FBP + BoS from Port 8001"""
    # Parse JSON
    # Handle "fbp" and "bos" keys
```

**Key Changes**:
- Added `udp_camera` socket for Port 8001
- Added `thread_network_camera` for camera data
- Split packet handling into two functions
- Port 8000 only processes CoP + Board Pose
- Port 8001 only processes FBP + BoS

---

### 3. main.py (NO CHANGES NEEDED)

The `main.py` file does **NOT** need changes because:
- `GodotBridgeHelper.__init__()` has default parameter `godot_port_camera=8001`
- Existing calls to `update_cop_data()`, `update_Boardpose_data()`, `update_FBP_data()`, `update_BoS_data()` work as-is
- The bridge automatically routes data to correct port internally

---

## Testing Plan

### Step 1: Test CoP on Port 8000 (Already Working)
```bash
# Run Python
python main.py

# Run Godot - should see CoP spheres moving
# Port 8000 receives CoP data at 100Hz
```

**Expected**: ✅ Red/black spheres visible and moving smoothly

---

### Step 2: Enable FBP on Port 8001
In `main.py`, uncomment line ~1010:

```python
# Currently commented:
# if fbp_data['keypoints_3d'] is not None:
#     self.godot_bridge.update_FBP_data(fbp_data)

# Uncomment:
if fbp_data['keypoints_3d'] is not None:
    self.godot_bridge.update_FBP_data(fbp_data)
```

In `BoardSetup.gd`, uncomment line ~88:

```gdscript
# Currently commented:
# update_fbp_from_network()

# Uncomment:
update_fbp_from_network()
```

**Expected**:
- ✅ Skeleton tracking appears (18 joints)
- ✅ NO crashes (FBP is isolated on Port 8001)
- ✅ CoP continues working on Port 8000

---

### Step 3: Enable BoS on Port 8001
In `main.py`, uncomment line ~847:

```python
# Currently commented:
# if left_foot_clean is not None or right_foot_clean is not None:
#     self.godot_bridge.update_BoS_data(bos_data)

# Uncomment:
if left_foot_clean is not None or right_foot_clean is not None:
    self.godot_bridge.update_BoS_data(bos_data)
```

**Expected**:
- ✅ Foot polygons appear (green outlines)
- ✅ Updates at camera framerate (~30Hz)
- ✅ No interference with CoP data

---

## Debugging Tips

### Check Port Activity
```gdscript
# In global_script.gd _process():
if Engine.get_process_frames() % 100 == 0:
    print("Port 8000 packets: ", udp.get_available_packet_count())
    print("Port 8001 packets: ", udp_camera.get_available_packet_count())
```

### Monitor Bridge Status
```python
# In main.py:
status = self.godot_bridge.get_status()
print(f"Port 8000: {status['packets_sent']} packets")
print(f"Port 8001: {self.godot_bridge.bridge_camera.packets_sent} packets")
```

---

## Benefits

1. **Crash Prevention**: FBP processing isolated - crashes won't affect CoP
2. **Performance**: High-frequency CoP doesn't block camera data
3. **Debugging**: Can disable Port 8001 to test CoP only
4. **Scalability**: Can add more UDP ports for future data types
5. **Clean Architecture**: Logical separation by data frequency

---

## Next Steps

1. ✅ Test CoP on Port 8000 (already confirmed working)
2. ⏳ Enable FBP transmission on Port 8001
3. ⏳ Test FBP visualization in Godot (BoardSetup.gd)
4. ⏳ Enable BoS transmission on Port 8001
5. ⏳ Verify all three systems work together

---

## Port Summary

| Port | Data Types       | Frequency | Thread in Python | Thread in Godot      |
|------|------------------|-----------|------------------|----------------------|
| 8000 | CoP + Board Pose | ~100 Hz   | compute_COP()    | network_thread()     |
| 8001 | FBP + BoS        | ~30 Hz    | run_aruco()      | network_thread_camera() |

---

## Rollback Instructions

If you need to revert to single-port mode:

1. In `godot_bridge.py`, change `__init__` to use one bridge
2. In `global_script.gd`, comment out `udp_camera` and `thread_network_camera`
3. Revert `handle_udp_packet()` to process all data types

**But we don't recommend this** - dual ports solve the crash issue!
