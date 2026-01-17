# Disaster Relief Resource Scout

## Agent 1: Disaster Intake & Normalization Agent

Production-ready agent that converts raw disaster reports into structured JSON.

### Quick Start

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-your-key
python test_intake.py
```

### Usage

```python
from agents.intake_agent import DisasterIntakeAgent, normalize_disaster_report

# Quick function
result = normalize_disaster_report("HELP! Trapped on roof!", source="twitter")

# Agent class
agent = DisasterIntakeAgent(model="gpt-4o-mini")
result = agent.process(raw_text, source_platform="whatsapp")

# LangGraph node (multi-agent orchestration)
from agents.intake_agent.langgraph_node import create_intake_graph
graph = create_intake_graph()
result = graph.invoke({"raw_input": text, "source_platform": "sms"})
```

### Output Schema

| Field | Type | Description |
|-------|------|-------------|
| request_id | UUID | Auto-generated |
| timestamp | ISO-8601 | Auto-generated |
| disaster_type | enum | earthquake, flood, hurricane, etc |
| need_type | enum | medical, food, rescue, etc |
| urgency | enum | critical, high, medium, low |
| location | object | Parsed location data |
| confidence | float | 0.0-1.0 classification confidence |

---
we have won this hackathon
# Singularity-Hackathon