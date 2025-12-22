"""
Data filtering utilities for smoothing sensor data and reducing jitter
Implements Exponential Moving Average (EMA) and Outlier Detection filters
"""

import numpy as np
from collections import deque
import logging

logger = logging.getLogger(__name__)


class ExponentialMovingAverage:
    """
    Exponential Moving Average filter for smoothing data

    Formula: smoothed = alpha * new_value + (1 - alpha) * previous_value

    Lower alpha = more smoothing (slower response)
    Higher alpha = less smoothing (faster response, more noise)
    """

    def __init__(self, alpha=0.3):
        """
        Args:
            alpha: Smoothing factor (0 < alpha < 1)
                   0.3 = moderate smoothing (recommended)
                   0.1 = aggressive smoothing (lag)
                   0.5 = less smoothing (noisier)
        """
        self.alpha = alpha
        self.value = None

    def update(self, new_value):
        """Update filter with new value and return smoothed output"""
        if self.value is None:
            self.value = new_value
        else:
            self.value = self.alpha * new_value + (1 - self.alpha) * self.value
        return self.value

    def reset(self):
        """Reset filter state"""
        self.value = None

    def __repr__(self):
        return f"EMA(alpha={self.alpha}, current={self.value})"


class OutlierFilter:
    """
    Detects and rejects outlier values beyond statistical threshold

    Uses z-score: (value - mean) / std_dev
    Rejects values where |z-score| > threshold (default: 2.0 = 95% confidence)
    """

    def __init__(self, window_size=10, threshold=2.0):
        """
        Args:
            window_size: Number of recent values to track for statistics
            threshold: Z-score threshold for outlier rejection
                      2.0 = 95% confidence (standard)
                      3.0 = 99.7% confidence (very strict)
        """
        self.window = deque(maxlen=window_size)
        self.threshold = threshold
        self.rejected_count = 0

    def is_outlier(self, value):
        """Check if value is an outlier"""
        if len(self.window) < 3:
            # Need at least 3 samples for meaningful statistics
            return False

        mean = np.mean(list(self.window))
        std = np.std(list(self.window))

        if std == 0:
            # All values are identical, no outliers possible
            return False

        z_score = abs(value - mean) / std
        return z_score > self.threshold

    def update(self, value):
        """
        Update filter with new value
        Returns value if not outlier, returns last valid value if outlier
        """
        if not self.is_outlier(value):
            self.window.append(value)
            return value
        else:
            # Reject outlier, return last valid value
            self.rejected_count += 1
            return list(self.window)[-1] if len(self.window) > 0 else value

    def get_stats(self):
        """Get current statistics"""
        if len(self.window) == 0:
            return None
        return {
            "mean": float(np.mean(list(self.window))),
            "std": float(np.std(list(self.window))),
            "min": float(np.min(list(self.window))),
            "max": float(np.max(list(self.window))),
            "rejected_count": self.rejected_count
        }

    def __repr__(self):
        stats = self.get_stats()
        if stats:
            return f"OutlierFilter(threshold={self.threshold}, mean={stats['mean']:.3f}, std={stats['std']:.3f})"
        return f"OutlierFilter(threshold={self.threshold}, window_size={len(self.window)})"


class CoordinateFilter:
    """
    Filter for 3D coordinate data (x, y, z)

    Combines two stages:
    1. Outlier rejection (removes spikes)
    2. Exponential smoothing (reduces jitter)
    """

    def __init__(self, alpha=0.3, outlier_threshold=2.0):
        """
        Args:
            alpha: EMA smoothing factor (0.3 recommended)
            outlier_threshold: Z-score threshold for outlier detection (2.0 recommended)
        """
        # Create separate filters for each axis
        self.x_filter = ExponentialMovingAverage(alpha)
        self.y_filter = ExponentialMovingAverage(alpha)
        self.z_filter = ExponentialMovingAverage(alpha)

        # Outlier filters for each axis
        self.x_outlier = OutlierFilter(threshold=outlier_threshold)
        self.y_outlier = OutlierFilter(threshold=outlier_threshold)
        self.z_outlier = OutlierFilter(threshold=outlier_threshold)

        self.update_count = 0

    def update(self, x, y, z):
        """
        Filter 3D coordinate

        Returns:
            (x_smooth, y_smooth, z_smooth): Filtered coordinates
        """
        self.update_count += 1

        # Stage 1: Outlier rejection (removes spikes)
        x_clean = self.x_outlier.update(x)
        y_clean = self.y_outlier.update(y)
        z_clean = self.z_outlier.update(z)

        # Stage 2: Exponential smoothing (reduces jitter)
        x_smooth = self.x_filter.update(x_clean)
        y_smooth = self.y_filter.update(y_clean)
        z_smooth = self.z_filter.update(z_clean)

        return x_smooth, y_smooth, z_smooth

    def reset(self):
        """Reset all filters"""
        self.x_filter.reset()
        self.y_filter.reset()
        self.z_filter.reset()
        self.update_count = 0

    def get_stats(self):
        """Get filter statistics for monitoring"""
        return {
            "updates": self.update_count,
            "x_outliers": self.x_outlier.rejected_count,
            "y_outliers": self.y_outlier.rejected_count,
            "z_outliers": self.z_outlier.rejected_count,
            "total_outliers": (
                self.x_outlier.rejected_count +
                self.y_outlier.rejected_count +
                self.z_outlier.rejected_count
            )
        }

    def __repr__(self):
        stats = self.get_stats()
        return (
            f"CoordinateFilter("
            f"updates={stats['updates']}, "
            f"outliers={stats['total_outliers']}"
            f")"
        )


class VectorFilter:
    """
    Filter for numpy arrays (vectors/matrices)
    Used for filtering full arrays like pose keypoints
    """

    def __init__(self, alpha=0.3, outlier_threshold=2.0):
        """
        Args:
            alpha: EMA smoothing factor
            outlier_threshold: Outlier detection threshold
        """
        self.alpha = alpha
        self.outlier_threshold = outlier_threshold
        self.previous_value = None
        self.outlier_filter = OutlierFilter(threshold=outlier_threshold)

    def update(self, new_value):
        """
        Filter array/vector data

        Args:
            new_value: numpy array or list

        Returns:
            Filtered array
        """
        new_value = np.asarray(new_value)

        # Check for outliers (using magnitude/norm for vectors)
        magnitude = np.linalg.norm(new_value)
        if self.outlier_filter.is_outlier(magnitude):
            # Return last valid value if outlier detected
            if self.previous_value is not None:
                return self.previous_value
            else:
                return new_value

        # Apply EMA smoothing
        if self.previous_value is None:
            self.previous_value = new_value
            return new_value

        smoothed = (
            self.alpha * new_value +
            (1 - self.alpha) * self.previous_value
        )
        self.previous_value = smoothed
        return smoothed

    def reset(self):
        """Reset filter"""
        self.previous_value = None
        self.outlier_filter = OutlierFilter(threshold=self.outlier_threshold)


if __name__ == "__main__":
    """Test the filters"""
    print("Testing CoordinateFilter...")

    # Create filter
    filter = CoordinateFilter(alpha=0.3, outlier_threshold=2.0)

    # Simulate noisy sensor data (movement + outliers)
    np.random.seed(42)
    for i in range(100):
        # True signal: smooth circular motion
        t = i * 0.1
        x_true = 0.5 * np.cos(t)
        y_true = 0.5 * np.sin(t)
        z_true = 0.3

        # Add noise
        x_noisy = x_true + np.random.normal(0, 0.02)
        y_noisy = y_true + np.random.normal(0, 0.02)
        z_noisy = z_true + np.random.normal(0, 0.01)

        # Randomly add outliers
        if np.random.random() < 0.05:  # 5% outlier rate
            x_noisy += np.random.normal(0, 0.3)

        # Filter
        x_smooth, y_smooth, z_smooth = filter.update(x_noisy, y_noisy, z_noisy)

        if i % 20 == 0:
            print(
                f"Step {i}: "
                f"Noisy=({x_noisy:.3f}, {y_noisy:.3f}, {z_noisy:.3f}) -> "
                f"Smooth=({x_smooth:.3f}, {y_smooth:.3f}, {z_smooth:.3f})"
            )

    print("\nFilter Statistics:")
    stats = filter.get_stats()
    print(f"  Total updates: {stats['updates']}")
    print(f"  Outliers rejected: {stats['total_outliers']}")
    print(f"  Outlier rate: {stats['total_outliers'] / (stats['updates'] * 3) * 100:.1f}%")
