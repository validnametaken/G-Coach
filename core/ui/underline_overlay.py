"""
G-Coach Grammarly-Style Floating Underline Overlay (Phase 8H)
Draws subtle, wavy red/blue underline indicators directly over detected error words
in active editor windows using transparent, click-through Win32 layered/overlay windows.
"""

from __future__ import annotations
from typing import List, Tuple, Optional
import logging
import platform

logger = logging.getLogger(__name__)

try:
    from PyQt6.QtCore import Qt, QRect, QPoint
    from PyQt6.QtGui import QPainter, QPen, QColor, QPainterPath
    from PyQt6.QtWidgets import QWidget, QApplication
    HAS_PYQT = True
except ImportError:
    HAS_PYQT = False


class UnderlineOverlayWindow(QWidget if HAS_PYQT else object):
    """Transparent click-through overlay window that renders Grammarly-style wavy underlines (red for errors, purple for style/warnings)."""

    def __init__(self, items: List[Tuple[Tuple[int, int, int, int], str]] = None, parent=None):
        if not HAS_PYQT:
            return
        super().__init__(parent)
        self.items = items or [] # List of ((x, y, w, h), category) absolute screen coordinates
        
        # Window flags: Frameless, translucent, click-through (transparent to mouse), always on top
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self._update_geometry()

    def set_items(self, items: List[Tuple[Tuple[int, int, int, int], str]]):
        self.items = items or []
        self._update_geometry()
        self.update()

    def set_rects(self, rects: List[Tuple[int, int, int, int]]):
        """Backward compatibility helper for plain rects (defaulting to error category)."""
        self.set_items([(r, "grammar") for r in rects])

    def _update_geometry(self):
        if not self.items:
            self.setGeometry(0, 0, 1, 1)
            self.hide()
            return

        rects = [item[0] for item in self.items]
        # Compute bounding box covering all underlines
        min_x = min(r[0] for r in rects) - 5
        min_y = min(r[1] for r in rects) - 5
        max_x = max(r[0] + r[2] for r in rects) + 5
        max_y = max(r[1] + r[3] for r in rects) + 15

        self.setGeometry(min_x, min_y, max_x - min_x, max_y - min_y)
        self.show()

    def paintEvent(self, event):
        if not self.items or not HAS_PYQT:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        window_x = self.x()
        window_y = self.y()

        for (rx, ry, rw, rh), category in self.items:
            # Color-code: Red for spelling/grammar errors, Purple/Indigo for style/prose warnings
            cat_lower = (category or "").lower()
            if cat_lower in ("style", "warning", "punctuation", "word_boundary"):
                pen_color = QColor(139, 92, 246, 220) # Purple / Indigo
            else:
                pen_color = QColor(235, 87, 87, 220)  # Soft Red

            pen = QPen(pen_color, 2, Qt.PenStyle.SolidLine)
            painter.setPen(pen)

            # Local coordinates relative to this overlay window
            local_x = rx - window_x
            local_bottom_y = (ry + rh) - window_y

            # Draw wavy / squiggly line across the width of the bounding box
            path = QPainterPath()
            wave_width = 4
            wave_height = 3
            current_x = local_x
            end_x = local_x + max(rw, 10)

            path.moveTo(current_x, local_bottom_y)
            up = True
            while current_x < end_x:
                next_x = min(current_x + wave_width, end_x)
                mid_x = (current_x + next_x) / 2.0
                mid_y = local_bottom_y - wave_height if up else local_bottom_y + wave_height / 2
                path.quadTo(mid_x, mid_y, next_x, local_bottom_y)
                up = not up
                current_x = next_x

            painter.drawPath(path)
