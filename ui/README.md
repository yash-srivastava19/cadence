# Cadence UI Visualizer

A simple web-based interface for visualizing evolutionary program synthesis experiments.

## Features

🌐 **Network Visualization**
- Interactive node-link diagram showing program evolution tree
- Node size represents fitness (metric value)
- Color coding by performance
- Drag and zoom capabilities

📊 **Performance Analysis**
- Performance vs generation charts
- Average and best metric tracking
- Multiple metric support

🔍 **Program Inspector**
- Click nodes to view program code
- See diffs and prompts used
- Navigate parent-child relationships

🎯 **Interactive Controls**
- Highlight best performing programs
- Filter by generation
- Center on specific nodes
- Metric selection (cost, feasibility, etc.)

## Quick Start

### 1. Launch the UI
```bash
cd ui
python launch_ui.py
```

### 2. Open Browser
Navigate to: `http://localhost:5000`

### 3. Load Data
The UI automatically loads the latest experiment data from the database.

## UI Components

### Network View Tab
- **Main visualization area**: Interactive evolution tree
- **Sidebar controls**: Metric selection, highlighting, node details
- **Node interaction**: Click to select, drag to move, scroll to zoom

### Performance Tab
- **Line charts**: Average and best performance over generations
- **Trend analysis**: Visual progress tracking

### Code View Tab
- **Source code display**: Full program code for selected node
- **Syntax highlighting**: Easy-to-read code formatting

## Controls

### Sidebar Controls
- **Metric Selection**: Choose which metric to visualize (cost, feasibility)
- **Highlight Controls**:
  - "Best Score": Highlight the best performing program
  - "Generation": Highlight all programs from a specific generation
  - "Clear": Remove all highlighting
- **Selected Node Info**: Details about the currently selected program

### Node Interactions
- **Click**: Select a node to view its details
- **Drag**: Move nodes around (they'll spring back)
- **📍 Locator**: Center the view on the selected node

### Keyboard Shortcuts
- **Mouse wheel**: Zoom in/out
- **Click and drag**: Pan around the visualization

## Data Sources

The UI reads from:
- **SQLite Database**: `cadence_db.sqlite` - Program evolution data
- **Experiment Results**: JSON files from experiments directory
- **Configuration**: Experiment config files

## Troubleshooting

### "No programs found"
- Make sure you've run some experiments first
- Check that `cadence_db.sqlite` exists and has data

### "Import errors"
- Run from the correct directory (ui/ folder)
- Make sure Flask is installed: `pip install flask`

### "Port already in use"
- Change the port in `app.py`: `app.run(port=5001)`
- Or kill the existing process

## Architecture

```
ui/
├── app.py              # Flask backend server
├── launch_ui.py        # Launcher script
├── templates/
│   └── index.html      # Main UI interface
└── README.md           # This file
```

**Backend (Flask)**:
- Serves the web interface
- Provides REST API endpoints
- Reads from SQLite database

**Frontend (HTML/JS)**:
- D3.js for network visualization
- Plotly.js for performance charts
- Vanilla JavaScript for interactions

## API Endpoints

- `GET /` - Main UI page
- `GET /api/programs` - All programs data
- `GET /api/program/<id>` - Specific program details
- `GET /api/metrics` - Available metrics
- `GET /api/performance/<id>` - Performance lineage

## Customization

### Adding New Metrics
1. Add to `get_metrics()` in `app.py`
2. Update database queries if needed
3. Metrics will appear in dropdown automatically

### Styling
- Edit CSS in `templates/index.html`
- Colors, fonts, layout are all customizable

### New Visualizations
- Add new tabs in the HTML
- Implement corresponding JavaScript functions
- Use D3.js or Plotly.js for charts

## Dependencies

- **Python 3.8+**
- **Flask** (auto-installed by launcher)
- **Web browser** with JavaScript enabled

External JavaScript libraries (loaded from CDN):
- D3.js v7 (network visualization)
- Plotly.js (performance charts)

## Performance

- Handles 1000+ programs efficiently
- Real-time interaction with force simulation
- Responsive design for different screen sizes
