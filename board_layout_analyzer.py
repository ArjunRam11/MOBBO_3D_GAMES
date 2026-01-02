"""
Board Layout Analyzer - Determines physical arrangement of force sensing boards
based on their ArUco marker positions.

Analyzes translation vectors from board pose estimation to determine if boards
are arranged in a grid pattern (e.g., 2x1, 1x2, 2x2, 3x2, etc.)
"""

import numpy as np
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


def analyze_board_layout(translations: Dict[int, np.ndarray]) -> Dict:
    """
    Analyze board layout based on translation vectors from ArUco pose estimation.

    Determines the physical grid arrangement of boards by analyzing distances and
    alignments in X-Y plane.

    Args:
        translations: Dict mapping board_id -> translation vector (3x1 or 3D array)
                     e.g., {11: array([x, y, z]), 12: array([x, y, z])}

    Returns:
        Dict containing:
        {
            'num_boards': int - total number of boards
            'layout': str - arrangement pattern (e.g., "2x1", "1x2", "2x2", "3x1", "1x3", "3x2", "2x3")
            'rows': int - number of rows in grid
            'cols': int - number of columns in grid
            'arrangement_type': str - "front_back" or "left_right" or "grid"
            'board_grid': List[List[int]] - 2D grid showing board IDs placement
            'spacing': Dict - spacing info {'x_spacing': float, 'y_spacing': float}
            'alignment_quality': Dict - alignment metrics for each direction
        }
    """

    if not translations or len(translations) == 0:
        logger.warning("No boards detected for layout analysis")
        return {
            'num_boards': 0,
            'layout': 'unknown',
            'rows': 0,
            'cols': 0,
            'arrangement_type': 'unknown',
            'board_grid': [],
            'spacing': {'x_spacing': 0, 'y_spacing': 0},
            'alignment_quality': {}
        }

    num_boards = len(translations)

    # Extract board IDs and positions (X, Y only - ignore Z)
    board_ids = sorted(translations.keys())
    positions = {}

    for board_id in board_ids:
        trans = translations[board_id]
        if isinstance(trans, np.ndarray):
            if trans.shape == (3, 1):
                x, y = trans[0, 0], trans[1, 0]  # [0]=X, [1]=Y, [2]=Z
            else:
                x, y = trans[0], trans[1]  # [0]=X, [1]=Y, [2]=Z
        else:
            x, y = trans[0], trans[1]  # [0]=X, [1]=Y, [2]=Z

        # Convert from meters to centimeters (RealSense/OpenCV returns meters)
        x = float(x) * 100.0
        y = float(y) * 100.0

        positions[board_id] = {'x': x, 'y': y}

    # Sort positions by X then Y for consistent ordering
    sorted_boards = sorted(board_ids, key=lambda bid: (positions[bid]['x'], positions[bid]['y']))

    # Calculate pairwise distances
    distances = _calculate_board_distances(positions, sorted_boards)

    # Analyze alignment and spacing
    x_values = [positions[bid]['x'] for bid in sorted_boards]
    y_values = [positions[bid]['y'] for bid in sorted_boards]

    x_diffs = np.diff(sorted(set(x_values)))  # Unique X differences
    y_diffs = np.diff(sorted(set(y_values)))  # Unique Y differences

    alignment = _analyze_alignment(positions, sorted_boards, x_diffs, y_diffs)

    # Determine layout type and grid arrangement
    layout_info = _determine_layout(
        num_boards,
        positions,
        sorted_boards,
        alignment,
        x_diffs,
        y_diffs
    )

    # Create board grid
    board_grid = _create_board_grid(layout_info['rows'], layout_info['cols'], positions, sorted_boards)

    # Calculate spacing
    spacing = {
        'x_spacing': float(np.mean(x_diffs)) if len(x_diffs) > 0 else 0,
        'y_spacing': float(np.mean(y_diffs)) if len(y_diffs) > 0 else 0
    }

    result = {
        'num_boards': num_boards,
        'layout': layout_info['layout'],
        'rows': layout_info['rows'],
        'cols': layout_info['cols'],
        'arrangement_type': layout_info['arrangement_type'],
        'board_grid': board_grid,
        'spacing': spacing,
        'alignment_quality': alignment,
        'board_positions': positions  # Include actual positions for Godot
    }

    logger.info(f"Board layout detected: {layout_info['layout']} ({layout_info['arrangement_type']})")
    logger.info(f"Grid: {layout_info['rows']}x{layout_info['cols']}, Spacing: X={spacing['x_spacing']:.2f}cm, Y={spacing['y_spacing']:.2f}cm")

    return result


def _calculate_board_distances(positions: Dict, board_ids: List) -> Dict:
    """Calculate distances between boards"""
    distances = {}
    for i, bid1 in enumerate(board_ids):
        for bid2 in board_ids[i+1:]:
            pos1 = positions[bid1]
            pos2 = positions[bid2]
            dx = pos2['x'] - pos1['x']
            dy = pos2['y'] - pos1['y']
            dist = np.sqrt(dx**2 + dy**2)
            distances[(bid1, bid2)] = {
                'distance': dist,
                'dx': dx,
                'dy': dy
            }
    return distances


def _analyze_alignment(positions: Dict, board_ids: List, x_diffs, y_diffs) -> Dict:
    """
    Analyze how well boards are aligned in X and Y directions.
    Threshold: 5cm for alignment tolerance (more practical for real-world placement)
    """
    ALIGNMENT_THRESHOLD = 5.0  # 5cm - increased from 2cm for real-world tolerance

    # Check X-alignment (are boards in vertical columns?)
    x_variance = np.var([positions[bid]['x'] for bid in board_ids]) if len(board_ids) > 1 else 0
    x_aligned = x_variance < ALIGNMENT_THRESHOLD**2

    # Check Y-alignment (are boards in horizontal rows?)
    y_variance = np.var([positions[bid]['y'] for bid in board_ids]) if len(board_ids) > 1 else 0
    y_aligned = y_variance < ALIGNMENT_THRESHOLD**2

    return {
        'x_variance': float(x_variance),
        'y_variance': float(y_variance),
        'x_aligned': bool(x_aligned),
        'y_aligned': bool(y_aligned),
        'alignment_threshold': ALIGNMENT_THRESHOLD
    }


def _determine_layout(num_boards: int, positions: Dict, sorted_boards: List,
                     alignment: Dict, x_diffs, y_diffs) -> Dict:
    """
    Determine the board layout pattern based on alignment and spacing.

    Rules:
    - If |ΔX| < 2cm AND |ΔY| > 40cm → Vertical arrangement (front-back, 2x1, 3x1, etc.)
    - If |ΔY| < 2cm AND |ΔX| > 50cm → Horizontal arrangement (left-right, 1x2, 1x3, etc.)
    - Otherwise → Grid arrangement (2x2, 2x3, 3x2, etc.)
    """

    ALIGNMENT_THRESHOLD = 10.0  # cm
    MIN_SPACING_VERTICAL = 40.0  # cm - threshold for front-back spacing
    MIN_SPACING_HORIZONTAL = 50.0  # cm - threshold for left-right spacing

    # Determine unique X and Y positions (accounting for alignment tolerance)
    x_positions = _cluster_positions([positions[bid]['x'] for bid in sorted_boards], ALIGNMENT_THRESHOLD)
    y_positions = _cluster_positions([positions[bid]['y'] for bid in sorted_boards], ALIGNMENT_THRESHOLD)

    num_unique_x = len(x_positions)
    num_unique_y = len(y_positions)

    # Determine arrangement type
    if num_unique_x == 1:
        # All boards in same X position → vertical arrangement
        arrangement_type = "front_back"
        cols = 1
        rows = num_unique_y
        spacing = np.mean(np.diff(sorted(y_positions))) if len(y_positions) > 1 else 0

        if spacing < MIN_SPACING_VERTICAL:
            # Too close, might not be intentional alignment
            arrangement_type = "front_back"

    elif num_unique_y == 1:
        # All boards in same Y position → horizontal arrangement
        arrangement_type = "left_right"
        rows = 1
        cols = num_unique_x
        spacing = np.mean(np.diff(sorted(x_positions))) if len(x_positions) > 1 else 0

        if spacing < MIN_SPACING_HORIZONTAL:
            arrangement_type = "left_right"

    else:
        # Multiple rows and columns → grid arrangement
        arrangement_type = "grid"
        rows = num_unique_y
        cols = num_unique_x

    # Create layout string
    layout = f"{rows}x{cols}"

    return {
        'layout': layout,
        'rows': rows,
        'cols': cols,
        'arrangement_type': arrangement_type,
        'num_unique_x': num_unique_x,
        'num_unique_y': num_unique_y
    }


def _cluster_positions(positions: List[float], threshold: float) -> List[float]:
    """
    Cluster positions that are within threshold distance.
    Returns representative positions for each cluster.
    """
    if len(positions) == 0:
        return []

    sorted_pos = sorted(positions)
    clusters = [[sorted_pos[0]]]

    for pos in sorted_pos[1:]:
        if abs(pos - clusters[-1][-1]) <= threshold:
            clusters[-1].append(pos)
        else:
            clusters.append([pos])

    # Return mean of each cluster
    return [float(np.mean(cluster)) for cluster in clusters]


def _create_board_grid(rows: int, cols: int, positions: Dict, board_ids: List) -> List[List]:
    """
    Create a 2D grid representation of boards showing their positions.
    """
    if rows == 0 or cols == 0:
        return []

    grid = [[0] * cols for _ in range(rows)]

    ALIGNMENT_THRESHOLD = 2.0

    # Get unique positions
    unique_x = _cluster_positions([positions[bid]['x'] for bid in board_ids], ALIGNMENT_THRESHOLD)
    unique_y = _cluster_positions([positions[bid]['y'] for bid in board_ids], ALIGNMENT_THRESHOLD)

    unique_x_sorted = sorted(unique_x)
    unique_y_sorted = sorted(unique_y)

    # Place boards in grid
    for board_id in board_ids:
        x = positions[board_id]['x']
        y = positions[board_id]['y']

        # Find closest X column
        x_col = min(range(len(unique_x_sorted)),
                   key=lambda i: abs(unique_x_sorted[i] - x))
        # Find closest Y row
        y_row = min(range(len(unique_y_sorted)),
                   key=lambda i: abs(unique_y_sorted[i] - y))

        if 0 <= y_row < rows and 0 <= x_col < cols:
            grid[y_row][x_col] = int(board_id)

    return grid


# Convenience functions for formatting output to Godot
def format_layout_for_godot(layout_info: Dict) -> Dict:
    """
    Format layout information for transmission to Godot.
    Removes numpy types and ensures JSON serializable format.
    """
    formatted = {
        'num_boards': int(layout_info['num_boards']),
        'layout': str(layout_info['layout']),
        'rows': int(layout_info['rows']),
        'cols': int(layout_info['cols']),
        'arrangement_type': str(layout_info['arrangement_type']),
        'board_grid': layout_info['board_grid'],
        'spacing': {
            'x_spacing': float(layout_info['spacing']['x_spacing']),
            'y_spacing': float(layout_info['spacing']['y_spacing'])
        },
        'alignment_quality': {
            'x_variance': float(layout_info['alignment_quality']['x_variance']),
            'y_variance': float(layout_info['alignment_quality']['y_variance']),
            'x_aligned': bool(layout_info['alignment_quality']['x_aligned']),
            'y_aligned': bool(layout_info['alignment_quality']['y_aligned'])
        },
        'board_positions': {
            str(bid): {
                'x': float(pos['x']),
                'y': float(pos['y'])
            }
            for bid, pos in layout_info.get('board_positions', {}).items()
        }
    }
    return formatted
