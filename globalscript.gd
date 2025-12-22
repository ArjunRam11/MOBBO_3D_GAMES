extends Node

# ============================================================
# MOBBO Global Network Manager for real-time data reception
# Receives CoP, Board Pose, FBP, and BoS data from Python
# ============================================================

# Session and debug variables
var session_id: int = 1
var current_date: String = ""
var trial_counts: Dictionary = {}

# ============================================================
# DATA STORAGE - Updated from Python via UDP
# ============================================================
# Board Pose data structure: {reference_id: int, boards: {id: {relative_rotation_matrix, relative_translation}}}
var board_pose_data: Dictionary = {}

# Center of Pressure data
var local_cops: Array = []  # Array of {x, y, z, weight}
var raw_x: float = 0.0
var raw_y: float = 0.0
var raw_z: float = 0.0

# Base of Support data: {left_foot: [...], right_foot: [...]}
var bos_data: Dictionary = {}

# Full Body Pose data: {keypoints_3d: [...], angles: [...]}
var fbp_data: Dictionary = {}

# ============================================================
# UDP CONFIGURATION - Dual UDP ports from godot_bridge.py
# ============================================================
# RECEIVING from Python:
# Port 8000: CoP (Center of Pressure) + Board Pose (high frequency)
# Port 8001: FBP (Full Body Pose) + BoS (Base of Support) (camera frequency)
#
# SENDING to Python:
# Port 9000: Command socket for reset board commands (created on-demand)
@onready var udp_cop: PacketPeerUDP = PacketPeerUDP.new()
@onready var udp_camera: PacketPeerUDP = PacketPeerUDP.new()

# Network threads
@onready var thread_udp_cop = Thread.new()
@onready var thread_udp_camera = Thread.new()

# Connection state
var connected: bool = false
var disconnected: bool = false

# Game scaling
var X_SCREEN_OFFSET: int
var Y_SCREEN_OFFSET: int
var Y_SCREEN_OFFSET3D: int

@export var PLAYER_POS_SCALER_X: int = 20 * 100
@export var PLAYER_POS_SCALER_Z: int = 20 * 100
@export var PLAYER3D_POS_SCALER_Y: int = 30 * 100

# Derived positions
var network_position: Vector2 = Vector2.ZERO
var network_position3D: Vector2 = Vector2.ZERO
var workspace: Vector2 = Vector2.ZERO

var scaled_network_position: Vector2 = Vector2.ZERO
var scaled_network_position3D: Vector2 = Vector2.ZERO

# Debug/control
@export var debug: bool = false
var endgame: bool = false

# Screen size
var screen_size = DisplayServer.screen_get_size()


# ============================================================
# INITIALIZATION
# ============================================================
func _ready():
	current_date = get_date_string()
	load_session_info()

	# Bind UDP socket to port 8000 (CoP + Board Pose)
	var result_cop = udp_cop.bind(8000, "127.0.0.1")
	if result_cop == OK:
		print("✅ UDP port 8000 bound - receiving CoP + Board Pose")
	else:
		print("❌ Failed to bind UDP port 8000: %d" % result_cop)

	# Bind UDP socket to port 8001 (FBP + BoS)
	var result_camera = udp_camera.bind(8001, "127.0.0.1")
	if result_camera == OK:
		print("✅ UDP port 8001 bound - receiving FBP + BoS")
	else:
		print("❌ Failed to bind UDP port 8001: %d" % result_camera)

	# Calculate screen offsets
	X_SCREEN_OFFSET = int(screen_size.x / 4)
	Y_SCREEN_OFFSET = int(screen_size.y / 4)
	Y_SCREEN_OFFSET3D = int(screen_size.y / 1.75)

	# Start network threads
	thread_udp_cop.start(_thread_udp_cop)
	thread_udp_camera.start(_thread_udp_camera)

	print("🎮 GlobalScript initialized - ready to receive MOBBO data")




# ============================================================
# UDP NETWORK THREADS
# ============================================================
func _thread_udp_cop():
	"""Thread for receiving CoP + Board Pose data on port 8000"""
	while not endgame:
		if udp_cop.get_available_packet_count() > 0:
			_handle_cop_packet()
		OS.delay_msec(1)


func _thread_udp_camera():
	"""Thread for receiving FBP + BoS data on port 8001"""
	while not endgame:
		if udp_camera.get_available_packet_count() > 0:
			_handle_camera_packet()
		OS.delay_msec(1)


# ============================================================
# PACKET HANDLERS
# ============================================================
func _handle_cop_packet():
	"""Handle CoP and Board Pose data from port 8000"""
	var packet = udp_cop.get_packet()
	if packet == null or packet.is_empty():
		return

	var packet_string = packet.get_string_from_utf8()
	if packet_string == null or packet_string.is_empty():
		return

	# Parse JSON
	var json_data = JSON.parse_string(packet_string)
	if json_data == null or typeof(json_data) != TYPE_DICTIONARY:
		return

	# Process CoP data if present
	if json_data.has("cop"):
		_process_cop_data(json_data["cop"])

	# Process Board Pose data if present
	if json_data.has("board_pose"):
		_process_board_pose_data(json_data["board_pose"])


func _handle_camera_packet():
	"""Handle FBP and BoS data from port 8001"""
	var packet = udp_camera.get_packet()
	if packet == null or packet.is_empty():
		return

	var packet_string = packet.get_string_from_utf8()
	if packet_string == null or packet_string.is_empty():
		return

	# Parse JSON
	var json_data = JSON.parse_string(packet_string)
	if json_data == null or typeof(json_data) != TYPE_DICTIONARY:
		return

	# Process BoS data if present
	if json_data.has("bos"):
		_process_bos_data(json_data["bos"])

	# Process FBP data if present
	if json_data.has("fbp"):
		_process_fbp_data(json_data["fbp"])


# ============================================================
# DATA PROCESSORS
# ============================================================
func _process_cop_data(cop_data: Variant):
	"""Process Center of Pressure data - both local and global"""
	if typeof(cop_data) != TYPE_DICTIONARY:
		return

	# Process local CoPs (individual sensors)
	if cop_data.has("local_cops") and typeof(cop_data["local_cops"]) == TYPE_ARRAY:
		local_cops.clear()
		for local_cop in cop_data["local_cops"]:
			if typeof(local_cop) == TYPE_DICTIONARY:
				local_cops.append(local_cop)

	# Process global CoP (combined)
	if cop_data.has("gcop") and typeof(cop_data["gcop"]) == TYPE_DICTIONARY:
		var gcop = cop_data["gcop"]

		if gcop.has("x") and gcop.has("y") and gcop.has("z"):
			raw_x = float(gcop.get("x", 0.0))
			raw_y = float(gcop.get("y", 0.0))
			raw_z = float(gcop.get("z", 0.0))

			# Validate values are finite
			if is_finite(raw_x) and is_finite(raw_y) and is_finite(raw_z):
				# Update network positions
				var net_x = raw_x * PLAYER_POS_SCALER_X + X_SCREEN_OFFSET
				var net_y = raw_y * PLAYER3D_POS_SCALER_Y + Y_SCREEN_OFFSET3D
				var net_z = raw_z * PLAYER_POS_SCALER_Z + Y_SCREEN_OFFSET

				network_position = Vector2(net_x, net_z)
				network_position3D = Vector2(net_x, net_y)
				workspace = Vector2(net_x, net_y)

				# Update scaled positions (with global scalars if available)
				var scalar_x = 1.0
				var scalar_y = 1.0
				if has_node("/root/GlobalSignals"):
					var signals = get_node("/root/GlobalSignals")
					if signals.has_meta("global_scalar_x"):
						scalar_x = signals.get_meta("global_scalar_x")
					if signals.has_meta("global_scalar_y"):
						scalar_y = signals.get_meta("global_scalar_y")

				scaled_network_position = Vector2(
					raw_x * PLAYER_POS_SCALER_X * scalar_x + X_SCREEN_OFFSET,
					raw_z * PLAYER_POS_SCALER_Z * scalar_y + Y_SCREEN_OFFSET
				)
				scaled_network_position3D = Vector2(
					raw_x * PLAYER_POS_SCALER_X * scalar_x + X_SCREEN_OFFSET,
					raw_y * PLAYER3D_POS_SCALER_Y * scalar_y + Y_SCREEN_OFFSET3D
				)

				connected = true


func _process_board_pose_data(board_pose: Variant):
	"""Process board pose data"""
	if typeof(board_pose) != TYPE_DICTIONARY:
		return

	# Extract data wrapper
	if board_pose.has("data") and typeof(board_pose["data"]) == TYPE_DICTIONARY:
		board_pose_data = board_pose["data"]
		if board_pose_data.has("reference_id"):
			print("📍 Board Pose Updated - Reference ID: %d" % int(board_pose_data.get("reference_id")))


func _process_bos_data(bos: Variant):
	"""Process Base of Support data"""
	if typeof(bos) != TYPE_DICTIONARY:
		return

	# Extract data wrapper
	if bos.has("data") and typeof(bos["data"]) == TYPE_DICTIONARY:
		bos_data = bos["data"]


func _process_fbp_data(fbp: Variant):
	"""Process Full Body Pose data"""
	if typeof(fbp) != TYPE_DICTIONARY:
		return

	# Extract data wrapper
	if fbp.has("data") and typeof(fbp["data"]) == TYPE_DICTIONARY:
		fbp_data = fbp["data"]


# ============================================================
# UTILITY FUNCTIONS
# ============================================================
func is_finite(value: float) -> bool:
	"""Check if value is finite (not NaN or Inf)"""
	return not is_nan(value) and not is_inf(value)


func get_date_string() -> String:
	"""Get current date as string"""
	var time = Time.get_datetime_dict_from_system()
	return "%04d-%02d-%02d" % [time.year, time.month, time.day]


func load_session_info():
	"""Load session info from file"""
	if FileAccess.file_exists("user://session.json"):
		var file = FileAccess.open("user://session.json", FileAccess.READ)
		var data = JSON.parse_string(file.get_as_text())
		if typeof(data) == TYPE_DICTIONARY:
			current_date = data.get("current_date", get_date_string())
			session_id = data.get("session_id", 1)
			trial_counts = data.get("trial_counts", {})


func save_session_info():
	"""Save session info to file"""
	var data = {
		"current_date": current_date,
		"session_id": session_id,
		"trial_counts": trial_counts
	}
	var file = FileAccess.open("user://session.json", FileAccess.WRITE)
	file.store_string(JSON.stringify(data))


# ============================================================
# COMMAND SENDING TO PYTHON
# ============================================================
func send_reset_board_command():
	"""Send reset board command to Python on port 9000"""
	var command = {
		"type": "reset_board",
		"action": "stop_all_threads",
		"timestamp": Time.get_ticks_msec()
	}

	var json_str = JSON.stringify(command)

	# Create a temporary UDP socket for sending command
	var command_socket = PacketPeerUDP.new()

	if command_socket.set_dest_address("127.0.0.1", 9000) == OK:
		var error = command_socket.put_packet(json_str.to_utf8_buffer())
		if error == OK:
			print("✅ Reset command sent to Python via port 9000")
		else:
			print("❌ Failed to send reset command")
	else:
		print("❌ Failed to set destination address for reset command")


# ============================================================
# CLEANUP
# ============================================================
func _notification(what: int):
	if what == NOTIFICATION_WM_CLOSE_REQUEST:
		endgame = true
		if thread_udp_cop.is_alive():
			thread_udp_cop.wait_to_finish()
		if thread_udp_camera.is_alive():
			thread_udp_camera.wait_to_finish()
		get_tree().quit()


func _exit_tree():
	"""Cleanup on exit"""
	endgame = true
	if thread_udp_cop and thread_udp_cop.is_alive():
		thread_udp_cop.wait_to_finish()
	if thread_udp_camera and thread_udp_camera.is_alive():
		thread_udp_camera.wait_to_finish()
