# ============================================================================
# IMPLEMENTATION CODE FOR CoP BOARD LAYOUT SCALING
# Copy these sections into e:\...\global_script.gd
# ============================================================================

# ============================================================================
# SECTION 1: ADD AFTER LINE 95 (After raw_z definition)
# ============================================================================
# This section adds the board layout configuration variables

var board_layout: String = "2x1"  # Default layout

# CoP scaling ranges based on board layout
var cop_x_min: float = 0.30
var cop_x_max: float = -0.30
var cop_y_min: float = -0.225
var cop_y_max: float = 0.675


# ============================================================================
# SECTION 2: ADD FUNCTION AFTER handle_cop_data_safe() (Around line 420)
# ============================================================================
# This function updates scaling based on detected board layout

func set_scaling_for_layout(layout: String) -> void:
	"""
	Update CoP scaling ranges based on board layout.
	Called when board layout is detected from Python.

	Args:
		layout: Board layout string ("1x2" or "2x1")
	"""
	board_layout = layout

	if layout == "1x2":
		# Layout: 1 board wide, 2 boards tall (vertical stacking)
		# User stands facing LEFT-RIGHT axis
		cop_x_min = -0.90
		cop_x_max = 0.30
		cop_y_min = -0.225
		cop_y_max = 0.225
		print("📐 SCALING CONFIGURED: 1x2 Layout")
		print("   X Range: %.2f to %.2f (LEFT to RIGHT)" % [cop_x_min, cop_x_max])
		print("   Y Range: %.2f to %.2f (BACK to FRONT)" % [cop_y_min, cop_y_max])

	elif layout == "2x1":
		# Layout: 2 boards wide, 1 board tall (horizontal stacking)
		# User stands facing FORWARD-BACKWARD axis
		# NOTE: X is REVERSED (0.30 to -0.30)
		cop_x_min = 0.30
		cop_x_max = -0.30
		cop_y_min = -0.225
		cop_y_max = 0.675
		print("📐 SCALING CONFIGURED: 2x1 Layout")
		print("   X Range: %.2f to %.2f (RIGHT to LEFT - REVERSED)" % [cop_x_min, cop_x_max])
		print("   Y Range: %.2f to %.2f (BACK to FRONT)" % [cop_y_min, cop_y_max])

	else:
		print("⚠️ UNKNOWN LAYOUT: %s, using default 2x1" % layout)
		cop_x_min = 0.30
		cop_x_max = -0.30
		cop_y_min = -0.225
		cop_y_max = 0.675


# ============================================================================
# SECTION 3: MODIFY handle_board_pose_data_safe() FUNCTION
# ============================================================================
# Find the section around line 545-549 and update it:

	# Extract and store board layout if included
	if data_content.has("layout"):
		var layout_container = data_content["layout"]
		if typeof(layout_container) == TYPE_DICTIONARY:
			var layout_str = layout_container.get("Board_Layout", "2x1")
			print("📐 Board Layout: %s" % str(layout_container))
			# CRITICAL: Update scaling for the detected layout
			set_scaling_for_layout(layout_str)


# ============================================================================
# SECTION 4: MODIFY handle_cop_data_safe() FUNCTION
# ============================================================================
# Replace the CoP calculation section (lines 386-401) with this:

			# Validate values are finite (not NaN or Inf)
			if is_finite(raw_x) and is_finite(raw_y) and is_finite(raw_z) and is_finite(weight):
				# Set connection status
				if weight > 0:
					_incoming_message = 2.0  # Connected
					connected = true

				# Print global CoP data every 50 frames
				if Engine.get_process_frames() % 50 == 0:
					print("🌐 GLOBAL CoP: x=%.4f, y=%.4f, z=%.4f, weight=%.2f" % [raw_x, raw_y, raw_z, weight])

				# ============================================================
				# CRITICAL FIX: Scale raw CoP using board layout ranges
				# ============================================================

				# Determine actual min/max (accounts for reversed X in 2x1)
				var actual_x_min = min(cop_x_min, cop_x_max)
				var actual_x_max = max(cop_x_min, cop_x_max)
				var actual_y_min = min(cop_y_min, cop_y_max)
				var actual_y_max = max(cop_y_min, cop_y_max)

				# Normalize CoP values to 0.0-1.0 range based on board layout
				# This maps the physical board space to normalized screen space
				var normalized_x = (raw_x - actual_x_min) / (actual_x_max - actual_x_min)
				var normalized_y = (raw_y - actual_y_min) / (actual_y_max - actual_y_min)

				# Clamp to valid 0.0-1.0 range
				normalized_x = clampf(normalized_x, 0.0, 1.0)
				normalized_y = clampf(normalized_y, 0.0, 1.0)

				# Handle reversed X axis for 2x1 layout
				# In 2x1 layout, cop_x_min (0.30) > cop_x_max (-0.30), meaning X is reversed
				if board_layout == "2x1" and cop_x_min > cop_x_max:
					normalized_x = 1.0 - normalized_x  # Invert: right→left becomes left→right in screen coords

				# Map normalized coordinates to screen coordinates
				var screen_width = float(MAX_X - MIN_X)
				var screen_height = float(MAX_Y - MIN_Y)

				net_x = MIN_X + (normalized_x * screen_width)
				net_y = MIN_Y + (normalized_y * screen_height)
				net_z = net_y  # For 2D games that use Z as vertical

				# Update all output positions
				net_a = net_y  # Alternative vertical position

				# Store in both 2D and 3D formats
				network_position = Vector2(net_x, net_z)
				network_position3D = Vector2(net_x, net_y)

				# OPTIONAL: Apply adaptive scaling if enabled
				# (This is for games with "Adapt ROM" toggle)
				# Commented out for now - implement if needed
				# if GlobalSignals.global_scalar_x > 0 and GlobalSignals.global_scalar_y > 0:
				#     scaled_network_position = Vector2(
				#         net_x * GlobalSignals.global_scalar_x,
				#         net_z * GlobalSignals.global_scalar_y
				#     )
				#     scaled_network_position3D = Vector2(
				#         net_x * GlobalSignals.global_scalar_x,
				#         net_y * GlobalSignals.global_scalar_y
				#     )


# ============================================================================
# DEBUGGING: Add this function to print scaling status
# ============================================================================

func print_cop_scaling_info() -> void:
	"""Debug function to print current CoP scaling configuration"""
	print("\n" + "=".repeat(60))
	print("📊 CoP SCALING CONFIGURATION")
	print("=".repeat(60))
	print("Board Layout: %s" % board_layout)
	print("\nCoP Ranges (from board):")
	print("  X: %.4f to %.4f" % [cop_x_min, cop_x_max])
	print("  Y: %.4f to %.4f" % [cop_y_min, cop_y_max])
	print("\nScreen Ranges (output):")
	print("  X: %d to %d" % [MIN_X, MAX_X])
	print("  Y: %d to %d" % [MIN_Y, MAX_Y])
	print("\nCurrent CoP Position:")
	print("  Raw: (%.4f, %.4f, %.4f)" % [raw_x, raw_y, raw_z])
	print("  Screen: (%.0f, %.0f, %.0f)" % [net_x, net_y, net_z])
	print("\nGame Positions:")
	print("  network_position: %s" % str(network_position))
	print("  network_position3D: %s" % str(network_position3D))
	print("=".repeat(60) + "\n")


# ============================================================================
# EXAMPLE USAGE IN _process() OR _ready()
# ============================================================================

# To debug scaling at any time, call:
# GlobalScript.print_cop_scaling_info()

# To manually set layout (for testing):
# GlobalScript.set_scaling_for_layout("1x2")
# GlobalScript.set_scaling_for_layout("2x1")


# ============================================================================
# VERIFICATION STEPS
# ============================================================================

# After implementing, you should see in console:

# ✅ On startup:
#    "📐 SCALING CONFIGURED: 2x1 Layout"
#    "   X Range: 0.3000 to -0.3000 (RIGHT to LEFT - REVERSED)"
#    "   Y Range: -0.2250 to 0.6750 (BACK to FRONT)"

# ✅ When board detected:
#    "📐 Board Layout: { "Board_Layout": "2x1" }"

# ✅ Continuous CoP updates:
#    "🌐 GLOBAL CoP: x=0.1234, y=0.0567, z=-0.0891, weight=85.50"

# ✅ Games respond to CoP movement:
#    - Fruit Catcher paddle moves left/right
#    - Jumpify player moves forward/backward
#    - Flappy Bird moves up/down


# ============================================================================
# INTEGRATION WITH EXISTING CODE
# ============================================================================

# The existing code references these variables:
#   PLAYER_POS_SCALER_X (line 51)
#   PLAYER_POS_SCALER_Z (line 52)
#   X_SCREEN_OFFSET (line 40)
#   Y_SCREEN_OFFSET (line 41)
#
# These are still used for ADAPTIVE SCALING (when games have "Adapt ROM" enabled)
# Our new scaling uses board layout ranges instead for PRIMARY scaling.
#
# For adaptive mode games, keep the existing PLAYER_POS_SCALER values unchanged.
# The board layout scaling applies to RAW CoP→SCREEN mapping.
