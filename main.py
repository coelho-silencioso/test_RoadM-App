from PySide6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsScene, QGraphicsView, QWidget, 
    QVBoxLayout, QHBoxLayout, QLabel, QToolButton, QMenuBar, QMenu,
    QSizePolicy, QRubberBand, QComboBox, QCheckBox, QToolBar, QFrame,
    QFileDialog, QMessageBox, QInputDialog, QLineEdit, QPushButton
)
from PySide6.QtCore import Qt, QPointF, QPoint, QTimer, QRectF
from PySide6.QtGui import QPainter, QIcon, QAction, QPainterPath, QColor, QPen, QBrush, QFont
import sys
import logging
import os
import subprocess
from node import Node
from group import Group
from persistence import ProjectPersistence

# Configure logging to output DEBUG-level logs with timestamps
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


class CustomTitleBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_pos = None
        self.setFixedHeight(32)
        # tell Qt to actually paint this widget's background from the stylesheet:
        self.setAttribute(Qt.WA_StyledBackground, True)
        # Set an objectName to target in the stylesheet
        self.setObjectName("titleBar")

        # Layout for title + window controls
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)

        # Window title
        self.title = QLabel("Roadmap `  Mind Map", self)
        layout.addWidget(self.title, 1)

        # Minimize, Maximize, Close buttons
        for icon_name, callback in (
            ("window-minimize", self.parent().showMinimized),
            ("window-maximize", self._toggle_maximize),
            ("window-close", self.parent().close),
        ):
            btn = QToolButton(self)
            btn.setIcon(QIcon.fromTheme(icon_name))
            btn.setAutoRaise(True)
            btn.clicked.connect(callback)
            layout.addWidget(btn)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        if self._drag_pos is not None and e.buttons() & Qt.LeftButton:
            self.window().move(e.globalPosition().toPoint() - self._drag_pos)
            e.accept()

    def mouseReleaseEvent(self, e):
        self._drag_pos = None
        e.accept()

    def _toggle_maximize(self):
        w = self.window()
        if w.isMaximized():
            w.showNormal()
        else:
            w.showMaximized()


class PanZoomView(QGraphicsView):
    def __init__(self, *args, margin=500, min_scale=0.35, max_scale=1.75, **kwargs):
        super().__init__(*args, **kwargs)
        self.margin = margin
        # Zoom limits
        self._min_scale = min_scale
        self._max_scale = max_scale
        # Zoom around mouse
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

        # never rubber-band on left drag
        self.setDragMode(QGraphicsView.NoDrag)
        self.setRubberBandSelectionMode(Qt.ItemSelectionMode.ContainsItemShape)  # This won't be used but set it anyway
        self._panning = False
        self._pan_start = QPointF()

        # Hide scrollbars
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Enable antialiasing for smoother rendering
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Enable context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._showContextMenu)

    def wheelEvent(self, event):
        # Always zoom with mouse wheel, no modifier key required
        factor = 1.15 if event.angleDelta().y() > 0 else 1/1.15

        # Compute current scale from the view's transform
        current_scale = self.transform().m11()  # assuming uniform scaling

        # Clamp: only apply if within limits
        next_scale = current_scale * factor
        if next_scale < self._min_scale or next_scale > self._max_scale:
            return  # ignore zoom beyond bounds

        # Apply the zoom
        self.scale(factor, factor)
        self._ensureSceneMargin()

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            # start panning
            self._panning = True
            self.setCursor(Qt.ClosedHandCursor)
            self._pan_start = event.pos()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning:
            delta = event.pos() - self._pan_start
            # scroll the view by the drag delta
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            self._pan_start = event.pos()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton and self._panning:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
            self._ensureSceneMargin()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # On window resize also ensure margin
        self._ensureSceneMargin()

    def drawForeground(self, painter, rect):
        # First, draw the group hulls
        self._drawGroupHulls(painter, rect)

        # We're not calling the base implementation because it would draw the rubber band
        # super().drawForeground(painter, rect)

    def _drawGroupHulls(self, painter, rect):
        """Draw visual representations of groups as semi-transparent hulls"""
        # Get all nodes in the scene
        nodes = [item for item in self.items() if isinstance(item, Node)]

        # Group nodes by group_id
        grouped_nodes = {}
        for node in nodes:
            if hasattr(node, 'group_id') and node.group_id:
                if node.group_id not in grouped_nodes:
                    grouped_nodes[node.group_id] = []
                grouped_nodes[node.group_id].append(node)

        # Draw a hull for each group
        for group_id, nodes in grouped_nodes.items():
            # Get the group object
            group = Group.get_group_by_id(group_id)
            if not group:
                continue

            # Handle collapsed groups differently
            if not group.expanded:
                self._drawCollapsedGroup(painter, group, nodes)
                continue

            # If there are no nodes in this group, skip
            if not nodes:
                continue

            # When the group is expanded, we don't show the group name text
            # as per the requirement: "When the nodes are not collapsed we can remove the text label from the group text"
            pass

    def _drawCollapsedGroup(self, painter, group, nodes):
        """Draw a badge or icon to represent a collapsed group"""
        # If there are no nodes in this group, skip
        if not nodes:
            return

        # Calculate the center position of all nodes in the group
        center_x = sum(node.pos().x() for node in nodes) / len(nodes)
        center_y = sum(node.pos().y() for node in nodes) / len(nodes)
        center = QPointF(center_x, center_y)

        # Set up the painter for drawing the badge
        painter.save()

        # Use the group's color
        badge_color = QColor(group.color)

        # Draw a circle as the badge
        badge_radius = 30
        badge_rect = QRectF(center.x() - badge_radius, center.y() - badge_radius, 
                           badge_radius * 2, badge_radius * 2)

        # Draw the badge with a solid fill and darker border
        painter.setPen(QPen(badge_color.darker(150), 2))
        painter.setBrush(QBrush(badge_color))
        painter.drawEllipse(badge_rect)

        # Draw the group name inside the badge
        painter.setPen(QPen(Qt.GlobalColor.white))
        font = QFont()
        font.setBold(True)
        font.setPointSize(8)
        painter.setFont(font)

        # Draw the group name centered in the badge
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, group.name)

        # Create the text for node count
        node_count_text = f"{len(nodes)} nodes"

        font.setPointSize(6)
        painter.setFont(font)

        # Draw the node count below the group name
        count_rect = QRectF(badge_rect.left(), badge_rect.center().y(), 
                           badge_rect.width(), badge_rect.height() / 2)
        painter.drawText(count_rect, Qt.AlignmentFlag.AlignCenter, node_count_text)

        painter.restore()

    def getNodesInGroup(self, group_id):
        """Get all nodes in a specific group"""
        return [item for item in self.items() if isinstance(item, Node) and 
                hasattr(item, 'group_id') and item.group_id == group_id]

    def drawItems(self, painter, numItems, items, options):
        # Override to ensure we don't draw the rubber band
        # Call the base implementation but make sure rubber band is not drawn
        super().drawItems(painter, numItems, items, options)

    def drawRubberBand(self, painter, rubberBandRect):
        # Override to prevent rubber band from being drawn
        # Don't call the base implementation
        pass

    def _showContextMenu(self, pos):
        """Show a context menu for the canvas"""
        # Convert view position to scene position
        scene_pos = self.mapToScene(pos)

        # Create the context menu
        menu = QMenu()

        # Add a "Groups" submenu
        groups_menu = menu.addMenu("Groups")

        # Get all groups
        all_groups = Group.get_all_groups()

        # Add actions for each group
        for group in all_groups:
            # Create an action for toggling the group's collapsed state
            action_text = f"{group.name} ({'Expand' if group.collapsed else 'Collapse'})"
            action = QAction(action_text, groups_menu)
            action.triggered.connect(lambda checked, g=group: self._toggleGroupCollapsed(g))
            groups_menu.addAction(action)

        # Show the menu at the cursor position
        menu.exec_(self.mapToGlobal(pos))

    def _toggleGroupCollapsed(self, group):
        """Toggle the collapsed state of a group"""
        # Toggle the expanded state (which handles showing/hiding nodes and badges)
        group.toggle_expanded()

        # Update the scene
        scene = self.scene()
        if scene:
            scene.update()

    def _ensureSceneMargin(self):
        """Grow the sceneRect so that the visible area + margin is always inside it."""
        scene = self.scene()
        if scene is None:
            return

        # Current scene bounds
        srect = scene.sceneRect()

        # What region is currently visible in scene coords?
        vis_rect = self.mapToScene(self.viewport().rect()).boundingRect()

        # Expand srect to include vis_rect plus margin
        expand_rect = vis_rect.adjusted(-self.margin, -self.margin,
                                        self.margin,  self.margin)
        new_rect = srect.united(expand_rect)

        # Only set if we've really grown
        if new_rect != srect:
            scene.setSceneRect(new_rect)


class CanvasScene(QGraphicsScene):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        self.start_node = None

        # Rubber band selection variables
        self.rubber_band = None
        self.rubber_band_origin = None
        self.is_rubber_band_active = False

    def selectStart(self, node):
        """Select a node, then highlight all its descendant connections
        and pull all descendants into one group."""
        if node is None:
            self.logger.debug("Cannot select None node")
            return

        try:
            self.start_node = node

            # 1) Standard selection of the root
            self.clearSelection()
            node.setSelected(True)
            node.bringToFront()            # ← make sure it jumps above everything

            # 2) Highlight every connection in its descendant tree
            #    (mark them selected so they paint with selected_pen)
            from connection import Connection

            try:
                # Get descendants safely
                descendants = set()
                try:
                    descendants = node.descendants()
                except Exception as e:
                    self.logger.debug(f"Error getting descendants: {str(e)}")

                for item in self.items():
                    if isinstance(item, Connection):
                        # Check if the connection has valid start and end nodes
                        if (not hasattr(item, 'start_node') or item.start_node is None or 
                            not hasattr(item, 'end_node') or item.end_node is None):
                            self.logger.debug("Skipping connection with invalid nodes")
                            continue

                        try:
                            # if either endpoint is in the subtree, select the connection
                            if (item.start_node == node or item.end_node == node):
                                item.setSelected(True)
                            elif descendants and (item.start_node in descendants or item.end_node in descendants):
                                item.setSelected(True)
                            else:
                                item.setSelected(False)
                        except Exception as e:
                            self.logger.debug(f"Error processing connection: {str(e)}")
                            continue
            except Exception as e:
                self.logger.debug(f"Error highlighting connections: {str(e)}")

            # 3) Highlight connections for the node and its descendants
            try:
                import time
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                node_id = id(node)
                count = node.highlight_connections_for_node(node_id, True)
                self.logger.debug(f"[{timestamp}] selectStart: Highlighted {count} connections for node '{node.text}' and its descendants")
            except Exception as e:
                self.logger.debug(f"Error in highlighting connections: {str(e)}")
        except Exception as e:
            self.logger.debug(f"Error in selectStart: {str(e)}")

    def mousePressEvent(self, event):
        # Check if left button was clicked
        if event.button() == Qt.MouseButton.LeftButton:
            # Get the click position
            pos = event.scenePos()
            self.logger.debug(f"Left click at position: ({pos.x()}, {pos.y()})")

            # Get the item at the click position
            item = self.itemAt(pos, self.views()[0].transform())

            # Log whether an item was found
            if item is None:
                self.logger.debug("No item found at click position")
            else:
                self.logger.debug(f"Item found at click position: {type(item).__name__}")

            # Import Connection class here to avoid circular import
            from connection import Connection

            # Check for modifier keys for multi-selection
            modifiers = event.modifiers()
            ctrl_pressed = modifiers & Qt.KeyboardModifier.ControlModifier

            # If it's a Connection, just select it and stop
            if isinstance(item, Connection):
                self.logger.debug(f"Connection selected")
                if not ctrl_pressed:
                    self.clearSelection()
                item.setSelected(True)
                return  # don't fall through to Node logic or "clear everything" logic

            # If the item is a Node or a child of a Node (like QGraphicsTextItem), select it
            node_item = None
            if isinstance(item, Node):
                node_item = item
            elif hasattr(item, 'parentItem') and isinstance(item.parentItem(), Node):
                node_item = item.parentItem()

            if node_item:
                self.logger.debug(f"Node selected: {node_item.text}")

                if ctrl_pressed:
                    # Toggle selection state of this node without affecting others
                    node_item.setSelected(not node_item.isSelected())

                    # If this node is now selected, make it the start_node
                    if node_item.isSelected():
                        self.start_node = node_item
                    elif self.start_node == node_item:
                        self.start_node = None

                    self.logger.debug(f"Multi-selection mode: Node '{node_item.text}' selection toggled")
                else:
                    # Check if the node is already selected
                    if node_item.isSelected():
                        # If the node is already selected, just make it the start node without clearing other selections
                        self.start_node = node_item
                        node_item.bringToFront()
                        self.logger.debug(f"Node '{node_item.text}' already selected, making it the start node without clearing other selections")
                    else:
                        # Single selection mode - clear other selections and select this node
                        self.selectStart(node_item)
                        self.logger.debug(f"Single selection mode: Node '{node_item.text}' selected as start")
            else:
                # If clicking on empty space, start rubber band selection or clear selection
                if not ctrl_pressed:
                    self.clearSelection()
                    if self.start_node:
                        self.start_node = None
                        self.logger.debug("Cleared start node selection")

                    # Unhighlight all connections when clicking on empty space
                    for item in self.items():
                        if isinstance(item, Connection):
                            item.setSelected(False)
                    self.logger.debug("Unhighlighted all connections")

                # Initialize rubber band selection
                view = self.views()[0]
                self.rubber_band_origin = pos

                # Create rubber band if it doesn't exist
                if self.rubber_band is None:
                    self.rubber_band = QRubberBand(QRubberBand.Rectangle, view.viewport())

                # Convert scene coordinates to view coordinates
                view_pos = view.mapFromScene(pos)
                self.rubber_band.setGeometry(view_pos.x(), view_pos.y(), 0, 0)
                self.rubber_band.show()
                self.is_rubber_band_active = True
                self.logger.debug(f"Started rubber band selection at {pos.x()}, {pos.y()}")

        # Call the parent class implementation for other cases
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move events for rubber band selection"""
        if self.is_rubber_band_active and self.rubber_band and self.rubber_band_origin:
            # Get the current position
            current_pos = event.scenePos()

            # Get the view
            view = self.views()[0]

            # Convert scene coordinates to view coordinates
            origin_view_pos = view.mapFromScene(self.rubber_band_origin)
            current_view_pos = view.mapFromScene(current_pos)

            # Calculate the rectangle for the rubber band
            rect = QRectF(
                min(origin_view_pos.x(), current_view_pos.x()),
                min(origin_view_pos.y(), current_view_pos.y()),
                abs(current_view_pos.x() - origin_view_pos.x()),
                abs(current_view_pos.y() - origin_view_pos.y())
            )

            # Update the rubber band geometry
            self.rubber_band.setGeometry(rect.toRect())
            self.logger.debug(f"Updated rubber band to {rect.x()}, {rect.y()}, {rect.width()}, {rect.height()}")

        # Call the parent class implementation
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release events for rubber band selection"""
        if event.button() == Qt.MouseButton.LeftButton and self.is_rubber_band_active and self.rubber_band:
            # Get the final rubber band rectangle in scene coordinates
            view = self.views()[0]
            rect = self.rubber_band.geometry()
            scene_rect = QRectF(
                view.mapToScene(rect.topLeft()),
                view.mapToScene(rect.bottomRight())
            )

            # Check for modifier keys
            modifiers = event.modifiers()
            ctrl_pressed = modifiers & Qt.KeyboardModifier.ControlModifier

            # If not adding to selection (Ctrl not pressed), clear current selection
            if not ctrl_pressed:
                self.clearSelection()
                if self.start_node:
                    self.start_node = None

            # Find all nodes that intersect with the rubber band rectangle
            selected_nodes = []
            for item in self.items(scene_rect):
                if isinstance(item, Node):
                    item.setSelected(True)
                    selected_nodes.append(item)
                elif hasattr(item, 'parentItem') and isinstance(item.parentItem(), Node):
                    parent_node = item.parentItem()
                    if parent_node not in selected_nodes:  # Avoid duplicates
                        parent_node.setSelected(True)
                        selected_nodes.append(parent_node)

            # Log the selection
            self.logger.debug(f"Rubber band selection completed: {len(selected_nodes)} nodes selected")

            # Hide the rubber band
            self.rubber_band.hide()
            self.is_rubber_band_active = False

            # If we selected exactly one node, make it the start node
            if len(selected_nodes) == 1 and not ctrl_pressed:
                self.start_node = selected_nodes[0]
                self.logger.debug(f"Set start node to {self.start_node.text}")

        # Reset rubber band state
        self.is_rubber_band_active = False

        # Call the parent class implementation
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        # Accept the event up front
        event.accept()

        # Check if left button was double-clicked
        if event.button() != Qt.MouseButton.LeftButton:
            # If it's not a left button double-click, don't create a node
            self.logger.debug(f"Ignoring non-left button double-click")
            return

        # Get the click positions in different coordinate systems
        screen_pos = event.screenPos()
        view_pos = event.pos()
        scene_pos = event.scenePos()

        # Check if there's already an item at the clicked position
        item = self.itemAt(scene_pos, self.views()[0].transform())

        # Import Connection class here to avoid circular import
        from connection import Connection

        # <<< ADD THIS BLOCK >>>
        if isinstance(item, Connection):
            # let the connection itself (or nothing) handle the double-click
            self.logger.debug(f"Double-click on connection detected. Not creating a node.")
            return

        # Log the click positions
        self.logger.debug(f"Canvas double-click detected:")
        self.logger.debug(f"  Screen position: ({screen_pos.x()}, {screen_pos.y()})")
        self.logger.debug(f"  View position: ({view_pos.x()}, {view_pos.y()})")
        self.logger.debug(f"  Scene position: ({scene_pos.x()}, {scene_pos.y()})")

        # Check if there's already a node at the clicked position
        item = self.itemAt(scene_pos, self.views()[0].transform())

        # Import Connection class here to avoid circular import
        from connection import Connection

        # If there's a node, a child of a node, or a connection at the clicked position, don't create a new node
        if isinstance(item, Node) or (hasattr(item, 'parentItem') and isinstance(item.parentItem(), Node)) or isinstance(item, Connection):
            self.logger.debug(f"Item already exists at this position. Not creating a new node.")
            return

        # If no node or connection exists at the clicked position, create a new one
        self.logger.debug(f"Creating node at position: ({scene_pos.x()}, {scene_pos.y()})")

        # Create a temporary node to calculate dimensions
        temp_node = Node("New Node")
        # Set Z-value to 1 to ensure it's drawn above connections (which have Z-value -1)
        temp_node.setZValue(1)
        rect = temp_node.boundingRect()
        half_w, half_h = rect.width() / 2, rect.height() / 2

        # Calculate the standard centered position
        standard_centered = scene_pos - QPointF(half_w, half_h)

        # Apply the 3/4 spacing reduction (move 3/4 of the way from standard_centered to scene_pos)
        # This effectively reduces the spacing by 3/4, making the node closer to the click point
        vector = QPointF(scene_pos.x() - standard_centered.x(), scene_pos.y() - standard_centered.y())
        reduced_spacing = QPointF(
            standard_centered.x() + vector.x() * 0.75,
            standard_centered.y() + vector.y() * 0.75
        )

        # Position the node with reduced spacing
        temp_node.setPos(reduced_spacing)
        self.addItem(temp_node)
        self.logger.debug(f"New node positioned at {reduced_spacing.x()}, {reduced_spacing.y()} (with 3/4 spacing reduction)")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        logging.debug("Initializing MainWindow")

        # Setup border blinking
        self.is_border_blinking = False
        self._border_blink_timer = QTimer(self)
        self._border_blink_timer.setInterval(1000)  # Slower blink - every 1000ms
        self._border_blink_timer.timeout.connect(self._toggleBorderBlink)

        # Remove native title bar
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        logging.debug("Native title bar removed")

        # Build our own title bar + menu + central
        root = QWidget(self)
        root.setObjectName("rootWidget")
        root.setAttribute(Qt.WA_StyledBackground, True)
        self.setCentralWidget(root)
        vbox = QVBoxLayout(root)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        logging.debug("Root widget and layout created")

        # 1) Custom title bar
        self._title_bar = CustomTitleBar(self)
        vbox.addWidget(self._title_bar, 0)  # no stretch
        logging.debug("Custom title bar added")

        # 2) Menu bar
        menu = QMenuBar(self)
        menu.setObjectName("menuBar")
        menu.setAttribute(Qt.WA_StyledBackground, True)

        # File menu
        file_menu = menu.addMenu("File")
        file_menu.addAction(QAction("New Node", self))

        # Add Save action
        save_action = QAction("Save Project...", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._saveProject)
        file_menu.addAction(save_action)

        # Add Load action
        load_action = QAction("Load Project...", self)
        load_action.setShortcut("Ctrl+O")
        load_action.triggered.connect(self._loadProject)
        file_menu.addAction(load_action)

        # Add separator
        file_menu.addSeparator()

        # Add GitHub submenu
        github_menu = file_menu.addMenu("GitHub")

        # Add Commit and Push action
        commit_push_action = QAction("Commit and Push", self)
        commit_push_action.triggered.connect(self._githubCommitAndPush)
        github_menu.addAction(commit_push_action)

        # Add Configure Repository action
        config_repo_action = QAction("Configure Repository", self)
        config_repo_action.triggered.connect(self._configureGitHubRepo)
        github_menu.addAction(config_repo_action)

        # Add separator
        file_menu.addSeparator()

        # Add Exit action
        file_menu.addAction(QAction("Exit", self, triggered=self.close))

        # Edit menu
        edit_menu = menu.addMenu("Edit")
        edit_menu.addAction(QAction("Undo", self))

        vbox.addWidget(menu, 0)  # no stretch
        logging.debug("Menu bar added")

        # 3) Toolbar for filtering and search
        toolbar = QToolBar("Filtering Toolbar")
        toolbar.setObjectName("filterToolbar")
        toolbar.setMovable(False)

        # Add a separator and label for the tag filter
        toolbar.addWidget(QLabel("Filter by Tag:"))

        # Add a button for tag filtering
        self.tag_filter_button = QPushButton("Show/Hide Tags")
        self.tag_filter_button.setMinimumWidth(150)
        self.tag_filter_button.clicked.connect(self._showTagFilterMenu)
        toolbar.addWidget(self.tag_filter_button)

        # Initialize tag visibility tracking
        self.visible_tags = set()  # Empty set means all tags are visible
        self.all_tags_visible = True

        # Add a separator
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)
        toolbar.addWidget(separator)

        # Add a label for the group visibility
        toolbar.addWidget(QLabel("Show/Hide Groups:"))

        # Add a button for group visibility
        self.group_visibility_button = QPushButton("Show/Hide Groups")
        self.group_visibility_button.setMinimumWidth(150)
        self.group_visibility_button.clicked.connect(self._showGroupVisibilityMenu)
        toolbar.addWidget(self.group_visibility_button)

        # Initialize group visibility tracking
        self.visible_groups = set()  # Empty set means all groups are visible
        self.all_groups_visible = True

        # Add the toolbar to the layout
        vbox.addWidget(toolbar, 0)  # no stretch
        logging.debug("Filtering toolbar added")

        # 3) Create graphics scene and view
        self.scene = CanvasScene()
        logging.debug("GraphicsScene created")

        self.view = PanZoomView(self.scene)
        logging.debug("PanZoomView created")
        logging.debug("Scene assigned to view")

        # Make the view expand to fill its container
        self.view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        logging.debug("View size policy set to Expanding")

        # Align scene origin to top-left of the view
        self.view.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        logging.debug("View alignment set to top-left")

        # Set an initial scene rectangle - InfiniteView will dynamically expand it as needed
        self.scene.setSceneRect(0, 0, 1000, 1000)
        logging.debug("Initial scene rectangle set to (0,0,1000,1000) - will be dynamically expanded by InfiniteView")

        # Enable context menus on the view
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
        logging.debug("Context menus enabled on view")

        # Add the view to the layout with stretch factor 1 (takes all remaining space)
        vbox.addWidget(self.view, 1)
        logging.debug("View added to layout with stretch factor 1")

        # Antialiasing is already enabled in the InfiniteView class
        logging.debug("Antialiasing already enabled in InfiniteView")

        # Apply initial stylesheet
        self._toggleBorderBlink()
        logging.debug("Initial stylesheet applied")

        # Resize the window
        self.resize(1200, 800)
        logging.debug("Window resized to 1200×800")

    def _toggleBorderBlink(self):
        """Toggle the border color between default and lighter blue"""
        self.is_border_blinking = not self.is_border_blinking

        # Get the application instance
        app = QApplication.instance()
        if not app:
            return

        # Update the border color in the application stylesheet
        if self.is_border_blinking:
            # Use lighter blue for the "on" phase
            border_color = "#42A5F5"
            logging.debug("Border blink state: ON (lighter blue)")
        else:
            # Use default blue for the "off" phase
            border_color = "#1E88E5"
            logging.debug("Border blink state: OFF (default blue)")

        # Apply the updated stylesheet with the new border color
        app.setStyleSheet(f"""
            /* border around entire app */
            #rootWidget {{
                border: 4px solid {border_color};
                background: #222;
            }}

            /* title bar */
            #titleBar {{
                background: #1E88E5;
            }}
            #titleBar QLabel,
            #titleBar QToolButton {{
                color: white;
            }}
            #titleBar QToolButton:hover {{
                background: #42A5F5;
            }}

            /* menu bar (file/edit at top) */
            QMenuBar#menuBar {{
                background: #42A5F5;
                color: white;
            }}
            QMenuBar#menuBar::item:selected {{
                background: #1E88E5;
            }}

            /* all QMenu—this covers both the menu-bar's drop-downs *and* any context menus */
            QMenu {{
                background: #1E88E5;      /* match title bar */
                color: white;
                border: none;
                /* optional: rounded corners, padding, etc */
            }}
            QMenu::item:selected {{
                background: #42A5F5;      /* hover state */
                color: black;
            }}
            QMenu::separator {{
                height: 1px;
                background: #42A5F5;
                margin: 4px 0;
            }}
        """)

    def showEvent(self, event):
        """Start the border blinking when the window is shown"""
        super().showEvent(event)
        self._border_blink_timer.start()
        logging.debug("Border blinking started")

        # Update the tag and group dropdowns
        self._updateTagFilter()
        self._updateGroupVisibility()

        # Apply filters to ensure correct visibility
        self._applyTagFilter()
        self._applyGroupFilter()

    def _updateTagFilter(self):
        """Update the tag filter with all tags in the scene"""
        # Get all tags from all nodes in the scene
        all_tags = set()
        for item in self.scene.items():
            if isinstance(item, Node) and hasattr(item, 'tags'):
                all_tags.update(item.tags)

        # If we have visible tags but some are no longer in the scene, remove them
        if self.visible_tags:
            self.visible_tags = self.visible_tags.intersection(all_tags)

        # Update the button text to show the current state
        if self.all_tags_visible:
            self.tag_filter_button.setText("All Tags Visible")
        elif not self.visible_tags:
            self.tag_filter_button.setText("No Tags Visible")
        elif len(self.visible_tags) == 1:
            self.tag_filter_button.setText(f"Tag: {next(iter(self.visible_tags))}")
        else:
            self.tag_filter_button.setText(f"{len(self.visible_tags)} Tags Visible")

    def _updateGroupVisibility(self):
        """Update the group visibility with all groups in the scene"""
        # Get all groups
        all_groups = Group.get_all_groups()

        # Get all group IDs
        all_group_ids = {group.id for group in all_groups}

        # If we have visible groups but some are no longer in the scene, remove them
        if self.visible_groups:
            self.visible_groups = self.visible_groups.intersection(all_group_ids)

        # Update the button text to show the current state
        if self.all_groups_visible:
            self.group_visibility_button.setText("All Groups Visible")
        elif not self.visible_groups:
            self.group_visibility_button.setText("No Groups Visible")
        elif len(self.visible_groups) == 1:
            # Find the group name for the visible group
            group_id = next(iter(self.visible_groups))
            group_name = next((group.name for group in all_groups if group.id == group_id), "Unknown")
            self.group_visibility_button.setText(f"Group: {group_name}")
        else:
            self.group_visibility_button.setText(f"{len(self.visible_groups)} Groups Visible")

    def _showTagFilterMenu(self):
        """Show a menu with checkable actions for each tag"""
        # Create a menu
        menu = QMenu(self)

        # Add "Show All" action
        show_all_action = QAction("Show All Tags", menu, checkable=True)
        show_all_action.setChecked(self.all_tags_visible)
        show_all_action.toggled.connect(self._toggleAllTags)
        menu.addAction(show_all_action)

        # Add separator
        menu.addSeparator()

        # Get all tags from all nodes in the scene
        all_tags = set()
        for item in self.scene.items():
            if isinstance(item, Node) and hasattr(item, 'tags'):
                all_tags.update(item.tags)

        # Add checkable actions for each tag
        for tag in sorted(all_tags):
            action = QAction(tag, menu, checkable=True)
            # If all tags are visible, or this tag is in the visible_tags set, check it
            action.setChecked(self.all_tags_visible or tag in self.visible_tags)
            # Connect to a lambda that calls _toggleTagVisibility with the tag name
            action.toggled.connect(lambda checked, t=tag: self._toggleTagVisibility(t, checked))
            menu.addAction(action)

        # Show the menu at the button's position
        menu.exec_(self.tag_filter_button.mapToGlobal(self.tag_filter_button.rect().bottomLeft()))

    def _toggleAllTags(self, checked):
        """Toggle visibility of all tags"""
        self.all_tags_visible = checked

        # If showing all tags, clear the visible_tags set
        if checked:
            self.visible_tags.clear()

        # Update the UI
        self._updateTagFilter()

        # Apply the filter
        self._applyTagFilter()

    def _toggleTagVisibility(self, tag, visible):
        """Toggle visibility of a specific tag"""
        # If we're showing all tags and we're hiding one, switch to specific mode
        if self.all_tags_visible and not visible:
            # Get all tags from all nodes in the scene
            all_tags = set()
            for item in self.scene.items():
                if isinstance(item, Node) and hasattr(item, 'tags'):
                    all_tags.update(item.tags)

            # Add all tags except the one being hidden
            self.visible_tags = all_tags - {tag}
            self.all_tags_visible = False
        # If we're in specific mode
        elif not self.all_tags_visible:
            if visible:
                # Add the tag to the visible set
                self.visible_tags.add(tag)
            else:
                # Remove the tag from the visible set
                self.visible_tags.discard(tag)

        # Update the UI
        self._updateTagFilter()

        # Apply the filter
        self._applyTagFilter()

    def _applyTagFilter(self):
        """Apply the tag filter based on current visibility settings"""
        # First, mark all nodes as not visible
        for item in self.scene.items():
            if isinstance(item, Node):
                item.setVisible(False)

        # If all tags are visible, show all nodes (subject to group filter)
        if self.all_tags_visible:
            # Show all nodes that pass the group filter
            for item in self.scene.items():
                if isinstance(item, Node):
                    # Only set visible if it's not hidden by group filter
                    if self._isNodeVisibleByGroupFilter(item):
                        item.setVisible(True)
        # If specific tags are visible
        elif self.visible_tags:
            # Show only nodes with visible tags (subject to group filter)
            for item in self.scene.items():
                if isinstance(item, Node):
                    # Check if the node has any visible tag
                    has_visible_tag = hasattr(item, 'tags') and any(tag in self.visible_tags for tag in item.tags)
                    # Only set visible if it's not hidden by group filter
                    if has_visible_tag and self._isNodeVisibleByGroupFilter(item):
                        item.setVisible(True)
        # If no tags are visible, all nodes remain hidden

        # Update connections
        self._updateConnectionVisibility()

        # Update the scene
        self.scene.update()

    def _isNodeVisibleByGroupFilter(self, node):
        """Check if a node is visible based on the group filter"""
        # If all groups are visible, the node is visible
        if self.all_groups_visible:
            return True

        # If no groups are visible, the node is not visible
        if not self.visible_groups:
            return False

        # Check if the node is in a visible group
        return hasattr(node, 'group_id') and node.group_id in self.visible_groups

    def _updateConnectionVisibility(self):
        """Update connection visibility based on node visibility"""
        from connection import Connection
        for item in self.scene.items():
            if isinstance(item, Connection):
                # Show the connection if both nodes are visible
                start_visible = item.start_node.isVisible()
                end_visible = item.end_node.isVisible()
                item.setVisible(start_visible and end_visible)

    def _showGroupVisibilityMenu(self):
        """Show a menu with checkable actions for each group"""
        # Create a menu
        menu = QMenu(self)

        # Add "Show All" action
        show_all_action = QAction("Show All Groups", menu, checkable=True)
        show_all_action.setChecked(self.all_groups_visible)
        show_all_action.toggled.connect(self._toggleAllGroups)
        menu.addAction(show_all_action)

        # Add separator
        menu.addSeparator()

        # Get all groups
        all_groups = Group.get_all_groups()

        # Add checkable actions for each group
        for group in all_groups:
            action = QAction(group.name, menu, checkable=True)
            # If all groups are visible, or this group is in the visible_groups set, check it
            action.setChecked(self.all_groups_visible or group.id in self.visible_groups)
            # Connect to a lambda that calls _toggleGroupVisibility with the group ID
            action.toggled.connect(lambda checked, g=group.id: self._toggleGroupVisibility(g, checked))
            menu.addAction(action)

        # Show the menu at the button's position
        menu.exec_(self.group_visibility_button.mapToGlobal(self.group_visibility_button.rect().bottomLeft()))

    def _toggleAllGroups(self, checked):
        """Toggle visibility of all groups"""
        self.all_groups_visible = checked

        # If showing all groups, clear the visible_groups set
        if checked:
            self.visible_groups.clear()

        # Update the UI
        self._updateGroupVisibility()

        # Apply the filter
        self._applyGroupFilter()

    def _toggleGroupVisibility(self, group_id, visible):
        """Toggle visibility of a specific group"""
        # If we're showing all groups and we're hiding one, switch to specific mode
        if self.all_groups_visible and not visible:
            # Get all group IDs
            all_groups = Group.get_all_groups()
            all_group_ids = {group.id for group in all_groups}

            # Add all groups except the one being hidden
            self.visible_groups = all_group_ids - {group_id}
            self.all_groups_visible = False
        # If we're in specific mode
        elif not self.all_groups_visible:
            if visible:
                # Add the group to the visible set
                self.visible_groups.add(group_id)
            else:
                # Remove the group from the visible set
                self.visible_groups.discard(group_id)

        # Update the UI
        self._updateGroupVisibility()

        # Apply the filter
        self._applyGroupFilter()

    def _applyGroupFilter(self):
        """Apply the group filter based on current visibility settings"""
        # First, mark all nodes as not visible
        for item in self.scene.items():
            if isinstance(item, Node):
                item.setVisible(False)

        # If all groups are visible, show all nodes (subject to tag filter)
        if self.all_groups_visible:
            # Show all nodes that pass the tag filter
            for item in self.scene.items():
                if isinstance(item, Node):
                    # Only set visible if it's not hidden by tag filter
                    if self._isNodeVisibleByTagFilter(item):
                        item.setVisible(True)
        # If specific groups are visible
        elif self.visible_groups:
            # Show only nodes in visible groups (subject to tag filter)
            for item in self.scene.items():
                if isinstance(item, Node):
                    # Check if the node is in a visible group
                    in_visible_group = hasattr(item, 'group_id') and item.group_id in self.visible_groups
                    # Only set visible if it's not hidden by tag filter
                    if in_visible_group and self._isNodeVisibleByTagFilter(item):
                        item.setVisible(True)
        # If no groups are visible, all nodes remain hidden

        # Update connections
        self._updateConnectionVisibility()

        # Update the scene
        self.scene.update()

    def _isNodeVisibleByTagFilter(self, node):
        """Check if a node is visible based on the tag filter"""
        # If all tags are visible, the node is visible
        if self.all_tags_visible:
            return True

        # If no tags are visible, the node is not visible
        if not self.visible_tags:
            return False

        # Check if the node has any visible tag
        return hasattr(node, 'tags') and any(tag in self.visible_tags for tag in node.tags)

    def _saveProject(self):
        """Save the current project to a file"""
        # Show a file dialog to get the filename
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project",
            os.path.expanduser("~"),
            "JSON Files (*.json);;All Files (*)"
        )

        if not filename:
            return  # User cancelled

        # Add .json extension if not present
        if not filename.lower().endswith('.json'):
            filename += '.json'

        # Save the project
        success = ProjectPersistence.save_project(self.scene, filename)

        # Show a message box to indicate success or failure
        if success:
            QMessageBox.information(
                self,
                "Save Successful",
                f"Project saved to {filename}",
                QMessageBox.StandardButton.Ok
            )
            logging.debug(f"Project saved to {filename}")
        else:
            QMessageBox.critical(
                self,
                "Save Failed",
                "Failed to save the project. See log for details.",
                QMessageBox.StandardButton.Ok
            )
            logging.error("Failed to save the project")

    def _loadProject(self):
        """Load a project from a file"""
        # Show a file dialog to get the filename
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Load Project",
            os.path.expanduser("~"),
            "JSON Files (*.json);;All Files (*)"
        )

        if not filename:
            return  # User cancelled

        # Load the project
        success = ProjectPersistence.load_project(self.scene, filename)

        # Show a message box to indicate success or failure
        if success:
            QMessageBox.information(
                self,
                "Load Successful",
                f"Project loaded from {filename}",
                QMessageBox.StandardButton.Ok
            )
            logging.debug(f"Project loaded from {filename}")

            # Update the tag and group dropdowns
            self._updateTagFilter()
            self._updateGroupVisibility()

            # Apply filters to ensure correct visibility
            self._applyTagFilter()
            self._applyGroupFilter()
        else:
            QMessageBox.critical(
                self,
                "Load Failed",
                "Failed to load the project. See log for details.",
                QMessageBox.StandardButton.Ok
            )
            logging.error("Failed to load the project")

    def _configureGitHubRepo(self):
        """Configure GitHub repository settings"""
        # Get the repository URL
        repo_url, ok = QInputDialog.getText(
            self,
            "Configure GitHub Repository",
            "Enter GitHub repository URL:",
            QLineEdit.Normal,
            "https://github.com/coelho-silencioso/RoadM-App.git"
        )

        if not ok or not repo_url:
            return  # User cancelled or didn't enter a URL

        # Check if the current directory is a git repository
        try:
            subprocess.run(["git", "status"], check=True, capture_output=True)
            is_git_repo = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            is_git_repo = False

        if not is_git_repo:
            # Initialize git repository
            try:
                subprocess.run(["git", "init"], check=True)
                logging.debug("Git repository initialized")
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                QMessageBox.critical(
                    self,
                    "Git Error",
                    f"Failed to initialize git repository: {str(e)}",
                    QMessageBox.StandardButton.Ok
                )
                logging.error(f"Failed to initialize git repository: {str(e)}")
                return

        # Configure remote repository
        try:
            # Check if remote already exists
            result = subprocess.run(["git", "remote"], check=True, capture_output=True, text=True)

            if "origin" in result.stdout:
                # Update existing remote
                subprocess.run(["git", "remote", "set-url", "origin", repo_url], check=True)
                logging.debug(f"Updated remote 'origin' to {repo_url}")
            else:
                # Add new remote
                subprocess.run(["git", "remote", "add", "origin", repo_url], check=True)
                logging.debug(f"Added remote 'origin' with URL {repo_url}")

            QMessageBox.information(
                self,
                "GitHub Repository Configured",
                f"Repository configured with URL: {repo_url}",
                QMessageBox.StandardButton.Ok
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            QMessageBox.critical(
                self,
                "Git Error",
                f"Failed to configure remote repository: {str(e)}",
                QMessageBox.StandardButton.Ok
            )
            logging.error(f"Failed to configure remote repository: {str(e)}")

    def _githubCommitAndPush(self):
        """Commit and push changes to GitHub"""
        # Check if git is installed
        try:
            subprocess.run(["git", "--version"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            QMessageBox.critical(
                self,
                "Git Not Found",
                "Git is not installed or not in the PATH. Please install Git and try again.",
                QMessageBox.StandardButton.Ok
            )
            return

        # Check if the current directory is a git repository
        try:
            subprocess.run(["git", "status"], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            # Not a git repository, prompt to configure
            reply = QMessageBox.question(
                self,
                "Git Repository Not Found",
                "This directory is not a git repository. Would you like to configure it now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                self._configureGitHubRepo()
            return

        # Get the commit message
        commit_msg, ok = QInputDialog.getText(
            self,
            "Commit Changes",
            "Enter commit message:",
            QLineEdit.Normal,
            "Update roadmap"
        )

        if not ok or not commit_msg:
            return  # User cancelled or didn't enter a message

        try:
            # Add all files
            subprocess.run(["git", "add", "."], check=True)
            logging.debug("Added all files to git staging area")

            # Commit changes
            subprocess.run(["git", "commit", "-m", commit_msg], check=True)
            logging.debug(f"Committed changes with message: {commit_msg}")

            # Push to remote
            push_result = subprocess.run(
                ["git", "push", "origin", "master"], 
                capture_output=True, 
                text=True
            )

            # Check if push failed due to branch name (master vs main)
            if push_result.returncode != 0 and "master" in push_result.stderr:
                # Try with 'main' branch instead
                push_result = subprocess.run(
                    ["git", "push", "origin", "main"], 
                    capture_output=True, 
                    text=True
                )

            if push_result.returncode == 0:
                QMessageBox.information(
                    self,
                    "Push Successful",
                    "Changes successfully pushed to GitHub.",
                    QMessageBox.StandardButton.Ok
                )
                logging.debug("Changes pushed to GitHub")
            else:
                # If push failed, show error message
                QMessageBox.critical(
                    self,
                    "Push Failed",
                    f"Failed to push changes to GitHub: {push_result.stderr}",
                    QMessageBox.StandardButton.Ok
                )
                logging.error(f"Failed to push changes to GitHub: {push_result.stderr}")

        except subprocess.CalledProcessError as e:
            QMessageBox.critical(
                self,
                "Git Error",
                f"Git operation failed: {e.stderr if hasattr(e, 'stderr') else str(e)}",
                QMessageBox.StandardButton.Ok
            )
            logging.error(f"Git operation failed: {e.stderr if hasattr(e, 'stderr') else str(e)}")


if __name__ == "__main__":
    logging.debug("Starting application")

    # Initialize QApplication
    app = QApplication(sys.argv)
    logging.debug("QApplication initialized")

    # Create and show the main window
    window = MainWindow()
    logging.debug("Showing MainWindow")
    window.show()

    # Start the event loop
    logging.debug("Entering event loop")
    sys.exit(app.exec())
