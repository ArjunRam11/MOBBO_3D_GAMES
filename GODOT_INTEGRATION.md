# Godot Integration Guide

This guide explains how to receive Global Center of Pressure (GCoP) data from MOBBO in your Godot game engine.

## Overview

The MOBBO system now sends real-time GCoP data via UDP to Godot, allowing you to control games using your balance and weight distribution.

## Data Format

**Protocol**: UDP
**Default Port**: 9999
**Data Format**: JSON

```json
{
  "type": "gcop",
  "x": 0.0234,        // X position in meters
  "y": -0.0156,       // Y position in meters
  "z": 0.0000,        // Z position in meters
  "weight": 75.5,     // Total weight in Newtons
  "timestamp": 1234567890.123,
  "num_cops": 2       // Number of CoP sensors active
}
```

## Configuration

### Python Side (MOBBO)

Edit [main.py](main.py) line 351-356:

```python
self.godot_bridge = GodotBridgeHelper(
    gcop_array=gcop1,
    data_lock=data_lock,
    godot_ip="127.0.0.1",  # Change if Godot is on different machine
    godot_port=9999        # Change to match your Godot port
)
```

### Send Rate

Edit [godot_bridge.py](godot_bridge.py) to change update frequency:

```python
# Default: 50Hz (0.02 seconds)
bridge = GodotBridge(send_rate=0.02)

# For 30Hz: send_rate=0.033
# For 60Hz: send_rate=0.016
```

## Godot Setup

### 1. Create UDP Receiver Script (GDScript)

Create a new script in Godot called `MobboReceiver.gd`:

```gdscript
extends Node

# UDP Configuration
var udp_port = 9999
var udp_server = PacketPeerUDP.new()

# CoP Data
var gcop_position = Vector3.ZERO
var gcop_weight = 0.0
var is_receiving = false

# Signals for game logic
signal cop_updated(position, weight)
signal weight_threshold_crossed(weight)

# Smoothing
var smoothing_enabled = true
var smooth_factor = 0.3  # Lower = smoother but more lag

func _ready():
	# Bind to UDP port
	var result = udp_server.bind(udp_port)
	if result == OK:
		print("✅ MOBBO Receiver started on port ", udp_port)
		is_receiving = true
	else:
		print("❌ Failed to bind to port ", udp_port)
		is_receiving = false

func _process(_delta):
	if not is_receiving:
		return

	# Check for incoming packets
	if udp_server.get_available_packet_count() > 0:
		var packet = udp_server.get_packet()
		var json_string = packet.get_string_from_utf8()

		# Parse JSON
		var json = JSON.new()
		var error = json.parse(json_string)

		if error == OK:
			var data = json.get_data()
			_process_cop_data(data)
		else:
			print("JSON Parse Error: ", json.get_error_message())

func _process_cop_data(data):
	"""Process received CoP data"""
	var new_position = Vector3(
		data.get("x", 0.0),
		data.get("z", 0.0),  # Godot Y-up coordinate system
		-data.get("y", 0.0)  # Flip Y to Z
	)

	var new_weight = data.get("weight", 0.0)

	# Apply smoothing
	if smoothing_enabled:
		gcop_position = gcop_position.lerp(new_position, smooth_factor)
	else:
		gcop_position = new_position

	gcop_weight = new_weight

	# Emit signals
	emit_signal("cop_updated", gcop_position, gcop_weight)

	# Weight threshold detection
	if gcop_weight > 50.0:  # Adjust threshold as needed
		emit_signal("weight_threshold_crossed", gcop_weight)

func get_cop_position() -> Vector3:
	"""Get current GCoP position"""
	return gcop_position

func get_cop_weight() -> float:
	"""Get current weight on sensors"""
	return gcop_weight

func _exit_tree():
	"""Cleanup on exit"""
	udp_server.close()
	print("MOBBO Receiver stopped")
```

### 2. Example: Control Player Movement

Create a player controller script:

```gdscript
extends CharacterBody3D

@onready var mobbo = get_node("/root/MobboReceiver")

# Movement settings
@export var speed_multiplier = 5.0
@export var max_speed = 10.0

func _ready():
	# Connect to CoP signals
	mobbo.connect("cop_updated", _on_cop_updated)

func _on_cop_updated(cop_position: Vector3, weight: float):
	"""Move player based on CoP position"""
	if weight > 20.0:  # Only move if sufficient weight
		# Scale CoP position to game movement
		var movement = Vector3(
			cop_position.x * speed_multiplier,
			0.0,
			cop_position.z * speed_multiplier
		)

		# Clamp to max speed
		movement = movement.limit_length(max_speed)

		# Apply movement
		velocity = movement
		move_and_slide()

func _physics_process(_delta):
	# Your existing physics code here
	pass
```

### 3. Example: Balance Game

```gdscript
extends Node3D

@onready var mobbo = get_node("/root/MobboReceiver")
@onready var balance_indicator = $BalanceIndicator

var is_balanced = false
var balance_threshold = 0.05  # 5cm tolerance

func _ready():
	mobbo.connect("cop_updated", _on_cop_updated)

func _on_cop_updated(cop_position: Vector3, weight: float):
	"""Check if player is balanced"""

	# Update visual indicator
	balance_indicator.position = cop_position * 10.0  # Scale for visibility

	# Check balance (close to center)
	var distance_from_center = cop_position.length()
	is_balanced = distance_from_center < balance_threshold and weight > 30.0

	# Change indicator color
	if is_balanced:
		balance_indicator.modulate = Color.GREEN
	else:
		balance_indicator.modulate = Color.RED

	# Game logic
	if is_balanced:
		print("🎯 Perfect balance! Score++")
```

## Testing

### 1. Test Python Side

Run the test receiver to verify UDP is working:

```bash
python test_godot_bridge.py
```

Then start your MOBBO application. You should see CoP data being received.

### 2. Test Godot Side

1. Add `MobboReceiver.gd` as an AutoLoad singleton in Godot:
   - Project → Project Settings → AutoLoad
   - Add the script with name `MobboReceiver`

2. Create a simple test scene with a label to display data:

```gdscript
extends Label

@onready var mobbo = get_node("/root/MobboReceiver")

func _ready():
	mobbo.connect("cop_updated", _on_cop_updated)

func _on_cop_updated(cop_position: Vector3, weight: float):
	text = "CoP: %.3f, %.3f, %.3f\nWeight: %.1f N" % [
		cop_position.x, cop_position.y, cop_position.z, weight
	]
```

3. Run the scene - you should see live CoP data when MOBBO is running

## Coordinate System

**MOBBO** uses:
- X: Left/Right (positive = right)
- Y: Forward/Backward (positive = forward)
- Z: Up/Down (usually 0)

**Godot** (Y-up):
- X: Left/Right
- Y: Up/Down
- Z: Forward/Backward

The example scripts handle the coordinate conversion automatically.

## Troubleshooting

### No data received in Godot

1. **Check firewall**: Allow UDP port 9999
2. **Check IP address**: If Godot is on a different machine, update `godot_ip` in main.py
3. **Check port**: Ensure both sides use the same port
4. **Test with test_godot_bridge.py**: Verify Python side is sending

### Data is choppy/laggy

1. Reduce smoothing factor in Godot (lower = less smooth but more responsive)
2. Increase send rate in `godot_bridge.py` (lower value = faster)
3. Check network latency if using different machines

### Connection lost

The UDP protocol is connectionless, so there's no "connection" to lose. If data stops:
1. Check if MOBBO threads are still running
2. Verify force sensor boards are sending data
3. Check system resources (CPU/memory)

## Game Ideas

### Balance Games
- **Tightrope Walker**: Keep CoP centered while crossing obstacles
- **Stacking Game**: Balance while stacking virtual blocks
- **Surfing Simulator**: Use weight shifts to control a surfboard

### Rehabilitation Games
- **Target Practice**: Shift weight to move cursor and hit targets
- **Path Following**: Follow a path by controlling CoP
- **Balance Training**: Progressive difficulty balance challenges

### Action Games
- **Character Control**: Direct character movement with weight shifts
- **Vehicle Control**: Steer vehicles using balance
- **Sports Games**: Golf putting, bowling using CoP control

## Performance

- **Update Rate**: ~50Hz (20ms intervals)
- **Latency**: < 50ms typical
- **CPU Impact**: Minimal (~1% on modern hardware)
- **Network**: ~100 bytes/packet, ~5KB/s bandwidth

## Advanced Features

### Custom Data Processing

You can modify [godot_bridge.py](godot_bridge.py) to send additional data:

```python
def _get_gcop_data(self) -> Optional[dict]:
    return {
        "type": "gcop",
        "x": float(self.gcop_array[0]),
        "y": float(self.gcop_array[1]),
        "z": float(self.gcop_array[2]),
        "weight": float(self.total_weight),
        # Add custom data
        "custom_value": your_custom_calculation(),
        "game_state": "playing"
    }
```

### Multiple Godot Instances

To send data to multiple Godot instances:

```python
# Create multiple bridges
bridge1 = GodotBridge(godot_ip="192.168.1.10", godot_port=9999)
bridge2 = GodotBridge(godot_ip="192.168.1.11", godot_port=9999)

bridge1.start()
bridge2.start()
```

## Support

For issues or questions:
- Check logs in Python console
- Enable debug logging: Set `logging.basicConfig(level=logging.DEBUG)`
- Review force sensor data to ensure it's valid
- Test with `test_godot_bridge.py` first
