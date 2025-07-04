from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsItem, QMenu, QStyleOptionGraphicsItem
from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui  import QPainter, QPen, QPolygonF, QAction, QColor, QPainterPath
import math, logging

# Configure logger for this module
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class Connection(QGraphicsPathItem):
    def __init__(self, start_node, end_node, is_strong=False):
        super().__init__()
        self.start_node = start_node
        self.end_node = end_node

        # Store path points
        self.start_pos = QPointF()
        self.corner_pos = QPointF()  # The "elbow" point
        self.end_pos = QPointF()

        # Connection type
        self.is_strong = is_strong

        # Define pens for different states
        self.default_pen = QPen(QColor("#B0BEC5"), 2)  # Soft Gray for default
        self.hover_pen = QPen(QColor("#4DB6AC"), 3)    # Muted Teal for hover
        self.selected_pen = QPen(QColor("#FFCA28"), 4) # Warm Amber for selected
        self.strong_pen = QPen(QColor("#1E88E5"), 2)   # Darker Blue for strong connections

        # Set initial pen based on connection type
        self.pen = self.strong_pen if self.is_strong else self.default_pen

        # Enable selection and hover events
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)

        # Set a lower Z-value to ensure the line appears behind nodes
        self.setZValue(-1)

        # Arrow properties
        self.arrow_length = 12
        self.arrow_angle  = math.pi / 6

        # Update the line position
        self.updatePosition()

        logger.debug(f"Connection created from '{start_node.text}' to '{end_node.text}'")

    def boundingRect(self) -> QRectF:
        """Return a rectangle that covers the path plus room for the arrowhead"""
        # Get the base bounding rect from QGraphicsPathItem
        rect = super().boundingRect()

        # Add extra space for the arrowhead
        extra = self.arrow_length + self.pen.widthF()
        return rect.adjusted(-extra, -extra, extra, extra)

    def paint(self, painter: QPainter, option, widget):
        """
        Draw the path and arrowhead; highlight if this connection is directly selected
        *or* if either of its endpoint nodes is selected.
        """
        # determine highlight state
        node_selected = False
        # Check if both nodes still exist and are valid before accessing their properties
        if hasattr(self, 'start_node') and self.start_node is not None and hasattr(self, 'end_node') and self.end_node is not None:
            try:
                node_selected = self.start_node.isSelected() or self.end_node.isSelected()
            except (RuntimeError, AttributeError):
                # Handle case where nodes exist but are in an invalid state
                logger.debug("Error checking node selection state, nodes may be invalid")
                node_selected = False

        conn_selected = self.isSelected()

        if conn_selected or node_selected:
            pen = self.selected_pen
        elif self.isUnderMouse():
            pen = self.hover_pen
        else:
            pen = self.strong_pen if self.is_strong else self.default_pen

        # Set the pen for the path
        self.setPen(pen)

        # Save the current selection state and option
        was_selected = self.isSelected()
        saved_option = QStyleOptionGraphicsItem(option)

        # Temporarily set the item as not selected to prevent the selection rectangle
        if was_selected:
            self.setSelected(False)
            # Modify the option to remove the selection state
            saved_option.state &= ~QStyleOptionGraphicsItem.State.Selected

        # Let the base class draw the path with the modified option
        super().paint(painter, saved_option, widget)

        # Restore the selection state
        if was_selected:
            self.setSelected(True)

        # Compute arrowhead points - use the direction from corner to end
        # This ensures the arrowhead points in the right direction for the vertical segment
        angle = math.atan2(self.end_pos.y() - self.corner_pos.y(),
                           self.end_pos.x() - self.corner_pos.x())
        p1 = self.end_pos
        p2 = QPointF(
            p1.x() - self.arrow_length * math.cos(angle - self.arrow_angle),
            p1.y() - self.arrow_length * math.sin(angle - self.arrow_angle)
        )
        p3 = QPointF(
            p1.x() - self.arrow_length * math.cos(angle + self.arrow_angle),
            p1.y() - self.arrow_length * math.sin(angle + self.arrow_angle)
        )
        painter.setPen(pen)
        painter.setBrush(pen.color())
        painter.drawPolygon(QPolygonF([p1, p2, p3]))

        logger.debug(f"Drawing connection with pen color: {pen.color().name()}")

    def updatePosition(self):
        """Update the path position based on the nodes' positions"""
        self.prepareGeometryChange()

        # 1) grab the two anchor points—here we're using the bounding-rect centers
        p1 = self.start_node.sceneBoundingRect().center()
        p2 = self.end_node.sceneBoundingRect().center()

        # 2) choose an "elbow" point: horizontal then vertical
        # Create a raw corner point
        raw_corner = QPointF(p2.x(), p1.y())

        # Quantize to 20px grid
        GRID = 20
        grid_x = round(raw_corner.x() / GRID) * GRID
        grid_y = round(raw_corner.y() / GRID) * GRID
        self.corner_pos = QPointF(grid_x, grid_y)

        # 3) find the intersection with each node's rect
        def edgePoint(rect: QRectF, line: QLineF) -> QPointF:
            for edge in (
                QLineF(rect.topLeft(),     rect.topRight()),
                QLineF(rect.topRight(),    rect.bottomRight()),
                QLineF(rect.bottomRight(), rect.bottomLeft()),
                QLineF(rect.bottomLeft(),  rect.topLeft())
            ):
                intersect_type, pt = line.intersects(edge)
                if intersect_type == QLineF.BoundedIntersection:
                    return pt
            return line.p1()  # fallback to center

        start_rect = self.start_node.sceneBoundingRect()
        end_rect   = self.end_node.sceneBoundingRect()

        # 4) Find the start point (intersection of horizontal line with start node)
        horizontal_line = QLineF(p1, self.corner_pos)
        raw_start_pos = edgePoint(start_rect, horizontal_line)

        # Quantize the start point to the grid - but only the x-coordinate
        # since we want a perfectly horizontal line
        start_x = round(raw_start_pos.x() / GRID) * GRID
        self.start_pos = QPointF(start_x, self.corner_pos.y())

        # 5) Find the end point (intersection of vertical line with end node)
        vertical_line = QLineF(self.corner_pos, p2)
        raw_end_pos = edgePoint(end_rect, QLineF(p2, self.corner_pos))  # reversed for target

        # Quantize the end point to the grid - but only the y-coordinate
        # since we want a perfectly vertical line
        end_y = round(raw_end_pos.y() / GRID) * GRID
        self.end_pos = QPointF(self.corner_pos.x(), end_y)

        # 6) Build the path
        path = QPainterPath(self.start_pos)
        path.lineTo(self.corner_pos)
        path.lineTo(self.end_pos)
        self.setPath(path)

        # Trigger repaint
        self.update()

        logger.debug(f"Updated connection: start={self.start_pos}, corner={self.corner_pos}, end={self.end_pos}")

    def mousePressEvent(self, event):
        """Handle mouse press events - select this connection on left-click"""
        if event.button() == Qt.LeftButton:
            # Select this connection and stop propagation
            self.setSelected(True)
            event.accept()
            logger.debug(f"Connection clicked and selected")
        else:
            super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu()
        delete_act = menu.addAction("Delete Connection")
        delete_act.triggered.connect(lambda: self._delete())
        menu.exec_(event.screenPos())

    def _delete(self):
        if self.scene():
            logger.debug(f"Deleting connection from '{self.start_node.text}' to '{self.end_node.text}'")

            # Update parent-child relationships
            if hasattr(self.start_node, 'child_nodes') and hasattr(self.end_node, 'parent_nodes'):
                if self.end_node in self.start_node.child_nodes:
                    self.start_node.child_nodes.remove(self.end_node)
                    logger.debug(f"Removed {self.end_node.text} from {self.start_node.text}'s children")

                if self.start_node in self.end_node.parent_nodes:
                    self.end_node.parent_nodes.remove(self.start_node)
                    logger.debug(f"Removed {self.start_node.text} from {self.end_node.text}'s parents")

            self.scene().removeItem(self)

    def hoverEnterEvent(self, event):
        """Handle mouse hover enter event - change to hover pen"""
        if not self.isSelected():  # Only change if not already selected
            self.pen = self.hover_pen
            self.update()
            logger.debug(f"Connection hover enter: changing to teal")
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """Handle mouse hover leave event - revert to default or strong pen"""
        if not self.isSelected():  # Only change if not already selected
            self.pen = self.strong_pen if self.is_strong else self.default_pen
            self.update()
            logger.debug(f"Connection hover leave: reverting to {'strong blue' if self.is_strong else 'default gray'}")
        super().hoverLeaveEvent(event)

    def itemChange(self, change, value):
        """Handle item change events - particularly selection state"""
        if change == QGraphicsItem.ItemSelectedChange:
            if value:  # Being selected
                self.pen = self.selected_pen
                logger.debug(f"Connection selected: changing to amber")
            else:  # Being deselected
                # If mouse is still over the item, use hover pen, otherwise use default/strong
                if self.isUnderMouse():
                    self.pen = self.hover_pen
                    logger.debug(f"Connection deselected but still under mouse: changing to teal")
                else:
                    self.pen = self.strong_pen if self.is_strong else self.default_pen
                    logger.debug(f"Connection deselected: reverting to {'strong blue' if self.is_strong else 'default gray'}")
            self.update()
        return super().itemChange(change, value)
