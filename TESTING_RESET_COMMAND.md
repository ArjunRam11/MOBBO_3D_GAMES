# Testing Reset Board Command - Step by Step

**Goal**: Verify that the Reset Board command is being sent from Godot and received by Python.

---

## Quick Reference

| Component | What It Does |
|-----------|--------------|
| **Python** | Listens on UDP:9000 for reset commands from Godot |
| **Godot** | Sends reset command via UDP:9000 to Python |
| **UDP:9000** | The communication channel between Godot and Python |

---

## STEP 1: Open a NEW Command Prompt/PowerShell

**Do NOT use VSCode terminal - open a fresh terminal window**

### On Windows:
1. Press `Win + R`
2. Type `cmd` or `powershell`
3. Press Enter

### Or right-click and select "Open PowerShell here"

---

## STEP 2: Navigate to Project Directory

```bash
cd e:\Godot_interface\MOBBO_3D_GAMES\MOBBO_3D_GAMES
```

Verify you're in the right directory by checking if you can see:
- `main.py`
- `godot_bridge.py`
- `BoardSetup.gd`

---

## STEP 3: Start Python

```bash
python main.py
```

**Watch the console output carefully!**

### Expected Output on Startup:

You should see this message appear in the console:

```
✅ SUCCESS: Command receiver listening on UDP port 9000
```

**⚠️ IMPORTANT**: If you don't see this message, something is wrong with the socket initialization.

---

## STEP 4: Start Godot (if not already running)

- Open Godot editor
- Load the BoardSetup scene
- Wait 3-5 seconds for systems to connect

---

## STEP 5: Click Reset Board Button

In the Godot scene:
1. Look at the left sidebar
2. Click the **"Reset Board"** button
3. **Immediately watch the Python console**

### Expected Python Console Output:

You should see these messages appear **immediately after clicking**:

```
📨 Reset board command received from Godot!
🔴 Stopping all threads...
⏳ Waiting 1 second for graceful shutdown...
🟢 Restarting board detection...
✅ Board reset complete!
```

### Expected Godot Console Output:

```
🔄 Resetting board visualization...
📤 Sending reset command to Python: stop_all_threads()
✅ Reset command sent to Python via UDP port 9000
⏳ Waiting for Python to: stop threads (1s) → reinitialize board detection
```

---

## STEP 6: Verify Behavior

After clicking Reset Board, you should observe:

### In Godot:
- ✅ All visualizations disappear (CoP, BoS, FBP disappear)
- ✅ Wait 3-7 seconds
- ✅ Visualizations reappear
- ✅ System resumes normal operation

### In Python Console:
- ✅ See the reset sequence messages
- ✅ See "Board reset complete!"
- ✅ Resume normal processing

---

## Troubleshooting

### Problem 1: Don't see "✅ SUCCESS: Command receiver listening..."

**Solution:**
- Port 9000 might be in use
- Check if another Python instance is running
- Kill it: `netstat -ano | find "9000"` then `taskkill /PID <pid> /F`
- Restart Python

### Problem 2: Click Reset Board but see NOTHING in Python console

**Possible Causes:**
1. Python console isn't connected
2. Godot and Python aren't on same machine
3. UDP:9000 not listening

**Solution:**
- Kill Python: `Ctrl+C`
- Restart: `python main.py`
- Look for: `✅ SUCCESS: Command receiver listening on UDP port 9000`
- If you don't see it, something is blocking port 9000

### Problem 3: Python receives command but visualizations don't reappear

**Solution:**
- Wait longer (up to 10 seconds) for board redetection
- Check that camera is connected
- Check that ArUco boards are visible to camera
- Verify force plates are connected

---

## What's Happening Technically

```
Timeline:
T=0ms:    User clicks "Reset Board" in Godot
T=10ms:   Godot creates JSON command: {"type": "reset_board", "action": "stop_all_threads"}
T=50ms:   Godot sends via UDP socket to 127.0.0.1:9000
T=100ms:  Python receives on UDP:9000
T=100-110ms: Python parses JSON
T=110-120ms: Python validates command
T=120ms:   Python starts reset sequence
          - stop_all_threads() [~1000ms]
          - sleep(1) [1000ms]
          - reset_all_threads() [2000-5000ms]
T=3500-7000ms: Board redetects
T=7000ms:  Godot receives new data
T=7100ms:  Godot renders visualizations
T=7200ms:  ✅ System operational again!

Total time: 3-7 seconds
```

---

## Success Criteria

✅ **System is working correctly if:**

1. **On Python startup**: See `✅ SUCCESS: Command receiver listening on UDP port 9000`
2. **On Reset Board click**: See reset sequence in Python console
3. **Visual**: Godot visualizations disappear and reappear
4. **Recovery**: System returns to normal after 3-7 seconds
5. **No errors**: No error messages in either console

---

## Summary

| Step | Action | Expected Output |
|------|--------|-----------------|
| 1 | Start Python | `✅ SUCCESS: Command receiver listening on UDP port 9000` |
| 2 | Start Godot | Systems connect (may take a few seconds) |
| 3 | Click Reset Board | `📨 Reset board command received from Godot!` |
| 4 | Wait | Visualizations disappear then reappear |
| 5 | Done! | System back to normal |

---

**Good luck!** 🚀

If you see the success messages, the reset command system is working perfectly!
