# Board Layout Analyzer Documentation

## Overview
The board layout analyzer automatically detects the physical arrangement of force sensing boards based on their ArUco marker positions obtained from pose estimation.

## How It Works

### 1. Input Data
- **Board translations** from ArUco pose estimation (X, Y, Z coordinates for each board)
- Analyzes only X-Y plane (ignores Z/depth)

### 2. Detection Logic

#### Vertical Arrangement (Front-Back)
- **Condition**: |ΔX| < 2cm AND |ΔY| > 40cm
- **Pattern**: 2×1, 3×1, 4×1, etc. (N rows, 1 column)
- **Meaning**: Boards arranged in front-to-back direction
- Example: Two boards aligned horizontally with 50cm spacing between them

#### Horizontal Arrangement (Left-Right)
- **Condition**: |ΔY| < 2cm AND |ΔX| > 50cm
- **Pattern**: 1×2, 1×3, 1×4, etc. (1 row, N columns)
- **Meaning**: Boards arranged in left-to-right direction
- Example: Three boards aligned vertically with 60cm spacing between them

#### Grid Arrangement
- **Condition**: Multiple unique X and Y positions
- **Pattern**: 2×2, 2×3, 3×2, 3×3, 4×2, etc.
- **Meaning**: Boards in a rectangular grid pattern
- Example: 2×3 grid (2 rows, 3 columns) with proper spacing

### 3. Output Data

The analyzer returns a dictionary containing:

```python
{
    'num_boards': int,                    # Total number of boards detected
    'layout': str,                        # Grid pattern (e.g., "2x1", "1x3", "2x2")
    'rows': int,                          # Number of rows in grid
    'cols': int,                          # Number of columns in grid
    'arrangement_type': str,              # "front_back", "left_right", or "grid"
    'board_grid': List[List[int]],        # 2D grid showing board IDs
    'spacing': {
        'x_spacing': float,               # Average spacing in X direction (cm)
        'y_spacing': float                # Average spacing in Y direction (cm)
    },
    'alignment_quality': {
        'x_variance': float,              # Variance in X positions
        'y_variance': float,              # Variance in Y positions
        'x_aligned': bool,                # Are boards aligned in X?
        'y_aligned': bool,                # Are boards aligned in Y?
        'alignment_threshold': float      # 2cm threshold
    },
    'board_positions': {
        board_id: {'x': float, 'y': float},  # Actual X, Y coordinates for each board
        ...
    }
}
```

### 4. Board Grid Representation

The `board_grid` shows the physical layout:

Example for 2×2 arrangement:
```
board_grid = [[11, 12],    # Row 0: boards 11, 12
              [21, 22]]     # Row 1: boards 21, 22
```

Example for 1×3 arrangement:
```
board_grid = [[11, 12, 13]]  # Single row with 3 columns
```

## Integration with Godot

The layout information is sent to Godot via UDP along with board pose data:

```json
{
  "board_layout": {
    "num_boards": 2,
    "layout": "2x1",
    "rows": 2,
    "cols": 1,
    "arrangement_type": "front_back",
    "board_grid": [[11], [12]],
    "spacing": {"x_spacing": 0.5, "y_spacing": 45.3},
    "alignment_quality": {...},
    "board_positions": {
      "11": {"x": 0.0, "y": 0.0},
      "12": {"x": 0.2, "y": 45.3}
    }
  }
}
```

## Use Cases in Godot

The Godot application can use layout information to:

1. **Customize game layout** - Position UI elements based on board arrangement
2. **Load appropriate maps** - Different game modes for different board configs
3. **Scale difficulty** - Adjust game parameters based on number of boards
4. **Spatial optimization** - Align 3D objects with board grid
5. **Multiplayer setup** - Assign players to specific boards in grid

## Expandability

The analyzer is designed to handle any number of boards:
- Tested conceptually for 2-6+ boards
- Automatically determines grid dimensions (rows, cols)
- Works with asymmetric grids if needed

## Thresholds

Current thresholds (configurable in `board_layout_analyzer.py`):
- **X-alignment threshold**: 2.0 cm
- **Y-alignment threshold**: 2.0 cm
- **Minimum vertical spacing**: 40 cm (to distinguish front-back arrangement)
- **Minimum horizontal spacing**: 50 cm (to distinguish left-right arrangement)

## Error Handling

If board layout analysis fails:
- Returns layout: "unknown"
- Logs warning with error details
- Continues with other operations
- Godot can fall back to default behavior

## Files Modified

1. **board_layout_analyzer.py** (NEW)
   - Core analysis functions
   - `analyze_board_layout()` - Main entry point
   - `format_layout_for_godot()` - Data formatting

2. **godot_bridge.py** (MODIFIED)
   - Added `board_layout_data` storage
   - Added `update_board_layout_data()` method
   - Modified `_get_cop_data()` to include layout in UDP packets

3. **main.py** (MODIFIED)
   - Import board layout analyzer
   - Call analyzer after board pose detection
   - Send results to Godot

## Testing

To test the analyzer:

```python
from board_layout_analyzer import analyze_board_layout, format_layout_for_godot
import numpy as np

# Example: 2x1 arrangement
translations = {
    11: np.array([[0.0], [0.0], [100.0]]),      # Front board
    12: np.array([[0.2], [45.0], [150.0]])      # Back board
}

layout = analyze_board_layout(translations)
print(layout['layout'])              # Output: "2x1"
print(layout['arrangement_type'])    # Output: "front_back"
```

## Future Enhancements

Possible improvements:
- Dynamic threshold adjustment based on measured spacing
- Support for non-rectangular arrangements
- Board orientation detection
- Automatic mapping to physical space
- Calibration utilities
