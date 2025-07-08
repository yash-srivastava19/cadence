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

### Web Server Configuration

```python
# ui/config.py
class WebConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key'
    HOST = os.environ.get('CADENCE_HOST') or '127.0.0.1'
    PORT = int(os.environ.get('CADENCE_PORT') or 5000)
    DEBUG = os.environ.get('CADENCE_DEBUG') == 'true'

    # Database
    DATABASE_URL = os.environ.get('DATABASE_URL') or 'sqlite:///cadence_db.sqlite'

    # Real-time updates
    WEBSOCKET_ENABLED = True
    UPDATE_INTERVAL = 1.0  # seconds

    # Security
    CORS_ORIGINS = ['http://localhost:3000', 'http://127.0.0.1:3000']
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
```

### Client Configuration

```javascript
// static/js/config.js
const CONFIG = {
    API_BASE_URL: '/api',
    WEBSOCKET_URL: window.location.origin,
    UPDATE_INTERVALS: {
        dashboard: 2000,    // 2 seconds
        network: 5000,      // 5 seconds
        charts: 3000        // 3 seconds
    },
    VISUALIZATION: {
        network: {
            nodeSize: [5, 50],
            linkDistance: 100,
            charge: -300
        },
        charts: {
            animation: true,
            responsive: true,
            theme: 'light'
        }
    }
};
```

## Deployment

### Production Deployment

```python
# ui/wsgi.py
from ui.app import create_app
import os

app = create_app(os.environ.get('FLASK_ENV') or 'production')

if __name__ == "__main__":
    app.run()
```

```bash
# Using Gunicorn
pip install gunicorn
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 ui.wsgi:app

# Using uWSGI
pip install uwsgi
uwsgi --http :5000 --gevent 1000 --http-websockets --master --wsgi-file ui/wsgi.py --callable app
```

### Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "--bind", "0.0.0.0:5000", "ui.wsgi:app"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  cadence-ui:
    build: .
    ports:
      - "5000:5000"
    environment:
      - CADENCE_DB_PATH=/data/cadence.sqlite
      - CADENCE_HOST=0.0.0.0
    volumes:
      - ./data:/data
    restart: unless-stopped
```

### Reverse Proxy Configuration

```nginx
# nginx.conf
server {
    listen 80;
    server_name cadence.example.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support
    location /socket.io/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    # Static files
    location /static/ {
        alias /app/ui/static/;
        expires 1y;
        add_header Cache-Control public;
    }
}
```

## Troubleshooting

### Common Issues

**Port Already in Use**
```bash
# Find process using port
lsof -i :5000

# Kill process
kill -9 <PID>

# Use different port
python ui/launch_ui.py --port 8080
```

**WebSocket Connection Failed**
```javascript
// Check connection status
socket.on('connect', () => {
    console.log('Connected to server');
});

socket.on('disconnect', () => {
    console.log('Disconnected from server');
});

socket.on('connect_error', (error) => {
    console.error('Connection error:', error);
});
```

**Database Access Issues**
```python
# Check database permissions
import sqlite3
try:
    conn = sqlite3.connect('cadence_db.sqlite')
    conn.close()
    print("Database accessible")
except Exception as e:
    print(f"Database error: {e}")
```

### Performance Optimization

**Large Datasets**
```python
# Implement pagination
@app.route('/api/programs')
def get_programs():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)

    programs = query_programs_paginated(page, per_page)
    return jsonify(programs)
```

**Memory Usage**
```python
# Use generators for large datasets
def stream_evolution_data():
    for generation in get_generations():
        yield json.dumps(generation) + '\n'

@app.route('/api/evolution/stream')
def stream_evolution():
    return Response(stream_evolution_data(),
                   mimetype='application/json')
```

**Caching**
```python
from flask_caching import Cache

cache = Cache(app, config={'CACHE_TYPE': 'simple'})

@app.route('/api/metrics/summary')
@cache.cached(timeout=60)  # Cache for 1 minute
def metrics_summary():
    return calculate_metrics_summary()
```
