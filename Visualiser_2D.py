"""
visualizer_2d.py  — 2-D top-down CoP / board / foot visualiser
"""

import numpy as np
import cv2
from PyQt5 import QtWidgets, QtCore, QtGui
from scipy.spatial import ConvexHull, QhullError

# ── colours ───────────────────────────────────────────────────────────────────
C_BG        = QtGui.QColor(255, 255, 255)
C_BOARD     = QtGui.QColor(0,   0,   0)
C_LOCAL_COP = QtGui.QColor(30,  100, 255)
C_GCOP      = QtGui.QColor(220, 30,  30)
C_FOOT      = QtGui.QColor(255, 140, 0)
C_HULL      = QtGui.QColor(0,   0,   0)
C_GRID      = QtGui.QColor(210, 210, 210)
C_AXIS_TXT  = QtGui.QColor(50,  50,  50)
C_FRAME     = QtGui.QColor(80,  80,  80)

R_LOCAL_COP = 8
R_GCOP      = 12
MARGIN_M    = 0.15


# ─────────────────────────────────────────────────────────────────────────────
class _PlotCanvas(QtWidgets.QWidget):

    def __init__(self, bos_estimator, parent=None):
        super().__init__(parent)
        self.bos = bos_estimator
        self._debug_printed = False
        self.setAttribute(QtCore.Qt.WA_OpaquePaintEvent)

    # ── one-time diagnostic ───────────────────────────────────────────────────
    def _debug_print(self):
        if self._debug_printed:
            return
        bos = self.bos
        print("\n=== [Visualizer2D] coordinate diagnostic ===")
        for bid, pts in bos.board_points_3d.items():
            arr = np.asarray(pts)
            print(f"  board_points_3d[{bid}] shape={arr.shape}  "
                  f"X=[{arr[:,0].min():.3f},{arr[:,0].max():.3f}]  "
                  f"Y=[{arr[:,1].min():.3f},{arr[:,1].max():.3f}]")
        for i, (v, w) in enumerate(getattr(bos, 'all_cops', [])):
            vf = np.asarray(v).flatten()
            print(f"  local_cop[{i}]  x={vf[0]:.3f}  y={vf[1]:.3f}  w={w:.1f}")
        try:
            from Graph_window_main import gcop1
            if gcop1 is not None:
                g = np.asarray(gcop1).flatten()
                print(f"  gcop1  x={g[0]:.3f}  y={g[1]:.3f}")
        except ImportError:
            pass
        print("===========================================\n")
        self._debug_printed = True

    # ── transform ─────────────────────────────────────────────────────────────
    def _build_transform(self, cw, ch):
        bos = self.bos
        all_x, all_y = [], []
        for bid, pts in bos.board_points_3d.items():
            arr = np.asarray(pts)
            if arr.ndim == 2 and arr.shape[1] >= 2:
                all_x.extend(arr[:, 0].tolist())
                all_y.extend(arr[:, 1].tolist())
        for v, _ in getattr(bos, 'all_cops', []):
            vf = np.asarray(v).flatten()
            if len(vf) >= 2 and np.isfinite(vf[:2]).all():
                all_x.append(float(vf[0]))
                all_y.append(float(vf[1]))
        if not all_x:
            all_x = [-0.5, 0.5];  all_y = [-0.5, 0.5]

        x_min = min(all_x) - MARGIN_M;  x_max = max(all_x) + MARGIN_M
        y_min = min(all_y) - MARGIN_M;  y_max = max(all_y) + MARGIN_M
        world_w = max(x_max - x_min, 1e-6)
        world_h = max(y_max - y_min, 1e-6)

        # padding: left=60 (Y labels), right=20, top=20, bottom=50 (X labels)
        PL, PR, PT, PB = 60, 20, 20, 50
        draw_w = cw - PL - PR
        draw_h = ch - PT - PB
        scale  = min(draw_w / world_w, draw_h / world_h)

        ox = PL + (draw_w - world_w * scale) / 2 - x_min * scale
        oy = ch - PB - (draw_h - world_h * scale) / 2 + y_min * scale

        return scale, ox, oy, x_min, x_max, y_min, y_max, PL, PR, PT, PB

    def _wc(self, wx, wy, scale, ox, oy):
        return int(wx * scale + ox), int(-wy * scale + oy)

    # ── paint ─────────────────────────────────────────────────────────────────
    def paintEvent(self, _ev):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        cw, ch = self.width(), self.height()
        painter.fillRect(0, 0, cw, ch, C_BG)

        bos = self.bos
        if not bos.board_points_3d:
            painter.setPen(QtGui.QPen(QtGui.QColor(150, 150, 150)))
            painter.drawText(cw // 2 - 90, ch // 2, "Waiting for board detection…")
            painter.end()
            return

        scale, ox, oy, x_min, x_max, y_min, y_max, PL, PR, PT, PB = \
            self._build_transform(cw, ch)

        def wc(wx, wy):
            return self._wc(wx, wy, scale, ox, oy)

        # ── clip to plot area so nothing bleeds into label margins ────────────
        plot_rect = QtCore.QRect(PL, PT, cw - PL - PR, ch - PT - PB)
        painter.setClipRect(plot_rect)

        # grid
        self._draw_grid(painter, wc, scale, x_min, x_max, y_min, y_max, cw, ch,
                        PL, PR, PT, PB)

        # boards (black outline, NO label)
        painter.setPen(QtGui.QPen(C_BOARD, 2))
        painter.setBrush(QtCore.Qt.NoBrush)
        for bid, pts in bos.board_points_3d.items():
            arr = np.asarray(pts)
            if arr.ndim != 2 or arr.shape[0] < 4 or arr.shape[1] < 2:
                continue
            corners = [QtCore.QPoint(*wc(p[0], p[1])) for p in arr[:4]]
            painter.drawPolygon(QtGui.QPolygon(corners))

        # foot outlines (orange)
        pen_foot = QtGui.QPen(C_FOOT, 2)
        painter.setPen(pen_foot)
        painter.setBrush(QtCore.Qt.NoBrush)
        all_foot_xy = []
        for foot_pts in [bos.left_foot_polygon_point, bos.right_foot_polygon_point]:
            if foot_pts is None:
                continue
            arr = np.asarray(foot_pts)
            if arr.ndim != 2 or arr.shape[1] < 2:
                continue
            valid = np.isfinite(arr[:, :2]).all(axis=1)
            arr = arr[valid]
            if len(arr) < 2:
                continue
            all_foot_xy.append(arr[:, :2])
            qpts = [QtCore.QPoint(*wc(p[0], p[1])) for p in arr]
            painter.drawPolyline(QtGui.QPolygon(qpts + [qpts[0]]))

        # BoS convex hull (black dashed)
        if all_foot_xy:
            combined = np.vstack(all_foot_xy)
            if combined.shape[0] >= 3:
                try:
                    hull = ConvexHull(combined, qhull_options='QJ')
                    hp = combined[hull.vertices]
                    painter.setPen(QtGui.QPen(C_HULL, 2, QtCore.Qt.DashLine))
                    painter.setBrush(QtCore.Qt.NoBrush)
                    painter.drawPolygon(
                        QtGui.QPolygon([QtCore.QPoint(*wc(p[0], p[1])) for p in hp]))
                except QhullError:
                    pass

        # local CoPs (blue)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QBrush(C_LOCAL_COP))
        for cop_vec, _w in getattr(bos, 'all_cops', []):
            v = np.asarray(cop_vec).flatten()
            if len(v) < 2 or not np.isfinite(v[:2]).all():
                continue
            px, py = wc(v[0], v[1])
            painter.drawEllipse(px - R_LOCAL_COP, py - R_LOCAL_COP,
                                R_LOCAL_COP * 2, R_LOCAL_COP * 2)

        # GCoP (red dot + crosshair)
        try:
            from Graph_window_main import gcop1
            if gcop1 is not None:
                g = np.asarray(gcop1).flatten()
                if len(g) >= 2 and np.isfinite(g[:2]).all():
                    gx, gy = wc(g[0], g[1])
                    painter.setBrush(QtGui.QBrush(C_GCOP))
                    painter.setPen(QtGui.QPen(C_GCOP.darker(160), 1))
                    painter.drawEllipse(gx - R_GCOP, gy - R_GCOP,
                                        R_GCOP * 2, R_GCOP * 2)
                    painter.setPen(QtGui.QPen(QtGui.QColor(160, 0, 0), 1))
                    painter.drawLine(gx - R_GCOP - 6, gy, gx + R_GCOP + 6, gy)
                    painter.drawLine(gx, gy - R_GCOP - 6, gx, gy + R_GCOP + 6)
        except ImportError:
            pass

        # ── remove clip so frame and legend draw over everything ──────────────
        painter.setClipping(False)

        # plot frame (border around the plot area)
        painter.setPen(QtGui.QPen(C_FRAME, 2))
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawRect(plot_rect)

        self._draw_legend(painter, cw, PT)
        painter.end()

    # ── grid + axis labels ────────────────────────────────────────────────────
    def _draw_grid(self, painter, wc, scale, x_min, x_max, y_min, y_max,
                   cw, ch, PL, PR, PT, PB):
        import math

        world_span = max(x_max - x_min, y_max - y_min)
        raw_step   = world_span / 7
        magnitude  = 10 ** math.floor(math.log10(max(raw_step, 1e-9)))
        step = magnitude
        for f in [1, 2, 5, 10]:
            if world_span / (magnitude * f) <= 8:
                step = magnitude * f
                break

        pen_grid = QtGui.QPen(C_GRID, 1, QtCore.Qt.DotLine)

        def ticks(lo, hi, s):
            return np.arange(math.ceil(lo / s) * s, hi + s * 0.01, s)

        # ── X tick lines + labels ─────────────────────────────────────────────
        fnt = QtGui.QFont("Arial", 8)
        painter.setFont(fnt)
        for xv in ticks(x_min, x_max, step):
            px, _  = wc(xv, 0)
            _, py0 = wc(xv, y_min)
            _, py1 = wc(xv, y_max)
            painter.setPen(pen_grid)
            painter.drawLine(px, min(py0, py1), px, max(py0, py1))
            painter.setPen(QtGui.QPen(C_AXIS_TXT))
            lbl = f"{xv:.2f}"
            # centre label under tick
            fm  = QtGui.QFontMetrics(fnt)
            lw  = fm.width(lbl)
            painter.drawText(px - lw // 2, ch - PB + 18, lbl)

        # ── Y tick lines + labels ─────────────────────────────────────────────
        for yv in ticks(y_min, y_max, step):
            _, py  = wc(0, yv)
            px0, _ = wc(x_min, yv)
            px1, _ = wc(x_max, yv)
            painter.setPen(pen_grid)
            painter.drawLine(min(px0, px1), py, max(px0, px1), py)
            painter.setPen(QtGui.QPen(C_AXIS_TXT))
            lbl = f"{yv:.2f}"
            fm  = QtGui.QFontMetrics(fnt)
            lh  = fm.height()
            lw  = fm.width(lbl)
            painter.drawText(PL - lw - 6, py + lh // 3, lbl)

        # ── axis title labels ─────────────────────────────────────────────────
        fnt_title = QtGui.QFont("Arial", 9, QtGui.QFont.Bold)
        painter.setFont(fnt_title)
        painter.setPen(QtGui.QPen(C_AXIS_TXT))

        # X label centred below plot
        x_title = "X  (m)"
        fm = QtGui.QFontMetrics(fnt_title)
        painter.drawText(PL + (cw - PL - PR) // 2 - fm.width(x_title) // 2,
                         ch - 6, x_title)

        # Y label rotated, centred left of plot
        painter.save()
        painter.translate(14, PT + (ch - PT - PB) // 2 + fm.width("Y  (m)") // 2)
        painter.rotate(-90)
        painter.drawText(0, 0, "Y  (m)")
        painter.restore()

    # ── legend (top-right, inside plot) ──────────────────────────────────────
    def _draw_legend(self, painter, cw, PT):
        items = [
            (C_LOCAL_COP, "Local CoP"),
            (C_GCOP,      "GCoP"),
            (C_FOOT,      "Foot outline"),
            (C_HULL,      "BoS hull"),
            (C_BOARD,     "Board"),
        ]
        row_h = 20
        box_w = 115
        box_h = len(items) * row_h + 10
        x0 = cw - box_w - 28
        y0 = PT + 8

        # semi-transparent white background
        painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255, 220)))
        painter.setPen(QtGui.QPen(C_FRAME, 1))
        painter.drawRect(x0, y0, box_w, box_h)

        fnt = QtGui.QFont("Arial", 8)
        painter.setFont(fnt)
        y = y0 + 14
        for color, label in items:
            painter.setBrush(QtGui.QBrush(color))
            painter.setPen(QtGui.QPen(color.darker(110)))
            painter.drawRect(x0 + 6, y - 9, 11, 11)
            painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))
            painter.drawText(x0 + 22, y, label)
            y += row_h


# ─────────────────────────────────────────────────────────────────────────────
class Visualizer2D(QtWidgets.QWidget):
    """Split window: camera feed (left, half) + 2-D CoP plot (right, half)."""

    def __init__(self, bos_estimator, parent=None):
        super().__init__(parent)
        self.bos = bos_estimator
        self.setWindowTitle("MOBBO – 2D CoP View")

        # Full-screen size, two equal halves
        screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
        W = screen.width()
        H = screen.height()
        self.resize(W, H)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        half_w = W // 2

        # ── left: camera ──────────────────────────────────────────────────────
        self.camera_label = QtWidgets.QLabel()
        self.camera_label.setFixedSize(half_w, H)
        self.camera_label.setStyleSheet("background-color: white;")
        self.camera_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.camera_label)

        # ── right: 2-D plot ───────────────────────────────────────────────────
        self.canvas = _PlotCanvas(bos_estimator)
        self.canvas.setFixedSize(half_w, H)
        layout.addWidget(self.canvas)

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self.canvas.update)
        self._timer.start()

    def camera_update(self, frame):
        if frame is None:
            return
        lbl_w = self.camera_label.width()
        lbl_h = self.camera_label.height()
        rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        # letterbox to fit label exactly
        h0, w0 = rgb.shape[:2]
        scale  = min(lbl_w / w0, lbl_h / h0)
        nw, nh = int(w0 * scale), int(h0 * scale)
        rgb    = cv2.resize(rgb, (nw, nh))
        qi = QtGui.QImage(rgb.data, nw, nh, 3 * nw, QtGui.QImage.Format_RGB888)
        pm = QtGui.QPixmap.fromImage(qi)
        self.camera_label.setPixmap(pm)

    def cop_and_gcop_update(self, cop_and_weight, weight):
        self.canvas._debug_print()
        self.canvas.update()