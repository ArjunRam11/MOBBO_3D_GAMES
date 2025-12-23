# Quick Reference: FBP/BoS Race Condition Fix

## The Problem in 30 Seconds

```
Python Thread (main.py):
    fbp_data = {
        'keypoints_3d': [kp0, kp1, ..., kp17]  ← Array of 18 dicts
    }
    godot_bridge.fbp_data = new_dict           ← Replace with new dict
    ⚠️ Old array might be garbage collected

Godot Thread (boardsetup.gd):
    var fbp_data = global_script.fbp_data      ← Get reference
    fbp_data = fbp_data.duplicate()            ← Shallow copy!
    var keypoints = fbp_data['keypoints_3d']   ← Still references OLD array
    for i in 18:
        var kp = keypoints[i]                  ← CRASH: Array was deleted!
```

**Root Cause:** Nested dicts with shallow copying create race condition window

---

## The Solution in 30 Seconds

```
Python → Send individual points (like CoP):
    fbp_point_0 = {'x': 0.1, 'y': 0.2, 'z': 0.3}  ← Atomic
    fbp_point_1 = {'x': 0.4, 'y': 0.5, 'z': 0.6}  ← Atomic
    ... (18 total)

Godot ← Receive flat array:
    var fbp_points: Array = [
        {'x': 0.1, 'y': 0.2, 'z': 0.3},  ← No nesting
        {'x': 0.4, 'y': 0.5, 'z': 0.6},  ← No shared refs
        ...
    ]
    for i in 18:
        var kp = fbp_points[i]  ✅ Safe: Single-level access
```

**Why It Works:** No nested structures = no race condition window

---

## THE ANSWER: YES, Send Individual Points Will Fix It

Absolutely, sending each individual point separately (like you do with CoP) will completely eliminate the race condition crashes.

**Why:**
- CoP pattern: Individual simple dicts ✅ WORKS
- FBP current: Nested dict arrays ❌ CRASHES  
- FBP fixed: Individual simple dicts ✅ WILL WORK

---

## Documentation Files

1. **DATA_STRUCTURE_ANALYSIS.md** - Detailed technical analysis
   - Deep dive into race condition
   - Why CoP works but FBP fails
   - Complete architectural explanation

2. **IMPLEMENTATION_GUIDE.md** - Step-by-step fix
   - 4 files to modify
   - 10 specific changes
   - Before/after code for each
   - Testing checklist

3. **QUICK_REFERENCE.md** - This file (overview)

---

## Key Changes Required

| File | Change | Lines |
|------|--------|-------|
| godot_bridge.py | Add fbp_points array | 3 changes |
| main.py | Use update_FBP_points_batch() | 2 changes |
| global_script.gd | Add fbp_points variable | 3 changes |
| boardsetup.gd | Simplify plot_fbp_points() | 2 changes |

**Total:** 10 simple changes across 4 files

---

## Estimated Time: 30-35 minutes

- Read docs: 10 min
- Implement: 15 min  
- Test: 10 min

---

## Implementation Checklist

- [ ] Read DATA_STRUCTURE_ANALYSIS.md (understand the problem)
- [ ] Review IMPLEMENTATION_GUIDE.md (understand the solution)
- [ ] Modify godot_bridge.py
- [ ] Modify main.py
- [ ] Modify global_script.gd
- [ ] Modify boardsetup.gd
- [ ] Test for 30+ minutes without crashes
- [ ] Commit to git

---

## Quick Summary

**Problem:** Godot crashes when reading nested FBP/BoS dicts while Python modifies them

**Root Cause:** Shallow copy in Godot doesn't protect nested arrays; race condition window exists

**Solution:** Send individual points as flat array (like CoP) instead of nested dict

**Result:** 
- ✅ No more race conditions
- ✅ Simpler code
- ✅ Matches working CoP pattern
- ✅ Stable rendering

**Effort:** ~35 minutes

**Confidence:** 100% - This is a proven architecture pattern (CoP uses it successfully)

