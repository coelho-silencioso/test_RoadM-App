from PySide6.QtWidgets import QGraphicsItem, QWidget, QGraphicsTextItem, QStyleOptionGraphicsItem, QLineEdit, QMenu, QInputDialog, QColorDialog, QMessageBox
from PySide6.QtGui import QPainter, QBrush, QPen, QKeyEvent, QAction, QColor
from PySide6.QtCore import QLineF, QPointF, QEvent, QRectF, Qt, QObject, QTimer
import logging
import time
from connection import Connection
from group import Group
from thought_bubble import ThoughtBubble

# Configure logger for this module
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class Node(QGraphicsItem, QObject):
    def __init__(self, text: str):
        QGraphicsItem.__init__(self)
        QObject.__init__(self)
        self.text = text

        # Track parent-child relationships
        self.parent_nodes = set()  # Nodes that are parents of this node
        self.child_nodes = set()   # Nodes that are children of this node

        # Tags and group membership
        self.tags = set()          # Set of tags assigned to this node
        self.group_id = None       # Group this node belongs to (None if not in a group)

        # Track thought bubbles
        self.thoughts = []         # List of thought bubbles attached to this node

        # Create text item as a child
        self.text_item = QGraphicsTextItem(text, self)
        # Set text color to white
        self.text_item.setDefaultTextColor(Qt.GlobalColor.white)

        # Set flags for interaction
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )

        # Create a hidden QLineEdit for editing the text
        # We need to wait until the item is added to a scene before creating the editor
        self.editor = None

        # Selection state attribute
        self.is_selected = False

        # Blinking attributes
        self.is_blinking = False
        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(500)  # Blink every 500ms
        self._blink_timer.timeout.connect(self._toggleBlink)


        logger.debug(f"Node created with text: {text}")

    def startBlinking(self):
        """Start blinking the node border"""
        logger.debug(f"Blinking started on node: {self.text}")
        self.is_blinking = True
        self._blink_timer.start()
        self.update()  # Force an immediate update

    def stopBlinking(self):
        """Stop blinking the node border"""
        logger.debug(f"Blinking stopped on node: {self.text}")
        self._blink_timer.stop()
        self.is_blinking = False
        self.update()  # Force an update to ensure border is in the correct state

    def _toggleBlink(self):
        """Toggle the blinking state and update the node"""
        self.is_blinking = not self.is_blinking
        logger.debug(f"Node {self.text} blink state: {'ON' if self.is_blinking else 'OFF'}")
        self.update()  # Trigger a repaint

    def highlight_connections_for_node(self, node_id=None, highlight=True):
        """
        Highlight all connections between a node and its descendants.

        Args:
            node_id (int, optional): The ID of the node to highlight connections for. If None, uses self.
            highlight (bool, optional): Whether to highlight or unhighlight the connections. Defaults to True.

        Returns:
            int: The number of connections highlighted
        """
        # If node_id is None, use self
        node = self if node_id is None else self

        # Log the operation
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        logger.debug(f"[{timestamp}] highlight_connections_for_node: {'Highlighting' if highlight else 'Unhighlighting'} connections for node '{node.text}' (ID: {id(node)})")

        # Get all descendants
        descendants = self.descendants(node)
        logger.debug(f"[{timestamp}] highlight_connections_for_node: Found {len(descendants)} descendants for node '{node.text}'")

        # Count the number of connections highlighted
        count = 0

        # Find all connections involving descendants
        try:
            for item in node.scene().items():
                if isinstance(item, Connection):
                    # Check if the connection has valid start and end nodes
                    if not hasattr(item, 'start_node') or item.start_node is None or not hasattr(item, 'end_node') or item.end_node is None:
                        logger.debug(f"[{timestamp}] highlight_connections_for_node: Skipping connection with invalid nodes")
                        continue

                    try:
                        # Check if this connection involves the node or a descendant
                        if (item.start_node == node or item.end_node == node or 
                            item.start_node in descendants or item.end_node in descendants):
                            # Apply highlight effect to the connection
                            if highlight:
                                # Create a custom highlight pen - bright cyan with increased width
                                highlight_pen = QPen(QColor("#00E5FF"), 4)  # Bright cyan, thicker
                                item.pen = highlight_pen
                                logger.debug(f"[{timestamp}] highlight_connections_for_node: Highlighted connection between '{item.start_node.text}' and '{item.end_node.text}'")
                            else:
                                # Restore the default pen based on connection type
                                item.pen = item.strong_pen if item.is_strong else item.default_pen
                                logger.debug(f"[{timestamp}] highlight_connections_for_node: Unhighlighted connection between '{item.start_node.text}' and '{item.end_node.text}'")

                            # Update the connection
                            item.update()
                            count += 1
                    except (RuntimeError, AttributeError) as e:
                        logger.debug(f"[{timestamp}] highlight_connections_for_node: Error processing connection: {str(e)}")
                        continue
        except Exception as e:
            logger.debug(f"[{timestamp}] highlight_connections_for_node: Error highlighting connections: {str(e)}")
            return 0

        logger.debug(f"[{timestamp}] highlight_connections_for_node: {'Highlighted' if highlight else 'Unhighlighted'} {count} connections for node '{node.text}'")
        return count

    def _update_descendant_connections_glow(self, glow_on):
        """Make connections to all descendants glow when this node is selected"""
        if not self.scene():
            return

        # Use the new highlight_connections_for_node function
        import time
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        logger.debug(f"[{timestamp}] _update_descendant_connections_glow: {'Applying' if glow_on else 'Removing'} glow effect to connections for node '{self.text}'")

        count = self.highlight_connections_for_node(id(self), glow_on)

        logger.debug(f"[{timestamp}] _update_descendant_connections_glow: {'Applied' if glow_on else 'Removed'} glow effect to {count} connections for node '{self.text}'")

    def updateConnections(self):
        """Update all connections attached to this node"""
        if not self.scene():
            return

        # Find all items in the scene
        for item in self.scene().items():
            # Check if the item is a Connection
            if isinstance(item, Connection):
                # Check if this node is either the start or end node of the connection
                if item.start_node == self or item.end_node == self:
                    # Update the connection's position
                    item.updatePosition()
                    logger.debug(f"Updated connection between '{item.start_node.text}' and '{item.end_node.text}'")

    def bringToFront(self):
        """Bring this node to the front of all other items in the scene"""
        if not self.scene():
            return

        # Look at every item in the scene, find the current maximum z
        max_z = max((item.zValue() for item in self.scene().items()), default=0)
        # Bump this node above it
        self.setZValue(max_z + 1)
        logger.debug(f"Bringing node '{self.text}' to front with z-value {max_z + 1}")

    def itemChange(self, change, value):
        # Handle selection change
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedChange:
            # If the node is being selected, bring it to the front
            if value:
                self.bringToFront()
                # Start blinking when selected
                self.startBlinking()
            else:
                # Stop blinking when deselected
                self.stopBlinking()

            # Propagate selection state to connections
            if self.scene():
                for item in self.scene().items():
                    if isinstance(item, Connection) and (item.start_node is self or item.end_node is self):
                        item.setSelected(value)

                # Make connections to all descendants glow when this node is selected
                self._update_descendant_connections_glow(value)

        # Handle position change for updating connections
        elif change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # Update all connections attached to this node
            self.updateConnections()

            # Update group if this node is part of a group
            # Note: We no longer create spines, but we keep the call for backward compatibility
            if hasattr(self, 'group_id') and self.group_id:
                group = Group.get_group_by_id(self.group_id)
                if group:
                    group.update_spines()

            # Update positions of thought bubbles when node moves
            if hasattr(self, 'thoughts') and self.thoughts:
                import time
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                logger.debug(f"[{timestamp}] Node '{self.text}' moved, updating {len(self.thoughts)} thought bubbles")
                self._repositionThoughts()

        # everything else: let the default behavior run
        return super().itemChange(change, value)

    def contextMenuEvent(self, event):
        """Handle right-click to show context menu"""
        menu = QMenu()

        # Always include edit action
        edit_action = menu.addAction("Edit Text")
        edit_action.triggered.connect(lambda: self._edit_text())

        # Add Note action
        add_note_action = menu.addAction("Add Note...")
        add_note_action.triggered.connect(lambda: self._add_note())

        # Check if there are multiple nodes selected
        selected_nodes = []
        if self.scene():
            selected_nodes = [item for item in self.scene().selectedItems() if isinstance(item, Node)]

        if len(selected_nodes) > 1:
            # If multiple nodes are selected, add option to delete all selected nodes
            delete_selected_action = menu.addAction(f"Delete Selected Nodes ({len(selected_nodes)})")
            delete_selected_action.triggered.connect(lambda: self._delete_selected_nodes(selected_nodes))

            # Regular delete action for just this node
            delete_action = menu.addAction("Delete This Node Only")
            delete_action.triggered.connect(lambda: self._delete_node())
        else:
            # Regular delete action
            delete_action = menu.addAction("Delete")
            delete_action.triggered.connect(lambda: self._delete_node())

        # If there's a start node selected and it's not this node, add connect action
        if self.scene() and hasattr(self.scene(), 'start_node') and self.scene().start_node and self.scene().start_node != self:
            start_node = self.scene().start_node
            connect_action = menu.addAction(f"Connect to {start_node.text}")
            connect_action.triggered.connect(lambda: self._connect_to_start_node(start_node))

        # Add Tags submenu
        tags_menu = menu.addMenu("Tags...")
        tags_menu.addAction("Add Tag...", lambda: self._promptAddTag())

        # Get all existing tags from all nodes in the scene
        all_tags = set()
        if self.scene():
            for item in self.scene().items():
                if isinstance(item, Node) and hasattr(item, 'tags'):
                    all_tags.update(item.tags)

        # Add checkable actions for existing tags
        for tag in sorted(all_tags):
            act = QAction(tag, tags_menu, checkable=True)
            act.setChecked(tag in self.tags)
            act.toggled.connect(lambda checked, t=tag: self._toggleTag(t, checked))
            tags_menu.addAction(act)

        # Add Groups submenu
        groups_menu = menu.addMenu("Groups...")
        groups_menu.addAction("New Group...", self._promptNewGroup)

        # Get all existing groups
        all_groups = Group.get_all_groups()

        # Add checkable actions for existing groups
        for group in all_groups:
            act = QAction(group.name, groups_menu, checkable=True)
            act.setChecked(self.group_id == group.id)
            act.toggled.connect(lambda checked, g=group: self._toggleGroup(g, checked))
            groups_menu.addAction(act)

        # Show the menu at the event position
        menu.exec_(event.screenPos())

    def _edit_text(self):
        """Edit the node text"""
        # Reuse the existing double-click functionality
        self._create_editor()

        if self.editor:
            # Get the position and size for the editor
            rect = self.boundingRect()
            scene_pos = self.mapToScene(rect.topLeft())
            view = self.scene().views()[0]
            view_pos = view.mapFromScene(scene_pos)

            # Position and resize the editor
            self.editor.setGeometry(
                view_pos.x(), 
                view_pos.y(), 
                rect.width(), 
                rect.height()
            )

            # Set the text and show the editor
            self.editor.setText(self.text)
            self.editor.show()
            self.editor.setFocus()
            self.editor.selectAll()

    def _delete_node(self):
        """Delete the node from the scene"""
        if self.scene():
            logger.debug(f"Deleting node: {self.text}")

            # Find and remove all connections attached to this node
            connections_to_remove = []
            for item in self.scene().items():
                if isinstance(item, Connection):
                    if item.start_node == self or item.end_node == self:
                        connections_to_remove.append(item)

            # Remove the connections and update parent-child relationships
            for conn in connections_to_remove:
                logger.debug(f"Removing connection between '{conn.start_node.text}' and '{conn.end_node.text}'")

                # Update parent-child relationships
                if conn.start_node == self and conn.end_node in self.child_nodes:
                    self.child_nodes.remove(conn.end_node)
                    conn.end_node.parent_nodes.remove(self)
                elif conn.end_node == self and conn.start_node in self.parent_nodes:
                    self.parent_nodes.remove(conn.start_node)
                    conn.start_node.child_nodes.remove(self)

                self.scene().removeItem(conn)

            # Remove this node from all parent and child relationships
            for parent in list(self.parent_nodes):
                if self in parent.child_nodes:
                    parent.child_nodes.remove(self)

            for child in list(self.child_nodes):
                if self in child.parent_nodes:
                    child.parent_nodes.remove(self)

            # Clear our own sets
            self.parent_nodes.clear()
            self.child_nodes.clear()

            # Remove the node itself
            self.scene().removeItem(self)

    def _delete_selected_nodes(self, selected_nodes):
        """Delete multiple selected nodes"""
        if not self.scene() or not selected_nodes:
            return

        logger.debug(f"Deleting {len(selected_nodes)} selected nodes")

        # Make a copy of the list to avoid modification during iteration
        nodes_to_delete = list(selected_nodes)

        # Delete each node
        for node in nodes_to_delete:
            # Skip if the node has already been removed from the scene
            if not node.scene():
                continue

            logger.debug(f"Deleting selected node: {node.text}")

            # Find and remove all connections attached to this node
            connections_to_remove = []
            for item in self.scene().items():
                if isinstance(item, Connection):
                    if item.start_node == node or item.end_node == node:
                        connections_to_remove.append(item)

            # Remove the connections and update parent-child relationships
            for conn in connections_to_remove:
                logger.debug(f"Removing connection between '{conn.start_node.text}' and '{conn.end_node.text}'")

                # Update parent-child relationships
                if conn.start_node == node and conn.end_node in node.child_nodes:
                    node.child_nodes.remove(conn.end_node)
                    conn.end_node.parent_nodes.remove(node)
                elif conn.end_node == node and conn.start_node in node.parent_nodes:
                    node.parent_nodes.remove(conn.start_node)
                    conn.start_node.child_nodes.remove(node)

                self.scene().removeItem(conn)

            # Remove this node from all parent and child relationships
            for parent in list(node.parent_nodes):
                if node in parent.child_nodes:
                    parent.child_nodes.remove(node)

            for child in list(node.child_nodes):
                if node in child.parent_nodes:
                    child.parent_nodes.remove(node)

            # Clear the node's sets
            node.parent_nodes.clear()
            node.child_nodes.clear()

            # Remove the node itself
            self.scene().removeItem(node)

        logger.debug(f"Finished deleting {len(nodes_to_delete)} selected nodes")

    def is_parent_of(self, node):
        """Check if this node is a parent (direct or indirect) of the given node"""
        # Check direct parent relationship
        if self in node.parent_nodes:
            return True

        # Check indirect parent relationship (recursively)
        for parent in node.parent_nodes:
            if self is parent or parent.is_parent_of(self):
                return True

        return False

    def ancestors(self, node):
        """Return a set of every node reachable by following end_node←start_node edges."""
        result = set()
        for item in node.scene().items():
            if isinstance(item, Connection) and item.end_node is node:
                p = item.start_node
                result.add(p)
                result |= self.ancestors(p)
        return result

    def get_all_descendants(self, node_id=None):
        """
        Helper function to gather all descendants of a given node, regardless of when they were created.

        Args:
            node_id (int, optional): The ID of the node to get descendants for. If None, uses self.

        Returns:
            List[int]: A list of node IDs representing all descendants of the given node.
        """
        # If node_id is None, use self
        node = self if node_id is None else self

        # Get all descendants using the descendants method
        descendants_set = self.descendants(node)

        # Convert to a list of node IDs
        descendant_ids = [id(descendant) for descendant in descendants_set]

        # Log the operation
        logger.debug(f"get_all_descendants: Found {len(descendant_ids)} descendants for node '{node.text}'")
        for i, desc_id in enumerate(descendant_ids):
            for desc in descendants_set:
                if id(desc) == desc_id:
                    logger.debug(f"get_all_descendants: Descendant {i+1}: '{desc.text}' (ID: {desc_id})")
                    break

        return descendant_ids

    def group_nodes(self, node_id, group_id):
        """
        Assign a group_id to a node and all its descendants.

        Args:
            node_id (int): The ID of the node to assign the group to
            group_id (int): The ID of the group to assign

        Returns:
            bool: True if successful, False otherwise
        """
        # Get the node by ID (in this case, we're using self)
        node = self

        # Log the operation
        logger.debug(f"group_nodes: Assigning group_id={group_id} to node '{node.text}' (ID: {node_id})")

        # Assign the group_id to the node
        node.group_id = group_id
        logger.debug(f"group_nodes: Assigned group_id={group_id} to node '{node.text}'")

        # Get all descendants
        descendant_ids = self.get_all_descendants(node_id)
        logger.debug(f"group_nodes: Found {len(descendant_ids)} descendants for node '{node.text}'")

        # Get the group
        group = Group.get_group_by_id(group_id)
        if not group:
            logger.debug(f"group_nodes: Group with ID {group_id} not found")
            return False

        # Add the node to the group
        group.add_member(node, node.scene())
        logger.debug(f"group_nodes: Added node '{node.text}' to group '{group.name}'")

        # Assign the group_id to all descendants
        for desc_id in descendant_ids:
            # Find the descendant node
            for item in node.scene().items():
                if isinstance(item, Node) and id(item) == desc_id:
                    descendant = item

                    # Ensure the descendant has a group_id attribute
                    if not hasattr(descendant, 'group_id'):
                        logger.debug(f"group_nodes: Descendant '{descendant.text}' has no group_id attribute, adding it")
                        descendant.group_id = None

                    # Assign the group_id to the descendant
                    descendant.group_id = group_id
                    logger.debug(f"group_nodes: Assigned group_id={group_id} to descendant '{descendant.text}'")

                    # Add the descendant to the group
                    group.add_member(descendant, node.scene())
                    logger.debug(f"group_nodes: Added descendant '{descendant.text}' to group '{group.name}'")
                    break

        return True

    def descendants(self, node=None):
        """Return a set of every node reachable by following start_node→end_node edges."""
        if node is None:
            node = self
        result = set()
        if node.scene():
            logger.debug(f"Finding descendants for node '{node.text}'")
            for item in node.scene().items():
                if isinstance(item, Connection) and item.start_node is node:
                    child = item.end_node
                    logger.debug(f"Found direct child: '{child.text}' for node '{node.text}'")
                    result.add(child)
                    # Recursively find descendants of this child
                    child_descendants = self.descendants(child)
                    logger.debug(f"Found {len(child_descendants)} descendants for child '{child.text}'")
                    result |= child_descendants
        return result

    def _connect_to_start_node(self, start_node):
        """Connect this node to the start node"""
        if self.scene():
            # First, collect all ancestors of start_node
            # If 'self' is already an ancestor of start_node, refuse:
            if self in self.ancestors(start_node):
                # Refuse to connect if it would create a cycle
                logger.debug(f"Refusing to connect {start_node.text} → {self.text}: would make a cycle")
                return

            # 2) Block "skipping" levels:
            #    If `self` is already reachable *from* start_node via any existing path,
            #    and it's not its direct child, refuse.
            descendants = start_node.descendants()
            if self in descendants and self not in start_node.child_nodes:
                logger.debug(f"Refusing to connect {start_node.text} → {self.text}: would skip a generation")
                return

            # We no longer require nodes to have groups to connect them
            # The check for group membership has been removed to allow connections between nodes without groups

            # Create a new connection
            conn = Connection(start_node, self)
            self.scene().addItem(conn)

            # Update parent-child relationships
            start_node.child_nodes.add(self)
            self.parent_nodes.add(start_node)

            # Check if the parent node has a group tag
            if hasattr(start_node, 'group_id') and start_node.group_id:
                # Get the group
                group = Group.get_group_by_id(start_node.group_id)
                if group:
                    # Assign the group tag to this node
                    self.group_id = start_node.group_id
                    logger.debug(f"Inherited group_id={start_node.group_id} from parent node '{start_node.text}'")

                    # Add this node to the group
                    group.add_member(self, self.scene())
                    logger.debug(f"Added node '{self.text}' to group '{group.name}' inherited from parent")

            # Deselect the start node using the standard selection mechanism
            start_node.setSelected(False)

            # Clear the start_node property in the scene
            if hasattr(self.scene(), 'start_node'):
                self.scene().start_node = None
                logger.debug("Cleared start node selection")

            # Log the connection
            logger.debug(f"Connected {start_node.text} → {self.text} (parent → child)")

    def _create_editor(self):
        """Create the line edit if it doesn't exist yet"""
        if self.editor is None and self.scene() and self.scene().views():
            view = self.scene().views()[0]
            self.editor = QLineEdit(view.viewport())
            self.editor.setWindowFlags(Qt.WindowType.FramelessWindowHint)
            self.editor.hide()
            self.editor.editingFinished.connect(self._editing_finished)
            self.editor.installEventFilter(self)

    def eventFilter(self, obj, event):
        """Handle escape key press to cancel editing"""
        if obj == self.editor and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self.editor.hide()
                return True
        return super().eventFilter(obj, event)

    def _editing_finished(self):
        """Handle the editing finished signal"""
        if self.editor and self.editor.isVisible():
            new_text = self.editor.text()
            if new_text != self.text:
                self.text = new_text
                self.text_item.setPlainText(new_text)
                logger.debug(f"Node text changed to: {new_text}")
            self.editor.hide()

    def _promptAddTag(self):
        """Show a dialog to add a new tag"""
        if not self.scene():
            return

        tag, ok = QInputDialog.getText(None, "Add Tag", "Enter a new tag:")
        if ok and tag:
            # Add the tag to this node
            self.tags.add(tag)
            logger.debug(f"Added tag '{tag}' to node '{self.text}'")
            self.update()  # Redraw the node to show the tag

    def _toggleTag(self, tag, checked):
        """Toggle a tag on or off"""
        if checked:
            # Add the tag
            self.tags.add(tag)
            logger.debug(f"Added tag '{tag}' to node '{self.text}'")
        else:
            # Remove the tag
            if tag in self.tags:
                self.tags.remove(tag)
                logger.debug(f"Removed tag '{tag}' from node '{self.text}'")

        self.update()  # Redraw the node to update the tags display

    def _promptNewGroup(self):
        """Show a dialog to create a new group"""
        if not self.scene():
            return

        # Prompt for group name
        group_name, ok = QInputDialog.getText(None, "New Group", "Enter group name:")
        if not ok or not group_name:
            return

        # Prompt for group color
        color = QColorDialog.getColor(QColor("#3F51B5"), None, "Choose Group Color")
        if not color.isValid():
            return

        # Create the new group with this node as the anchor
        group = Group(group_name, color, self)

        # Assign this node to the group
        self.group_id = group.id
        logger.debug(f"Created new group '{group_name}' and assigned node '{self.text}' as anchor")

        # Create the cluster badge on the anchor
        group._create_cluster_badge(self.scene())

        # Add all descendants to the group as well
        logger.debug(f"Finding descendants of node '{self.text}'")
        descendants = self.descendants()
        logger.debug(f"Found {len(descendants)} descendants for node '{self.text}'")

        for descendant in descendants:
            logger.debug(f"Processing descendant '{descendant.text}'")
            # Ensure the descendant has a group_id attribute
            if not hasattr(descendant, 'group_id'):
                logger.debug(f"Descendant '{descendant.text}' has no group_id attribute, adding it")
                descendant.group_id = None

            # Set the group_id on the descendant
            descendant.group_id = group.id
            logger.debug(f"Set group_id={group.id} on descendant '{descendant.text}'")

            # Add the descendant to the group's members
            group.add_member(descendant, self.scene())
            logger.debug(f"Added descendant node '{descendant.text}' to group '{group.name}'")

        # Update the scene to show the group
        if self.scene():
            self.scene().update()

    def _toggleGroup(self, group, checked):
        """Toggle group membership"""
        if checked:
            # Add to group
            self.group_id = group.id
            logger.debug(f"Added node '{self.text}' to group '{group.name}'")

            # Add this node to the group's members and create badge
            # Note: We no longer create spines, only badges
            group.add_member(self, self.scene())

            # Add all descendants to the group as well
            logger.debug(f"Finding descendants of node '{self.text}'")
            descendants = self.descendants()
            logger.debug(f"Found {len(descendants)} descendants for node '{self.text}'")

            for descendant in descendants:
                logger.debug(f"Processing descendant '{descendant.text}'")
                # Ensure the descendant has a group_id attribute
                if not hasattr(descendant, 'group_id'):
                    logger.debug(f"Descendant '{descendant.text}' has no group_id attribute, adding it")
                    descendant.group_id = None

                # Check if the descendant already has the correct group_id
                if descendant.group_id != group.id:
                    # Set the group_id on the descendant
                    descendant.group_id = group.id
                    logger.debug(f"Set group_id={group.id} on descendant '{descendant.text}'")

                    # Add the descendant to the group's members
                    group.add_member(descendant, self.scene())
                    logger.debug(f"Added descendant node '{descendant.text}' to group '{group.name}'")
                else:
                    logger.debug(f"Descendant '{descendant.text}' already has group_id: {descendant.group_id}")
        else:
            # Remove from group
            if self.group_id == group.id:
                self.group_id = None
                logger.debug(f"Removed node '{self.text}' from group '{group.name}'")

                # Remove this node from the group's members and remove badge
                # Note: We no longer create spines, only badges
                group.remove_member(self, self.scene())

        # Update the scene to reflect group changes
        if self.scene():
            self.scene().update()

    def addThought(self, text):
        """Add a thought bubble to the node and track it"""
        if not self.scene():
            return

        # Create the thought bubble
        bubble = ThoughtBubble(self, text)

        # Set Z-value to be higher than connections (-1) but lower than node text
        # Node has Z-value of 1, so set bubble to 0.5
        bubble.setZValue(self.zValue() - 0.5)

        # Add the bubble to our list
        self.thoughts.append(bubble)

        # Reposition all thought bubbles
        self._repositionThoughts()

        logger.debug(f"Added thought bubble to node '{self.text}' with text: {text}")

        return bubble

    def _repositionThoughts(self, min_padding=ThoughtBubble.DEFAULT_MIN_PADDING, 
                          angle_spread=ThoughtBubble.DEFAULT_ANGLE_SPREAD):
        """
        Fan out thoughts around the top of this node with collision avoidance.

        Args:
            min_padding (int): Minimum padding between bubbles
            angle_spread (int): Angle spread in degrees for the fan layout
        """
        import math
        import time

        count = len(self.thoughts)
        if count == 0:
            return

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        logger.debug(f"[{timestamp}] Repositioning {count} thought bubbles for node '{self.text}'")

        # Convert angle_spread from degrees to radians and calculate start/end angles
        half_spread = math.radians(angle_spread / 2)
        # Center the fan above the node (negative y is up)
        center_angle = -math.pi/2  # -90 degrees (straight up)
        start = center_angle - half_spread
        end = center_angle + half_spread

        # Sort bubbles by creation time to ensure consistent ordering
        sorted_bubbles = sorted(self.thoughts, key=lambda b: b.creation_time)

        # First pass: position all bubbles in a fan layout
        for i, bubble in enumerate(sorted_bubbles):
            # Calculate angle based on position in the array
            angle = start + (end-start)*(i/(count-1 if count>1 else 1))

            # Get node bounding rectangle in scene coordinates
            nb = self.sceneBoundingRect()

            # Calculate base distance from node center
            # Use node height, bubble radius, and padding
            # Reduced multiplier from 1.2 to 0.8 to bring bubbles closer to node
            base_dist = nb.height()/2 + bubble.radius*0.8 + min_padding

            # For multiple bubbles, add some radial distance based on index
            # This helps prevent initial overlaps
            if count > 1:
                # Add more distance for bubbles further from the center
                # Reduced multiplier from 2 to 1.5 to keep bubbles closer together
                radial_offset = abs(i - (count-1)/2) * min_padding * 1.5
                dist = base_dist + radial_offset
            else:
                dist = base_dist

            # Calculate position
            x = nb.center().x() + math.cos(angle)*dist
            y = nb.center().y() + math.sin(angle)*dist

            # Set the bubble's position
            bubble.setPos(x, y)

            # Store initial position for logging
            bubble.final_x = x
            bubble.final_y = y
            bubble.padding_used = min_padding

            logger.debug(f"[{timestamp}] Initial position for bubble id={bubble.bubble_id}: ({x:.1f}, {y:.1f}), angle={math.degrees(angle):.1f}°")

        # Second pass: resolve collisions
        # Process bubbles in order, ensuring each one doesn't overlap with previously positioned ones
        processed_bubbles = []

        for bubble in sorted_bubbles:
            # Check and resolve collisions with already processed bubbles
            collision_resolved = bubble.adjust_position_for_collision(processed_bubbles, min_padding)

            if collision_resolved:
                logger.debug(f"[{timestamp}] Collision resolved for bubble id={bubble.bubble_id}, final position: ({bubble.final_x:.1f}, {bubble.final_y:.1f})")
            else:
                logger.debug(f"[{timestamp}] No collision detected for bubble id={bubble.bubble_id}")

            # Add this bubble to the processed list
            processed_bubbles.append(bubble)

        logger.debug(f"[{timestamp}] Completed repositioning {count} thought bubbles for node '{self.text}'")

    def _add_note(self):
        """Add a thought bubble note to the node via dialog"""
        if not self.scene():
            return

        # Prompt for note text
        text, ok = QInputDialog.getText(None, "Add Note", "Enter note text:")
        if ok and text:
            # Use the addThought method to create and track the bubble
            self.addThought(text)

    def mousePressEvent(self, event):
        """Handle mouse press event"""
        # Bring this item above all its siblings
        self.bringToFront()

        # Save the initial position for potential dragging of multiple nodes
        self._drag_start_pos = event.scenePos()

        # Then continue with the default behavior
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Handle mouse move event for dragging multiple nodes"""
        # Only handle if we're selected and there are other selected nodes
        if self.isSelected() and self.scene():
            selected_nodes = [item for item in self.scene().selectedItems() 
                             if isinstance(item, Node) and item is not self]

            if selected_nodes and hasattr(self, '_drag_start_pos'):
                # Calculate the delta from the drag start position
                delta = event.scenePos() - self._drag_start_pos

                # Update the drag start position for the next move event
                self._drag_start_pos = event.scenePos()

                # Move all other selected nodes by the same delta
                for node in selected_nodes:
                    node.setPos(node.pos() + delta)

                    # Update group for each moved node
                    # Note: We no longer create spines, but we keep the call for backward compatibility
                    if hasattr(node, 'group_id') and node.group_id:
                        group = Group.get_group_by_id(node.group_id)
                        if group:
                            group.update_spines()

                logger.debug(f"Moving {len(selected_nodes)} selected nodes along with '{self.text}'")

        # Call the parent implementation to handle the normal dragging behavior
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)

        # look for any other Node we overlap now that we're done dragging
        others = [item for item in self.collidingItems()
                  if isinstance(item, Node) and item is not self]
        if not others:
            return

        other = others[0]
        my_rect    = self.sceneBoundingRect()
        other_rect = other.sceneBoundingRect()
        w, h       = my_rect.width(), my_rect.height()

        # build a dict of named anchors on the other node:
        oc = other_rect.center()
        anchors = {
            # sides:
            'top':    QPointF(oc.x(), other_rect.top()),
            'bottom': QPointF(oc.x(), other_rect.bottom()),
            'left':   QPointF(other_rect.left(),  oc.y()),
            'right':  QPointF(other_rect.right(), oc.y()),
            # corners:
            'topLeft':     other_rect.topLeft(),
            'topRight':    other_rect.topRight(),
            'bottomRight': other_rect.bottomRight(),
            'bottomLeft':  other_rect.bottomLeft(),
        }

        # for each anchor compute the target pos for this node,
        # then pick the one closest to its current pos()
        best_pos = None
        best_dist2 = float('inf')
        cur_pos = self.pos()

        for name, pt in anchors.items():
            if name == 'top':
                cand = QPointF(pt.x() - w/2, pt.y() - h)
            elif name == 'bottom':
                cand = QPointF(pt.x() - w/2, pt.y())
            elif name == 'left':
                cand = QPointF(pt.x() - w, pt.y() - h/2)
            elif name == 'right':
                cand = QPointF(pt.x(), pt.y() - h/2)
            else:
                # true corner-to-corner snapping:
                # other topLeft  →   this bottomRight
                if name == 'topLeft':
                    cand = QPointF(pt.x() - w, pt.y() - h)
                # other topRight → this bottomLeft
                elif name == 'topRight':
                    cand = QPointF(pt.x(),    pt.y() - h)
                # other bottomRight → this topLeft
                elif name == 'bottomRight':
                    cand = QPointF(pt.x(),    pt.y())
                # other bottomLeft → this topRight
                elif name == 'bottomLeft':
                    cand = QPointF(pt.x() - w, pt.y())

            dx = cand.x() - cur_pos.x()
            dy = cand.y() - cur_pos.y()
            dist2 = dx*dx + dy*dy
            if dist2 < best_dist2:
                best_dist2 = dist2
                best_pos = cand

        if best_pos is not None:
            logger.debug(f"Snapping '{self.text}' to anchor at {best_pos}")
            self.setPos(best_pos)

            # Update group after snapping
            # Note: We no longer create spines, but we keep the call for backward compatibility
            if hasattr(self, 'group_id') and self.group_id:
                group = Group.get_group_by_id(self.group_id)
                if group:
                    group.update_spines()

    def mouseDoubleClickEvent(self, event):
        """Handle double-click to edit the node text"""
        logger.debug(f"Editing node: {self.text}")

        # Create the editor if it doesn't exist yet
        self._create_editor()

        if self.editor:
            # Get the position and size for the editor
            rect = self.boundingRect()
            scene_pos = self.mapToScene(rect.topLeft())
            view = self.scene().views()[0]
            view_pos = view.mapFromScene(scene_pos)

            # Position and resize the editor
            self.editor.setGeometry(
                view_pos.x(),
                view_pos.y(),
                rect.width(),
                rect.height()
            )

            # Set the text and show the editor
            self.editor.setText(self.text)
            self.editor.show()
            self.editor.setFocus()
            self.editor.selectAll()


    def boundingRect(self) -> QRectF:
        # Return a rectangle for the node
        return QRectF(0, 0, 150, 50)

    def anchorPoints(self, at_pos: QPointF = None, subdivisions: int = 4) -> list[QPointF]:
        """
        Returns scene-coords of equally spaced anchors along the border.
        subdivisions=N gives you points at t=0,1/N,2/N,...,N/N on each edge.
        """
        if at_pos is None:
            at_pos = self.pos()
        r = self.boundingRect()
        # corners in local coords
        corners = [
            QPointF(r.left(),  r.top()),
            QPointF(r.right(), r.top()),
            QPointF(r.right(), r.bottom()),
            QPointF(r.left(),  r.bottom()),
        ]

        # interpolation helper
        def lerp(p, q, t):
            return QPointF(p.x() + (q.x()-p.x())*t,
                           p.y() + (q.y()-p.y())*t)

        anchors = []
        # walk each edge
        for i in range(4):
            p0 = corners[i]
            p1 = corners[(i+1)%4]
            for k in range(subdivisions+1):
                anchors.append( lerp(p0, p1, k/subdivisions) )

        # shift into scene coords
        return [ at_pos + p for p in anchors ]

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget):
        logger.debug(f"Painting node: {self.text}")

        # Draw a rounded rectangle
        rect = self.boundingRect()

        # Light blue background (#42A5F5) as specified in the requirements
        bg_color = QColor("#42A5F5")
        painter.setBrush(QBrush(bg_color))

        # Change border based on selection and blinking state
        if self.isSelected():
            if self._blink_timer.isActive():
                # Timer is active, use the current blink state
                if self.is_blinking:
                    # In the "on" phase of the blink cycle - use tangerine (#FFA726)
                    painter.setPen(QPen(QColor("#FFA726"), 3))
                else:
                    # In the "off" phase of the blink cycle - use a lighter tangerine
                    painter.setPen(QPen(QColor("#FFCC80"), 3))
            else:
                # Timer is not active, use the default selected state - tangerine
                painter.setPen(QPen(QColor("#FFA726"), 3))  # Thicker tangerine border for selected nodes

            # Draw a "selected" indicator (small circle in top-right corner)
            painter.save()
            # Use the same color as the border for the indicator
            if self._blink_timer.isActive():
                # Timer is active, use the current blink state
                indicator_color = QColor("#FFA726") if self.is_blinking else QColor("#FFCC80")
            else:
                # Timer is not active, use the default selected state
                indicator_color = QColor("#FFA726")
            painter.setBrush(QBrush(indicator_color))
            painter.setPen(QPen(indicator_color, 1))
            indicator_size = 10
            painter.drawEllipse(rect.right() - indicator_size - 5, rect.top() + 5, indicator_size, indicator_size)
            painter.restore()
        else:
            # Darker blue border (#1565C0) for unselected nodes
            painter.setPen(QPen(QColor("#1565C0"), 2))  # Slightly thicker for better visibility

        painter.drawRoundedRect(rect, 10, 10)

        # Position the text item at the center
        text_width = self.text_item.boundingRect().width()
        text_height = self.text_item.boundingRect().height()
        self.text_item.setPos(
            (rect.width() - text_width) / 2,
            (rect.height() - text_height) / 2
        )

        # Draw tags as colored pills at the bottom of the node
        if hasattr(self, 'tags') and self.tags:
            # Save painter state
            painter.save()

            # Define tag pill properties
            pill_height = 16
            pill_spacing = 4
            pill_y = rect.bottom() - pill_height - 5  # 5px from bottom
            pill_x = rect.left() + 5  # Start 5px from left

            # Define tag colors (cycle through these)
            tag_colors = ["#E91E63", "#9C27B0", "#673AB7", "#3F51B5", "#2196F3", 
                         "#009688", "#4CAF50", "#8BC34A", "#CDDC39", "#FFC107"]

            # Draw each tag
            for i, tag in enumerate(sorted(self.tags)):
                # Choose color based on tag index (cycle through colors)
                color_index = i % len(tag_colors)
                pill_color = QColor(tag_colors[color_index])

                # Set up painter for this pill
                painter.setBrush(QBrush(pill_color))
                painter.setPen(QPen(pill_color.darker(120), 1))

                # Calculate pill width based on tag text
                font_metrics = painter.fontMetrics()
                text_width = font_metrics.horizontalAdvance(tag) + 10  # 5px padding on each side
                pill_width = max(30, text_width)  # Minimum width of 30px

                # Draw pill (rounded rectangle)
                pill_rect = QRectF(pill_x, pill_y, pill_width, pill_height)
                painter.drawRoundedRect(pill_rect, 8, 8)

                # Draw tag text
                painter.setPen(QPen(Qt.GlobalColor.white))
                painter.drawText(pill_rect, Qt.AlignmentFlag.AlignCenter, tag)

                # Move x position for next pill
                pill_x += pill_width + pill_spacing

                # If we're about to go off the edge, move to next row
                if pill_x + 30 > rect.right() - 5:  # 30px is minimum pill width, 5px from right edge
                    pill_x = rect.left() + 5
                    pill_y -= pill_height + 2  # Move up for next row with 2px spacing

            # Restore painter state
            painter.restore()
