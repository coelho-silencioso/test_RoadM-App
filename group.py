from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsEllipseItem, QGraphicsTextItem
from PySide6.QtGui import QColor, QPen, QBrush
from PySide6.QtCore import Qt, QLineF, QRectF
import uuid
import logging

class ClusterBadge(QGraphicsEllipseItem):
    """A clickable badge that toggles the expanded state of a group."""
    def __init__(self, x, y, width, height, group, parent=None):
        super().__init__(x, y, width, height, parent)
        self.group = group
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        """Handle mouse press to toggle the group's expanded state."""
        # Toggle the group's expanded state
        self.group.toggle_expanded()

        # Update the scene
        if self.scene():
            self.scene().update()

        # Accept the event to prevent it from propagating
        event.accept()

    def hoverEnterEvent(self, event):
        """Handle hover enter to show a tooltip."""
        state = "Collapse" if self.group.expanded else "Expand"
        self.setToolTip(f"{state} group '{self.group.name}'")
        super().hoverEnterEvent(event)

# Configure logger for this module
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class Group:
    """
    Represents a group of nodes with a name, color, and unique ID.
    Groups can be collapsed/expanded to hide/show their member nodes.
    Groups have an anchor node and member nodes with badges.
    """
    # Class variable to store all groups
    all_groups = {}

    def __init__(self, name, color=None, anchor_node=None):
        """
        Initialize a new group with a name, optional color, and optional anchor node.

        Args:
            name (str): The name of the group
            color (QColor, optional): The color of the group. Defaults to a random color.
            anchor_node (Node, optional): The anchor node for the group. If None, the first node added will be the anchor.
        """
        self.id = str(uuid.uuid4())  # Generate a unique ID for the group
        self.name = name

        # Default colors if none provided
        default_colors = [
            "#F44336", "#E91E63", "#9C27B0", "#673AB7", "#3F51B5", 
            "#2196F3", "#03A9F4", "#00BCD4", "#009688", "#4CAF50",
            "#8BC34A", "#CDDC39", "#FFEB3B", "#FFC107", "#FF9800"
        ]

        # Use provided color or pick a random one
        if color is None:
            import random
            color_str = random.choice(default_colors)
            self.color = QColor(color_str)
        else:
            self.color = color

        # Track if the group is collapsed
        self.expanded = True

        # Track the anchor node and member nodes
        self.anchor = anchor_node
        self.members = set()
        if anchor_node:
            self.members.add(anchor_node)

        # We no longer create spines (lines connecting anchor to members)
        # This attribute is kept for backward compatibility but is not used
        self.spines = []

        # Track badges (visual indicators on member nodes)
        self.badges = []

        # Track the cluster badge (visual indicator on the anchor node)
        self.cluster_badge = None
        self.cluster_text = None

        # Store the group in the class dictionary
        Group.all_groups[self.id] = self

        logger.debug(f"Created group '{name}' with ID {self.id} and color {self.color.name()}")

    @classmethod
    def get_group_by_id(cls, group_id):
        """Get a group by its ID"""
        return cls.all_groups.get(group_id)

    @classmethod
    def get_all_groups(cls):
        """Get all groups"""
        return list(cls.all_groups.values())

    def add_member(self, node, scene=None):
        """
        Add a node to the group.

        Args:
            node: The node to add to the group
            scene: The scene to add visual elements to (optional)
        """
        # Log the node's current group_id
        if hasattr(node, 'group_id'):
            logger.debug(f"Node '{node.text}' has group_id: {node.group_id} before adding to group '{self.name}' (id: {self.id})")
        else:
            logger.debug(f"Node '{node.text}' has no group_id attribute before adding to group '{self.name}' (id: {self.id})")

        # If this is the first node, make it the anchor
        if not self.anchor:
            self.anchor = node
            self.members.add(node)
            logger.debug(f"Set node '{node.text}' as anchor for group '{self.name}'")

            # Create the cluster badge on the anchor
            if scene:
                self._create_cluster_badge(scene)

            return

        # If the node is already a member, do nothing
        if node in self.members:
            logger.debug(f"Node '{node.text}' is already a member of group '{self.name}'")
            return

        # Add the node to the members set
        self.members.add(node)
        logger.debug(f"Added node '{node.text}' to group '{self.name}'")

        # Verify the node's group_id after adding to the group
        if hasattr(node, 'group_id'):
            logger.debug(f"Node '{node.text}' has group_id: {node.group_id} after adding to group '{self.name}' (id: {self.id})")
        else:
            logger.debug(f"Node '{node.text}' still has no group_id attribute after adding to group '{self.name}' (id: {self.id})")

        # Create a badge if a scene is provided
        if scene:
            self._create_badge(node, scene)

    def remove_member(self, node, scene=None):
        """
        Remove a node from the group.

        Args:
            node: The node to remove from the group
            scene: The scene to remove visual elements from (optional)
        """
        # If the node is not a member, do nothing
        if node not in self.members:
            logger.debug(f"Node '{node.text}' is not a member of group '{self.name}'")
            return

        # Remove the node from the members set
        self.members.remove(node)
        logger.debug(f"Removed node '{node.text}' from group '{self.name}'")

        # If the node is the anchor, choose a new anchor or clear the group
        if node == self.anchor:
            if self.members:
                self.anchor = next(iter(self.members))
                logger.debug(f"Set node '{self.anchor.text}' as new anchor for group '{self.name}'")

                # Move the cluster badge to the new anchor
                if scene and self.cluster_badge:
                    self.cluster_badge.setParentItem(self.anchor)
                    self.cluster_text.setParentItem(self.cluster_badge)
            else:
                self.anchor = None
                logger.debug(f"Group '{self.name}' now has no anchor")

                # Remove the cluster badge
                if scene and self.cluster_badge:
                    scene.removeItem(self.cluster_badge)
                    self.cluster_badge = None
                    self.cluster_text = None

        # Remove the badge for this node
        if scene:
            for i, member in enumerate(list(self.members)):
                if member == node:
                    # Remove the badge
                    if i < len(self.badges):
                        scene.removeItem(self.badges[i])
                        self.badges.pop(i)

                    break

    def _create_badge(self, node, scene):
        """
        Create a badge on the node.

        Args:
            node: The node to create a badge for
            scene: The scene to add the badge to
        """
        # Add a badge on the member
        badge = QGraphicsEllipseItem(-8, -8, 16, 16, parent=node)
        badge.setBrush(QBrush(self.color))
        badge.setPen(QPen(self.color.darker(150), 1))

        # Add the first letter of the group name to the badge
        text = QGraphicsTextItem(self.name[0].upper(), parent=badge)
        text.setDefaultTextColor(Qt.GlobalColor.white)
        text.setPos(-4, -6)

        # Set a tooltip with the group name
        badge.setToolTip(self.name)

        self.badges.append(badge)
        logger.debug(f"Created badge on node '{node.text}'")

        # Set visibility based on expanded state
        badge.setVisible(self.expanded)

    def _create_cluster_badge(self, scene):
        """
        Create a cluster badge on the anchor node.

        Args:
            scene: The scene to add the cluster badge to
        """
        # Create a circle as the badge using the ClusterBadge class
        self.cluster_badge = ClusterBadge(-12, -12, 24, 24, self, parent=self.anchor)
        self.cluster_badge.setBrush(QBrush(self.color))
        self.cluster_badge.setPen(QPen(self.color.darker(150), 2))

        # Add the number of members to the badge
        self.cluster_text = QGraphicsTextItem(str(len(self.members)), parent=self.cluster_badge)
        self.cluster_text.setDefaultTextColor(Qt.GlobalColor.white)
        self.cluster_text.setPos(-6, -10)

        # Set a tooltip
        state = "Collapse" if self.expanded else "Expand"
        self.cluster_badge.setToolTip(f"{state} group '{self.name}'")

        logger.debug(f"Created cluster badge on anchor node '{self.anchor.text}'")

    def update_spines(self):
        """
        This method is kept for backward compatibility but does nothing
        since we no longer create spines (line connections) for groups.
        """
        # No-op since we no longer create spines
        pass

    def toggle_expanded(self):
        """Toggle the expanded state of the group and update visibility of members and badges."""
        self.expanded = not self.expanded
        logger.debug(f"Group '{self.name}' is now {'expanded' if self.expanded else 'collapsed'}")

        # Update the cluster badge appearance
        if self.cluster_badge:
            if self.expanded:
                self.cluster_badge.setBrush(QBrush(self.color))
                self.cluster_text.setPlainText(str(len(self.members)))
            else:
                self.cluster_badge.setBrush(QBrush(self.color.lighter(150)))
                self.cluster_text.setPlainText("+")

        # Update visibility of members and badges
        for member in self.members:
            if member != self.anchor:
                member.setVisible(self.expanded)

        for badge in self.badges:
            badge.setVisible(self.expanded)

        # Update visibility of connections to/from collapsed nodes
        if self.anchor and self.anchor.scene():
            from connection import Connection
            for item in self.anchor.scene().items():
                if isinstance(item, Connection):
                    # If connection involves a non-anchor member of this group
                    if ((item.start_node in self.members and item.start_node != self.anchor) or 
                        (item.end_node in self.members and item.end_node != self.anchor)):
                        # Set visibility based on expanded state
                        item.setVisible(self.expanded)
                        logger.debug(f"{'Showing' if self.expanded else 'Hiding'} connection between '{item.start_node.text}' and '{item.end_node.text}'")

        return self.expanded

    def toggle_collapsed(self):
        """Legacy method for backward compatibility."""
        self.expanded = not self.expanded
        logger.debug(f"Group '{self.name}' is now {'expanded' if self.expanded else 'collapsed'}")
        return not self.expanded  # Return collapsed state for backward compatibility
