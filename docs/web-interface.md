# Web Interface

Cadence includes a web-based interface for monitoring and visualizing the evolution process in real-time.

## Overview

The web interface provides:
- Real-time evolution monitoring
- Interactive visualizations of program networks
- Performance metrics and charts
- Code inspection and comparison
- Experiment management

## Launching the Interface

### Basic Usage

```bash
# Start the web interface
cd cadence
python ui/launch_ui.py

# Open browser to http://localhost:5000
```

### Custom Configuration

```bash
# Specify port and host
python ui/launch_ui.py --port 8080 --host 0.0.0.0

# Enable debug mode
python ui/launch_ui.py --debug

# Use custom database
python ui/launch_ui.py --db-path /path/to/database.sqlite
```

## Interface Components

### Dashboard Overview

The main dashboard displays:

**Evolution Status**
- Current generation and progress
- Population size and diversity
- Best solution found
- Time elapsed and estimated completion

**Quick Metrics**
- Best cost evolution over time
- Success rate and feasibility
- LLM API usage and costs
- System resource utilization

### Network Visualization

Interactive network graph showing program relationships:

**Nodes**
- Each node represents a program
- Size indicates fitness (larger = better)
- Color represents generation
- Shape indicates program status (active, elite, failed)

**Edges**
- Lines show parent-child relationships
- Thickness indicates similarity
- Color represents generation gap

**Controls**
- Zoom in/out with mouse wheel
- Pan by dragging
- Click nodes to inspect code
- Toggle generations on/off

### Performance Charts

Multiple visualization types:

**Evolution Progress**
- Line chart of best cost over generations
- Population diversity metrics
- Convergence indicators

**Generation Analysis**
- Box plots of cost distributions
- Histogram of solution quality
- Scatter plots of fitness vs. complexity

**Comparative Analysis**
- Multiple experiment comparisons
- A/B testing results
- Parameter sensitivity analysis

### Code Inspector

Detailed code examination:

**Code Diff Viewer**
- Side-by-side comparison of parent and child programs
- Highlighted differences and changes
- Evolution block focus

**Syntax Highlighting**
- Python syntax highlighting
- Error highlighting
- Performance annotations

**Execution Traces**
- Program execution logs
- Error messages and stack traces
- Performance profiling data

### Experiment Manager

Control and monitor experiments:

**Experiment List**
- Active and completed experiments
- Progress indicators
- Quick statistics

**Configuration Editor**
- Modify experiment parameters
- Start/stop experiments
- Schedule experiments

**Results Browser**
- Download experiment data
- Export visualizations
- Generate reports

## API Endpoints

The web interface exposes REST APIs for programmatic access:

### Evolution Status

```bash
# Get current evolution status
GET /api/status

Response:
{
  "generation": 45,
  "population_size": 20,
  "best_cost": 123.45,
  "diversity": 0.75,
  "running": true,
  "start_time": "2025-07-08T10:00:00Z"
}
```

### Program Data

```bash
# Get all programs
GET /api/programs

# Get specific program
GET /api/programs/{program_id}

# Get programs from generation
GET /api/programs?generation={gen_num}

Response:
{
  "programs": [
    {
      "id": 1,
      "code": "def tsp(cities): ...",
      "cost": 123.45,
      "generation": 45,
      "parent_id": 5,
      "feasible": true,
      "timestamp": "2025-07-08T10:15:00Z"
    }
  ]
}
```

### Performance Metrics

```bash
# Get evolution history
GET /api/metrics/evolution

# Get generation statistics
GET /api/metrics/generation/{gen_num}

# Get performance summary
GET /api/metrics/summary

Response:
{
  "generations": [
    {
      "generation": 1,
      "best_cost": 245.67,
      "average_cost": 456.78,
      "diversity": 0.85,
      "feasible_count": 18
    }
  ]
}
```

### Control Operations

```bash
# Start evolution
POST /api/control/start
{
  "task": "tsp",
  "generations": 100,
  "population_size": 20
}

# Stop evolution
POST /api/control/stop

# Pause/resume
POST /api/control/pause
POST /api/control/resume

# Reset evolution
POST /api/control/reset
```

## Real-time Updates

The interface uses WebSocket connections for real-time updates:

### JavaScript Client

```javascript
// Connect to WebSocket
const socket = io();

// Listen for evolution updates
socket.on('evolution_update', (data) => {
    updateDashboard(data);
    updateCharts(data);
});

// Listen for new programs
socket.on('new_program', (program) => {
    addProgramToNetwork(program);
    updateMetrics();
});

// Listen for generation completion
socket.on('generation_complete', (stats) => {
    updateGenerationStats(stats);
    refreshVisualization();
});
```

### Server Events

```python
# In Flask app
from flask_socketio import emit, SocketIO

socketio = SocketIO(app)

def on_evolution_update(data):
    """Broadcast evolution updates to all clients."""
    socketio.emit('evolution_update', data)

def on_new_program(program):
    """Broadcast new program creation."""
    socketio.emit('new_program', program.to_dict())

def on_generation_complete(generation_stats):
    """Broadcast generation completion."""
    socketio.emit('generation_complete', generation_stats)
```

## Customization

### Adding Custom Visualizations

```javascript
// Custom chart component
function createCustomChart(containerId, data) {
    const svg = d3.select(containerId)
        .append('svg')
        .attr('width', 800)
        .attr('height', 400);

    // Custom visualization logic
    const chart = new CustomChart(svg, data);
    return chart;
}

// Register custom chart
registerVisualization('custom_metric', createCustomChart);
```

### Custom Metrics

```python
# In ui/app.py
@app.route('/api/metrics/custom')
def custom_metrics():
    """Provide custom metrics for visualization."""
    # Calculate custom metrics
    complexity_scores = calculate_complexity_scores()
    innovation_scores = calculate_innovation_scores()

    return jsonify({
        'complexity': complexity_scores,
        'innovation': innovation_scores
    })
```

### Theme Customization

```css
/* Custom theme in static/css/custom.css */
:root {
    --primary-color: #2C3E50;
    --secondary-color: #3498DB;
    --success-color: #27AE60;
    --warning-color: #F39C12;
    --danger-color: #E74C3C;
}

.dashboard-card {
    background: var(--primary-color);
    color: white;
    border-radius: 8px;
    padding: 20px;
    margin: 10px;
}

.network-node {
    stroke: var(--secondary-color);
    stroke-width: 2px;
}
```

## Configuration

There is none. `ui/app.py` hardcodes everything:

| Setting | Value | Where |
| --- | --- | --- |
| Host | `0.0.0.0` | `app.run()`, `ui/launch_ui.py` |
| Port | `5000` | same |
| Debug | `True` | same |
| Database | `cadence_db.sqlite`, relative to the working directory | `get_all_programs()`, `src/database.py` |

<!-- docs-test: allow-env CADENCE_HOST,CADENCE_PORT,CADENCE_DEBUG,CADENCE_DB_PATH -->
No `CADENCE_HOST`, `CADENCE_PORT`, `CADENCE_DEBUG`, or `CADENCE_DB_PATH`
exists. To change any of these, edit `ui/launch_ui.py`.

`debug=True` means the Flask reloader and the interactive debugger are on.
That is fine on your own machine and unsafe anywhere else, so do not expose
this port.

## Troubleshooting

**The dashboard is empty while a run is going**

The most common cause is Hydra. It changes the working directory to
`outputs/<date>/<time>/`, so a run writes its database *there* while the UI
reads `./cadence_db.sqlite` from wherever you launched it. Either launch the
UI from the run's output directory, or start runs with `hydra.run.dir=.` —
see [Configuration](configuration.md#where-output-goes-and-the-gotcha).

**Port 5000 is already in use**

On macOS, AirPlay Receiver holds port 5000. Turn it off in System Settings, or
edit the port in `ui/launch_ui.py`.

**`ModuleNotFoundError: No module named 'app'`**

`ui/launch_ui.py` does `from app import app`, which relies on `ui/` being on
`sys.path`. Run it as `python ui/launch_ui.py` from the project root, not as
`python -m ui.launch_ui`.
