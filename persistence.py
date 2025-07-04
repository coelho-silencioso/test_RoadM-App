import json
import os
import logging
from PySide6.QtCore import QPointF, QRectF
from node import Node
from connection import Connection
from group import Group

# Configure logger for this module
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class ProjectPersistence:
    """
    Handles saving and loading projects to/from JSON files.
    """
    
    @staticmethod
    def save_project(scene, filename):
        """
        Save the current project to a JSON file.
        
        Args:
            scene: The CanvasScene containing the nodes, connections, and groups
            filename: The path to the file to save to
        
        Returns:
            bool: True if the save was successful, False otherwise
        """
        try:
            # Create a dictionary to store the project data
            project_data = {
                "nodes": [],
                "connections": [],
                "groups": []
            }
            
            # Get all nodes in the scene
            nodes = [item for item in scene.items() if isinstance(item, Node)]
            
            # Create a mapping from node objects to their IDs
            node_to_id = {node: i for i, node in enumerate(nodes)}
            
            # Serialize nodes
            for node in nodes:
                node_data = {
                    "id": node_to_id[node],
                    "text": node.text,
                    "pos_x": node.pos().x(),
                    "pos_y": node.pos().y(),
                    "tags": list(node.tags) if hasattr(node, 'tags') else [],
                    "group_id": node.group_id if hasattr(node, 'group_id') else None
                }
                project_data["nodes"].append(node_data)
            
            # Get all connections in the scene
            connections = [item for item in scene.items() if isinstance(item, Connection)]
            
            # Serialize connections
            for connection in connections:
                connection_data = {
                    "start_node_id": node_to_id[connection.start_node],
                    "end_node_id": node_to_id[connection.end_node]
                }
                project_data["connections"].append(connection_data)
            
            # Serialize groups
            for group in Group.get_all_groups():
                group_data = {
                    "id": group.id,
                    "name": group.name,
                    "color": group.color.name(),
                    "collapsed": group.collapsed
                }
                project_data["groups"].append(group_data)
            
            # Write the data to the file
            with open(filename, 'w') as f:
                json.dump(project_data, f, indent=4)
            
            logger.debug(f"Project saved to {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving project: {e}")
            return False
    
    @staticmethod
    def load_project(scene, filename):
        """
        Load a project from a JSON file.
        
        Args:
            scene: The CanvasScene to load the project into
            filename: The path to the file to load from
        
        Returns:
            bool: True if the load was successful, False otherwise
        """
        try:
            # Check if the file exists
            if not os.path.exists(filename):
                logger.error(f"File not found: {filename}")
                return False
            
            # Read the data from the file
            with open(filename, 'r') as f:
                project_data = json.load(f)
            
            # Clear the current scene
            scene.clear()
            
            # Clear the groups
            Group.all_groups.clear()
            
            # Load groups
            for group_data in project_data.get("groups", []):
                group = Group(group_data["name"])
                group.id = group_data["id"]
                group.color = QColor(group_data["color"])
                group.collapsed = group_data["collapsed"]
                Group.all_groups[group.id] = group
            
            # Create a mapping from node IDs to node objects
            id_to_node = {}
            
            # Load nodes
            for node_data in project_data.get("nodes", []):
                node = Node(node_data["text"])
                node.setPos(QPointF(node_data["pos_x"], node_data["pos_y"]))
                
                # Set tags and group_id
                if "tags" in node_data:
                    node.tags = set(node_data["tags"])
                if "group_id" in node_data and node_data["group_id"]:
                    node.group_id = node_data["group_id"]
                
                # Add the node to the scene
                scene.addItem(node)
                
                # Add to the mapping
                id_to_node[node_data["id"]] = node
            
            # Load connections
            for connection_data in project_data.get("connections", []):
                start_node = id_to_node.get(connection_data["start_node_id"])
                end_node = id_to_node.get(connection_data["end_node_id"])
                
                if start_node and end_node:
                    connection = Connection(start_node, end_node)
                    scene.addItem(connection)
                    
                    # Update parent-child relationships
                    start_node.child_nodes.add(end_node)
                    end_node.parent_nodes.add(start_node)
            
            logger.debug(f"Project loaded from {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Error loading project: {e}")
            return False