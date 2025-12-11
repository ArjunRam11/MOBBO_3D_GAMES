# MOBBO-Godot Integration Testing Checklist

## Current Status: Testing CoP Visualization (Step 2)

### Testing Order
1. ✅ **Data Reception** - Verify Godot receives JSON packets
2. 🔄 **CoP Visualization** - Test local CoPs and global CoP rendering (CURRENT)
3. ⏳ **BoS Visualization** - Test foot polygon rendering
4. ⏳ **FBP Visualization** - Test body pose joint rendering
5. ⏳ **Board Pose Updates** - Test dynamic board updates

---

## Step 2: CoP Visualization Testing

### Pre-Test Setup

**Python Side Changes:**
- ✅ Added debug logging in `main.py:779-790`
- ✅ Prints every 100 packets with CoP data details

**Godot Side Changes:**
- ✅ Disabled FBP visualization in `BoardSetup.gd:91`
- ✅ Disabled FBP toggle key (F key) in `BoardSetup.gd:99-100`
- ✅ Added CoP debug logging in `BoardSetup.gd:316-319`

### Expected Console Output

**Python Console (every 100 packets):**
```
📤 PYTHON->GODOT CoP Packet #100:
   Local CoPs: 2
   Local[0]: x=0.0234, y=-0.0156, w=35.50
   GCoP: x=0.0189, y=-0.0123, z=0.0000, W=71.00
```

**Godot Console (every 100 frames):**
```
🔍 CoP Update:
  has_local_cops: true (count: 2)
  has_gcop: true (x:0.0189, y:-0.0123, z:0.0000)
```

**GlobalScript Debug (every 100 frames):**
```
DEBUG raw values: x=0.0189, y=-0.0123, z=0.0000
DEBUG network_position: (x, y)
```

### Visual Indicators

**What You Should See in Godot 3D View:**

1. **Global CoP (Red Sphere)**
   - Location: On the reference board (closest board)
   - Color: Red with emission glow
   - Size: 2.5cm radius
   - Height: 6cm above board surface
   - Movement: Follows your weight shifts smoothly

2. **Local CoPs (Black Spheres)**
   - Count: 2 (one per force sensor board)
   - Color: Black/dark gray
   - Size: 2cm radius (scales with weight)
   - Height: 3cm above board surface
   - Movement: Each shows individual sensor CoP

3. **Boards**
   - Reference board: Orange/transparent
   - Other boards: Default material
   - Should be positioned relative to each other

### Testing Steps

#### 1. Start Python Application
```bash
cd E:\Godot_interface\MOBBO_3D_GAMES\MOBBO_3D_GAMES
"C:\Users\Pintu\miniconda3\envs\mpy11\python.exe" main.py
```

**Expected Output:**
```
✅ UDP socket bound to port 8000
🎮 STARTING GODOT BRIDGE - Port 8000
✅ Godot bridge started successfully!
```

#### 2. Start Godot Application
- Open Godot project: `NOARKGames`
- Run scene: `Games/BoardViz/BoardViz.tscn`
- Or press F5

**Expected Initial Output:**
```
✅ UDP socket bound to port 8000 - ready to receive CoP data
✅ GlobalScript connected
✅ GCoP indicator created
✅ FBP Skeleton created
✅ Pre-created 32 FBP joint indicators
```

#### 3. Verify Data Flow

**Check Python Console:**
- Should see: `📤 PYTHON->GODOT CoP Packet #100` every ~1 second
- Verify local CoP count matches your setup (should be 2)
- Verify GCoP values are reasonable (typically 0.01 to 0.5 meters)

**Check Godot Console:**
- Should see: `🔍 CoP Update:` every ~1.6 seconds (at 60 FPS)
- Should see: `DEBUG raw values:` with same values as Python GCoP
- Verify `has_local_cops: true` and `has_gcop: true`

#### 4. Visual Verification

**Stand on Force Sensors:**
1. Stand centered → Red sphere should be near board center
2. Shift weight left → Red sphere moves left
3. Shift weight right → Red sphere moves right
4. Shift weight forward → Red sphere moves in -Z direction
5. Shift weight backward → Red sphere moves in +Z direction

**Check Local CoPs:**
- Two black spheres should be visible (one per board)
- They should move independently based on individual sensor readings
- Spheres should scale slightly larger when more weight is applied

#### 5. Camera Controls
- **Mouse drag**: Rotate view
- **Scroll**: Zoom in/out
- **H key**: Hide/show all visualizations

### Troubleshooting

#### No Spheres Visible

**Check 1: Data Reception**
```gdscript
# In Godot console, verify:
📦 Received JSON packet with keys: [cop, timestamp]
```
If missing, check:
- Python bridge started: Look for "✅ Godot bridge started"
- Port 8000 not blocked by firewall
- Python `godot_bridge.start()` was called

**Check 2: Raw Values**
```gdscript
DEBUG raw values: x=0.0189, y=-0.0123, z=0.0000
```
If all zeros, check:
- Force sensors are sending data
- `handle_cop_data_safe()` is processing correctly
- Look for "⚠️" warnings in console

**Check 3: Visualization Code**
```gdscript
🔍 CoP Update:
  has_local_cops: true (count: 2)
  has_gcop: true
```
If `false`, check:
- `network_manager.local_cops` is populated
- `network_manager.raw_x/y/z` are non-zero

#### Spheres in Wrong Position

**Check Coordinate Transform:**
- Godot uses Y-up, Python uses Z-up
- Transform: `Vector3(x, z, -y)` in `plot_gcop()`
- Verify `POSITION_SCALE = 1.0` in BoardSetup.gd

**Check Board Reference:**
- Red sphere should be on the CLOSEST board (reference board)
- If wrong board, check board pose detection

#### Crash on Startup

**Most Likely Cause: FBP Code**
- Verify line 91 has: `# update_fbp_from_network()`
- Verify line 99-100: FBP key toggle is commented
- Save file and reload Godot

**Check Console for:**
```
ERROR: [output overflow, print less text!]
CrashHandlerException: Program crashed with signal 11
```
If crash persists, check:
- `fbp_joint_indicators` array initialization
- No null indicators being accessed

### Success Criteria

✅ **Pass Criteria:**
1. Python console shows CoP packets being sent
2. Godot console shows CoP data being received
3. Red sphere (GCoP) is visible and moves with weight shifts
4. Black spheres (local CoPs) are visible (2 total)
5. No crash for 5+ minutes of operation
6. Smooth real-time updates (no lag > 100ms)

❌ **Fail Criteria:**
- No spheres visible after 10 seconds
- Spheres frozen (not updating)
- Crash within 5 minutes
- Console spam (> 10 warnings/second)

---

## Next Steps After CoP Works

### Step 3: Enable BoS Visualization
1. Uncomment in `BoardSetup.gd`: Add `update_bos_from_network()` call
2. Implement `plot_bos_polygons()` function
3. Test foot polygon rendering

### Step 4: Enable FBP Visualization
1. Uncomment in `BoardSetup.gd`: `update_fbp_from_network()`
2. Enable F key toggle
3. Test body pose joint rendering

---

## Debug Commands

**Reduce Logging (if too much spam):**

*Python:*
```python
# Change % 100 to % 500 in main.py:779
if self._send_counter % 500 == 0:
```

*Godot:*
```gdscript
# Change % 100 to % 500 in BoardSetup.gd:316
if Engine.get_process_frames() % 500 == 0:
```

**Force Show Indicators (for testing without data):**
```gdscript
# In BoardSetup.gd _ready():
gcop_indicator.visible = true
gcop_indicator.position = Vector3(0, 0.1, 0)
```

---

## Coordinate System Reference

### Python (RealSense Camera)
- X: Right (+) / Left (-)
- Y: Forward (+) / Backward (-)
- Z: Up (+) / Down (-)

### Godot (Y-up)
- X: Right (+) / Left (-)
- Y: Up (+) / Down (-)
- Z: Backward (+) / Forward (-)

### Transform Formula
```gdscript
godot_pos = Vector3(python_x, python_z, -python_y)
```

---

## Performance Metrics

**Target Performance:**
- Python send rate: 50Hz (every 20ms)
- Godot receive rate: 50-60 FPS
- Latency: < 50ms (CoP to visualization)
- CPU usage: < 15% combined

**Monitor:**
```python
# Python side - check godot_bridge.get_status()
print(godot_bridge.get_status())
# Should show: packets_sent increasing, send_rate: 0.02
```

---

## Contact & Support

**Issue Reporting:**
- Include console logs from both Python and Godot
- Include screenshot of 3D view
- Note which step failed

**Known Issues:**
- FBP visualization causes crash (DISABLED in this test)
- Audio driver warnings (WASAPI) - can be ignored
- "no debug info in PE/COFF" - Godot debug symbols missing (benign)
