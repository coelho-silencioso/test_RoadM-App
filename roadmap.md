
# Roadmap Mind Map App Plan

## Project Setup
- [x] Create a PySide6 project skeleton (virtual environment, install dependencies)
- [x] Setup project structure:
  - `main.py`
  - `gui/`
  - `core/`
  - `resources/`

## Core Architecture
- [x] Implement `MainWindow` (subclass of `QMainWindow`)
- [x] Setup `QGraphicsView` and `QGraphicsScene` for the canvas
- [x] Create `Node` class (subclass `QGraphicsItem` with rectangle and text)
- [x] Implement custom title bar with window controls
- [x] Create infinite canvas with dynamic expansion

## Features

### Node Management
- [x] Add node creation (double-click or context menu)
- [x] Drag and drop nodes
- [x] Edit node labels in-place (using `QLineEdit`)
- [x] Delete nodes
- [x] Node selection and highlighting
- [x] Node snapping (side-to-side and corner-to-corner)
- [x] Z-order management (bring to front)

### Connection Management
- [x] Connect nodes (select source, draw line, select target)
- [x] Visualize connections with arrowheads
- [x] Edit and delete connections
- [x] Connection styling with different states (default, hover, selected)
- [x] Strong/weak connection types
- [x] Highlight connections when nodes are selected

### Mind Map Capabilities
- [x] Expand/collapse subtrees
- [x] Grouping and tagging of nodes

### Roadmap Capabilities
- [ ] Integrate a timeline view
- [ ] Add milestones with date properties
- [ ] Export view as image or PDF

## UI/UX Enhancements
- [x] Context menus for canvas and nodes
- [x] Custom styling and theming
- [x] Zoom and pan functionality
- [x] Border blinking effect
- [x] Toolbar with common actions
- [ ] Minimap overview

## Persistence & Data
- [x] Save/load projects (JSON serialization)
- [ ] Autosave feature

## GitHub Integration
- [x] Configure GitHub repository
- [x] Commit and push changes to GitHub
- [x] Detailed instructions for GitHub usage

## Logging & Undo/Redo
- [ ] Implement command pattern for user actions
- [ ] Maintain an undo/redo stack
- [x] Log actions with timestamps and details

## Testing & Documentation
- [x] Error handling and confirmation dialogs
- [ ] Unit tests for core logic
- [ ] User guide and inline documentation

## Development Milestones
- [x] **MVP**: Node creation, drag & drop, label editing
- [x] **Beta**: Connections, custom UI, advanced node interactions
- [ ] **Release**: Full mind map and roadmap feature set, save/load functionality
