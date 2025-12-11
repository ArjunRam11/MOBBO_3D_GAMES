# Quick Test: CoP Visualization

## 🚀 Quick Start (2 Steps)

### 1. Start Python (Terminal 1)
```bash
cd E:\Godot_interface\MOBBO_3D_GAMES\MOBBO_3D_GAMES
"C:\Users\Pintu\miniconda3\envs\mpy11\python.exe" main.py
```

### 2. Start Godot (Terminal 2 or Godot Editor)
- Press **F5** in Godot Editor
- Or run: `Games/BoardViz/BoardViz.tscn`

---

## ✅ What You Should See

### Python Console
```
✅ Godot bridge started successfully!
📤 PYTHON->GODOT CoP Packet #100:
   Local CoPs: 2
   GCoP: x=0.0189, y=-0.0123, z=0.0000, W=71.00
```

### Godot Console
```
✅ UDP socket bound to port 8000
🔍 CoP Update:
  has_local_cops: true (count: 2)
  has_gcop: true (x:0.0189, y:-0.0123, z:0.0000)
```

### Godot 3D View
- 🔴 **Red glowing sphere** = Global CoP (moves with your balance)
- ⚫ **2 Black spheres** = Local CoPs (one per sensor board)
- 🟠 **Orange board** = Reference board (closest to camera)

---

## 🧪 Quick Test

1. **Stand centered** → Red sphere at board center
2. **Lean left** → Red sphere moves left
3. **Lean right** → Red sphere moves right
4. **Lean forward** → Red sphere moves forward (toward -Z)

---

## ⚠️ Troubleshooting

| Problem | Solution |
|---------|----------|
| **No spheres visible** | Check Python console for "📤" packets being sent |
| **Godot crash** | Verify FBP is disabled (line 91 commented) |
| **Spheres frozen** | Check Godot console for "⚠️" warnings |
| **Wrong position** | Verify force sensors are on the correct boards |

---

## 🔑 Keyboard Controls

- **H** - Hide/show all visualizations
- **Mouse Drag** - Rotate camera
- **Scroll** - Zoom in/out
- **ESC** - Exit

---

## 📊 Success =
✅ Spheres visible
✅ Real-time movement
✅ No crash for 5+ minutes
✅ Console shows data flow

---

## Next: Enable BoS & FBP
See [TESTING_CHECKLIST.md](TESTING_CHECKLIST.md) for full guide
