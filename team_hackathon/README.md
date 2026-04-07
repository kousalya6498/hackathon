# Pipeline Debugging Environment

An OpenEnv environment for training agents to diagnose and fix supply chain pipeline failures through systematic investigation using multi-signal operational evidence.

## 🎯 Overview

This environment simulates real-world supply chain debugging scenarios where agents must:
1. **Investigate** failure indicators across multiple systems (inventory, API, metrics)
2. **Diagnose** the root cause through systematic analysis
3. **Apply** appropriate fixes efficiently

Each task now ships with a larger incident corpus containing business impact summaries, inventory-side evidence, API-side traces, and metrics timelines rather than a single toy record.

### Real-World Application

Models production incident response in:
- E-commerce inventory systems
- Warehouse management platforms
- Supply chain orchestration systems
- Distributed pipeline monitoring

## 📊 Tasks

The environment includes 3 tasks with progressive difficulty:

### 1. Easy: Simple API Delay
- **Description**: API response time is elevated
- **Max Steps**: 8
- **Challenge**: Identify API delay and apply retry fix
- **Indicators**: High API response time, elevated latency

### 2. Medium: Warehouse Sync Failure
- **Description**: Stock mismatch between warehouse and central system
- **Max Steps**: 10
- **Challenge**: Diagnose sync issues across inventory and API systems
- **Indicators**: Inventory lag, API errors, sync delays

### 3. Hard: Cascading Timeout Failure
- **Description**: Multiple systems experiencing cascading failures
- **Max Steps**: 12
- **Challenge**: Comprehensive diagnosis and coordinated fixes
- **Indicators**: High latency, network congestion, API timeouts, inventory errors

## 🎮 Action Space

Agents can take 6 types of actions:

### Diagnostic Actions
- `check_logs` - Inspect inventory logs for errors and mismatches
- `check_api` - Inspect API sync logs for failures and delays
- `check_metrics` - Inspect latency and performance metrics

### Fix Actions
- `retry_pipeline` - Retry failed pipeline operations
- `apply_batching` - Apply batching to reduce load
- `fix_sync` - Apply synchronization correction

## 📈 Observation Space

Rich observations include:
- **Task Info**: task_id, difficulty level
- **Pipeline State**: pipeline name, issue description
- **Failure Indicators** (normalized 0-1):
  - inventory_lag_score
  - inventory_error_count
  - api_response_time
  - api_error_rate
  - latency_score
  - network_congestion
- **Action Feedback**: last action, result, actions taken
- **Progress**: step count, diagnosis/fix status
- **Score**: current episode score (0.0-1.0)
- **Hints**: Contextual guidance
- **Operational Evidence**:
  - inventory_log_excerpt
  - api_log_excerpt
  - metrics_summary
  - business_impact_summary

## 🏆 Scoring

Agents are scored 0.0-1.0 based on:

- **Correctness (70%)**: Taking the right diagnostic and fix actions
  - +10 points per correct diagnostic action
  - +20 points per correct fix action
  - -5 points for wrong actions
  - -2 points for redundant actions

- **Efficiency (30%)**: Completing the task in fewer steps
  - Bonus for optimal step count
  - Penalty for unnecessary actions

### Grading Properties
- ✅ Deterministic and reproducible
- ✅ Normalized to [0.0, 1.0] range
- ✅ Balances correctness and efficiency
- ✅ Provides meaningful difficulty progression

## 🚀 Quick Start

### Installation

```bash
# Install OpenEnv
pip install openenv-core[core]

# Or use uv
uv sync
```

### Running the Server

```bash
# Development mode
uvicorn server.app:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn server.app:app --host 0.0.0.0 --port 8000 --workers 4

# Or use the entry point
uv run server
```

### Using the Environment

```python
from team_hackathon import TeamHackathonEnv, TeamHackathonAction

# Connect to server
async with TeamHackathonEnv(base_url="http://localhost:8000") as env:
    # Reset environment
    result = await env.reset()
    obs = result.observation
    
    print(f"Task: {obs.task_id} ({obs.task_difficulty})")
    print(f"Issue: {obs.issue_description}")
    
    # Take actions
    while not obs.done:
        # Your agent logic here
        action = TeamHackathonAction(action_type="check_logs")
        result = await env.step(action)
        obs = result.observation
        
        print(f"Action: {obs.last_action}")
        print(f"Result: {obs.action_result}")
        print(f"Score: {obs.current_score:.3f}")
```

### Running the Baseline

```bash
# Run baseline agent across the task set
python3 baseline.py --episodes 3 --url http://localhost:8000

# Save results
python3 baseline.py --episodes 6 --url http://localhost:8000 --output results.json
```

### Running the LLM Inference Script

```bash
export OPENAI_API_KEY="your_key_here"
export API_BASE_URL="https://api.openai.com/v1"
export MODEL_NAME="gpt-4.1-mini"
export ENV_URL="http://localhost:8000"

# Runs easy, medium, and hard tasks in order by default
python3 inference.py
```

## 📦 Project Structure

```
team_hackathon/
├── models.py                    # Action/Observation types
├── client.py                    # Environment client
├── baseline.py                  # Baseline agent script
├── server/
│   ├── app.py                   # FastAPI server
│   └── team_hackathon_environment.py  # Environment implementation
├── data/
│   └── sample_logs.json         # Example failure logs
├── openenv.yaml                 # Environment specification
├── Dockerfile                   # Docker deployment
├── pyproject.toml               # Project configuration
└── README.md                    # This file
```

## 🐳 Docker Deployment

### Build

```bash
docker build -t pipeline-debugger:latest .
```

### Run

```bash
docker run -p 8000:8000 pipeline-debugger:latest
```

### Deploy to Hugging Face Spaces

```bash
openenv push
```

## 📊 Baseline Performance

The included rule-based baseline agent currently achieves:

| Difficulty | Mean Score | Success Rate |
|------------|------------|--------------|
| Easy       | 0.872      | 100%         |
| Medium     | 0.732      | 100%         |
| Hard       | 0.689      | 100%         |

**Overall**: 0.764 mean score, 100% success rate over one deterministic pass of all three tasks.

This provides a solid baseline for comparison. Well-trained RL agents should significantly exceed these scores.

## 🎓 Environment Design Highlights

### Real-World Utility
- Models genuine production debugging workflows
- Addresses actual operational challenges
- Applicable to multiple industries
- Fills gap in RL environments for operational tasks

### Task Quality
- Clear difficulty progression
- Well-defined objectives
- Deterministic grading
- Meaningful challenge at all levels

### Environment Design
- Clean state management
- Sensible action/observation spaces
- Good reward shaping (not sparse)
- Proper episode boundaries

### Code Quality
- OpenEnv spec compliant
- Clean project structure
- Typed models with Pydantic
- Comprehensive documentation
- Docker support

## 🔧 Development

### Testing the Environment

```python
from server.team_hackathon_environment import TeamHackathonEnvironment
from models import TeamHackathonAction

# Create environment
env = TeamHackathonEnvironment()

# Reset
obs = env.reset()
print(f"Task: {obs.task_id}")

# Take actions
action = TeamHackathonAction(action_type="check_logs")
obs = env.step(action)
print(f"Result: {obs.action_result}")
print(f"Score: {obs.current_score}")
```

### Validation

```bash
# Validate OpenEnv compliance
openenv validate

# Test Docker build
docker build -t test .
docker run -p 8000:8000 test
```

## 📝 License

This project is part of an OpenEnv hackathon submission.

## 🤝 Contributing

This environment demonstrates:
- Novel problem domain (supply chain debugging)
- Interesting two-phase mechanics (diagnosis → fix)
- Clever reward design balancing correctness and efficiency
- Real-world applicability

Perfect for training agents to handle production incidents efficiently!
