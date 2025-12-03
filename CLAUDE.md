# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
This is a 3D human motion analysis system that combines RealSense camera data with ArUco board positioning for biomechanical analysis. The system tracks human pose, foot keypoints, and center of pressure (CoP) data from force-sensing boards to compute base of support (BOS) and global center of pressure (GCoP).

## Key Dependencies
- OpenCV with ArUco support
- PyQt5 for GUI
- PyRealsense2 for camera interface
- YOLO (Ultralytics) for foot detection
- MediaPipe for pose estimation
- NumPy for mathematical operations
- Matplotlib/PyQtGraph for 3D visualization

## Core Architecture

### Main Application Flow
- **main.py**: Entry point - initializes Frame_Process, BOSEstimator, and ArUco3DVisualizer
- **Frame_Process.py**: Handles RealSense camera pipeline, video recording, and exposure settings
- **Graph_window_main.py**: Main PyQt5 GUI with 3D visualization using pyqtgraph.opengl

### Key Processing Components
- **BOSEstimator** (main.py): Central coordinator managing all processing threads
- **board_pose_estimator.py**: Detects ArUco boards and computes their 3D poses
- **foot_process.py**: YOLO-based foot keypoint detection with threading
- **base_of_support_lib.py**: Mathematical functions for 3D transformations and BOS calculations
- **COP_wifi_data.py**: WiFi communication for receiving force sensor data

### Data Processing Pipeline
1. **Board Detection**: ArUco markers establish coordinate reference frames
2. **Foot Detection**: YOLO model detects foot keypoints (heel/toe positions)
3. **Pose Estimation**: MediaPipe extracts 18 3D human keypoints
4. **CoP Integration**: WiFi data from force boards provides center of pressure
5. **3D Transformation**: All data transformed to reference board coordinate system
6. **BOS Computation**: Combines foot polygons and CoP data for analysis

### Threading Architecture
- **ArUco Thread**: Processes pose estimation and keypoint detection
- **BOS Thread**: Computes center of pressure and base of support continuously
- **Foot Detection Thread**: Runs YOLO inference in background
- **GUI Thread**: Handles PyQt5 interface and 3D visualization updates

## Development Commands

### Running the Application
```bash
python main.py
```

### Key Configuration Files
- **aruco_data.py**: Camera calibration matrices and ArUco board parameters
- **selected_colors.json**: GUI color configuration for visualization elements

### Model Files
- **yolov8n-pose.pt**: Human pose detection model
- **yolov8n-seg.pt**: Segmentation model
- **model/foot_pose_2pt.pt**: Custom foot keypoint detection model

## Important Code Patterns

### Global Shared Data
The system uses global numpy arrays with threading locks for real-time data sharing:
- `pose_3d_keypoints`: 18x3 human keypoints
- `gcop1`: Global center of pressure
- `data_lock`: Threading synchronization

### Camera Integration
RealSense camera access through `Frame_Process` class with proper pipeline management and error handling for device detection.

### 3D Coordinate Transformations
All spatial data is transformed to a common reference frame using the closest ArUco board as reference. The `base_of_support_lib.py` contains transformation utilities.

### Thread Management
Use the established pattern of setting global flags (`stop_flag_aruco`, `stop_threads`) and properly joining threads in `BOSEstimator.stop_all_threads()`.

## Recent Optimizations (2025-09-24)

### Architecture Refactoring
The main.py file has been completely refactored from a monolithic 536-line class to a modular architecture:
- **BoardManager**: Handles ArUco board detection and pose estimation
- **CoordinateTransformer**: Manages 3D coordinate transformations
- **ThreadManager**: Centralized thread lifecycle management
- **BoardData**: Encapsulates board state information
- **ThreadState**: Thread status tracking

### Performance Improvements
- **Reduced Sleep Intervals**: Changed from 0.1s to 0.01s in critical loops
- **Optimized Imports**: Replaced wildcard imports with specific imports
- **Memory Optimization**: Better numpy array handling and reduced allocations
- **Verbose Logging**: Reduced COP data console spam to every 50th message

### Error Handling Enhancements
- **Comprehensive Logging**: Added structured logging with severity levels
- **Graceful Shutdown**: Proper cleanup of all threads and resources
- **Exception Handling**: Try-catch blocks around critical operations
- **Attribute Safety**: Added missing class attributes for backward compatibility

### Fixed Issues
- **Import Resolution**: Fixed incorrect module imports (functions moved between modules)
- **Variable Scoping**: Resolved `bos_estimator` and `visualizer` undefined errors
- **Case Sensitivity**: Fixed MAT/DIST vs mat/dist inconsistencies
- **Thread Synchronization**: Proper thread lifecycle management

### Dependencies
Python interpreter path: `C:\Users\Pintu\miniconda3\envs\mpy11\python.exe`

### Testing
The system has been tested and verified to run without errors with:
- Real-time force sensor data processing (2 boards: 192.168.0.102, 192.168.0.103)
- Camera initialization and ArUco detection
- 3D visualization with PyQt5
- All threads running synchronously

### Git Configuration
- Comprehensive .gitignore added for Python projects
- Data folders (captures_Photo/, Mobbo_data/) excluded from version control
- Model files and temporary data excluded