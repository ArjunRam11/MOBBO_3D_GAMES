# CoP Visualization Debug Output Guide

## What You'll See Now

### 1. Global Script (Python Data Reception)
Every ~1.6 seconds, you'll see:

```
=== CENTER OF PRESSURE (CoP) VALUES ===
  Global CoP (raw): X=-0.1550  Y=-0.1207  Z=-0.0000
  Local CoPs: 2 sensors
    Sensor[0]: X=0.0234  Y=-0.0156  Weight=35.50
    Sensor[1]: X=0.0144  Y=-0.0211  Weight=35.50
=====================================
```

**✅ What This Means:**
- Python data IS being received by Godot
- X, Y, Z are the raw CoP coordinates from Python
- Weight values show force sensor readings

**⚠️ What to Watch For:**
- If values are FROZEN (not changing), step on/off the force plates
- If all zeros, Python isn't sending data

---

### 2. BoardSetup (Visualization Status)
Every ~1.6 seconds, you'll see:

```
🎯 === BOARDSETUP VISUALIZATION STATUS ===
📊 Data Status:
  • Local CoPs: ✅ YES (count: 2)
  • Global CoP: ✅ YES (raw: X=-0.1550 Y=-0.1207 Z=-0.0000)

🔴 Global CoP Sphere:
  • Exists: ✅ YES
  • Visible: ✅ YES
  • Position: (X=-0.155, Y=0.060, Z=0.121)
  • Scale: (1, 1, 1)

⚫ Local CoP Spheres:
  • Total indicators: 2
  • Sphere[0]: Visible=✅ Pos=(X=0.023, Y=0.030, Z=0.016)
  • Sphere[1]: Visible=✅ Pos=(X=0.014, Y=0.030, Z=0.021)
==========================================
```

**✅ What This Means:**
- `Exists: ✅ YES` - The sphere object was created
- `Visible: ✅ YES` - The sphere is set to be visible
- `Position: (X, Y, Z)` - Where the sphere is in 3D space
- Y=0.060 - Sphere is 6cm above board surface (correct height)

**⚠️ What to Watch For:**
- If `Visible: ❌ NO` - Spheres exist but aren't visible (data validation issue)
- If `Position` values are HUGE (>5.0) - Coordinate system error
- If `Visible: ✅ YES` but you can't see spheres - Camera angle issue

---

## Troubleshooting

### Issue: "Values are FROZEN (not changing)"

**Cause:** No one is standing on force plates, or Python isn't updating

**Fix:**
1. Step ON the force plates
2. Shift your weight left/right/forward/backward
3. Check Python console for "📤 PYTHON->GODOT CoP Packet" messages

---

### Issue: "Spheres are Visible=✅ but I don't see them"

**Cause:** Camera isn't looking at the right area

**Fix:**
1. Use **mouse drag** to rotate the camera view
2. Use **scroll wheel** to zoom out
3. Look for the orange reference board (closest board)
4. The red sphere should be ON or NEAR that board
5. Check the Position values - if X, Y, Z are all small (<0.5), the spheres are near the origin

**Camera Tips:**
- The reference board is the closest board to the camera
- Spheres positions are RELATIVE to the reference board
- If Position shows X=-0.155, Z=0.121, the sphere is:
  - 15.5cm to the LEFT (negative X)
  - 12.1cm FORWARD (positive Z in Godot = forward)

---

### Issue: "Visible=❌ NO even though data exists"

**Cause:** Data validation is rejecting the values

**Check:**
1. Look at the raw values: X, Y, Z
2. If any value is NaN or Inf, Python data is corrupt
3. If Z=0.0000 constantly, depth data might be missing
4. If X, Y, Z are all > 5.0, coordinate transform is wrong

**Common Causes:**
- Z=0 suggests the force plates aren't providing depth data (this is NORMAL for 2D CoP)
- Large values (>5.0) mean wrong coordinate scaling

---

## Expected Behavior

### When Standing Still
- Values should be RELATIVELY stable (small jitter is normal)
- Red sphere (GCoP) should be visible at board center
- Black spheres (local CoPs) should be visible on each board

### When Shifting Weight
- **Lean LEFT** → X becomes more negative (sphere moves left)
- **Lean RIGHT** → X becomes more positive (sphere moves right)
- **Lean FORWARD** → Z becomes more positive (sphere moves toward camera)
- **Lean BACKWARD** → Z becomes more negative (sphere moves away from camera)

### Real-Time Updates
- Sphere positions should update smoothly every frame
- No lag > 100ms
- Smooth movement when shifting weight

---

## Success Criteria

✅ **Working Correctly:**
1. Global Script prints CoP values every 1.6 seconds
2. Values CHANGE when you shift your weight
3. BoardSetup shows "Visible: ✅ YES" for all spheres
4. You can SEE the red and black spheres in 3D view
5. Spheres MOVE when you shift weight
6. Position values are reasonable (< 1.0 typically)

❌ **Not Working:**
1. No console output (data not flowing)
2. Values are frozen (no updates)
3. Visible: ❌ NO (validation rejecting data)
4. Can't see spheres despite Visible: ✅ YES (camera issue)

---

## Next Steps

1. **Run Godot** with these changes
2. **Stand on force plates**
3. **Check console output** for both sections above
4. **Report back** with:
   - Are values changing?
   - Is Visible: ✅ YES or ❌ NO?
   - Can you see the spheres in 3D view?
   - Include a screenshot of the Godot 3D view

This will help diagnose exactly where the issue is!
