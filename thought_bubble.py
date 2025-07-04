from PySide6.QtWidgets import QGraphicsItem, QGraphicsTextItem
from PySide6.QtGui import QPainter, QPainterPath, QBrush, QPen, QColor, QFont
from PySide6.QtCore import QRectF, QPointF, Qt
import logging
import time
import uuid

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class ThoughtBubble(QGraphicsItem):
    # Class variable to track global z-order counter
    _z_counter = 0

    # Default layout parameters
    DEFAULT_MIN_PADDING = 10
    DEFAULT_ANGLE_SPREAD = 60  # degrees
    DEFAULT_RADIUS = 60

    def __init__(self, parent_node, text, radius=DEFAULT_RADIUS):
        super().__init__(parent=parent_node)
        self.node = parent_node
        self.radius = radius
        self.bubble_id = str(uuid.uuid4())[:8]  # Generate a unique ID for logging
        self.creation_time = time.time()

        # Store the final position after collision resolution
        self.final_x = 0
        self.final_y = 0
        self.padding_used = 0
        self.collision_adjustments = 0

        # Create text item
        self.text = QGraphicsTextItem(text, parent=self)
        self.text.setTextWidth(radius*1.3)
        self.text.setDefaultTextColor(Qt.black)
        f = self.text.font()
        f.setPointSize(10)
        self.text.setFont(f)

        # Center the text in the upper part of the ellipse
        tb = self.text.boundingRect()
        self.text.setPos(-tb.width()/2, -tb.height()/2 - radius*0.1)

        # Set Z-value to ensure newer bubbles appear on top
        # Increment the class counter and use it for Z-ordering
        ThoughtBubble._z_counter += 1
        self.setZValue(0.5 + ThoughtBubble._z_counter * 0.01)  # Base Z + increment

        # The node will position this bubble using _repositionThoughts
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        logger.debug(f"[{timestamp}] Created thought bubble id={self.bubble_id} for node '{parent_node.text}' with text: {text}, z-value={self.zValue()}")

    def boundingRect(self) -> QRectF:
        r = self.radius
        # Ensure the bounding box covers the main ellipse plus the tail circles
        # and leave extra margin for stroke width
        return QRectF(-r*1.1, -r*0.9, r*2.2, r*1.8)

    def sceneBoundingBox(self):
        """Return the bubble's bounding box in scene coordinates for collision detection"""
        return self.mapToScene(self.boundingRect()).boundingRect()

    def intersects(self, other_bubble):
        """Check if this bubble intersects with another bubble"""
        return self.sceneBoundingBox().intersects(other_bubble.sceneBoundingBox())

    def adjust_position_for_collision(self, other_bubbles, min_padding=DEFAULT_MIN_PADDING):
        """
        Adjust position to avoid collision with other bubbles
        Returns True if position was adjusted, False otherwise
        """
        if not other_bubbles:
            return False

        # Check for collisions
        collisions = [b for b in other_bubbles if self.intersects(b)]
        if not collisions:
            return False

        # Try to resolve by moving radially outward
        original_pos = self.pos()
        node_center = self.node.sceneBoundingRect().center()
        bubble_center = self.sceneBoundingBox().center()

        # Calculate vector from node to bubble
        dx = bubble_center.x() - node_center.x()
        dy = bubble_center.y() - node_center.y()

        # Normalize and scale
        length = (dx**2 + dy**2)**0.5
        if length > 0:
            dx = dx / length
            dy = dy / length

        # Move outward in small increments until no collision
        increment = min_padding
        max_attempts = 10
        attempts = 0

        while attempts < max_attempts:
            attempts += 1
            # Move outward
            new_x = original_pos.x() + dx * increment * attempts
            new_y = original_pos.y() + dy * increment * attempts
            self.setPos(new_x, new_y)

            # Check if still colliding
            if not any(self.intersects(b) for b in other_bubbles):
                self.collision_adjustments += 1
                self.padding_used = increment * attempts
                self.final_x = new_x
                self.final_y = new_y
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                logger.debug(f"[{timestamp}] Adjusted bubble id={self.bubble_id} position to avoid collision. Moved by {increment * attempts} units.")
                return True

        # If we couldn't resolve, revert to original position
        self.setPos(original_pos)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        logger.debug(f"[{timestamp}] Failed to resolve collision for bubble id={self.bubble_id} after {max_attempts} attempts.")
        return False

    def paint(self, painter: QPainter, option, widget):
        r = self.radius
        path = QPainterPath()
        # main cloud:
        path.addEllipse(QPointF(0, 0), r, r*0.7)

        # tail circles:
        path.addEllipse(QPointF(-r*0.4, r*0.5), r*0.18, r*0.18)
        path.addEllipse(QPointF(-r*0.2, r*0.8), r*0.12, r*0.12)

        painter.setBrush(QBrush(QColor("#FFFFE0")))  # light yellow bubble
        painter.setPen(QPen(Qt.black, 1))
        painter.drawPath(path)
