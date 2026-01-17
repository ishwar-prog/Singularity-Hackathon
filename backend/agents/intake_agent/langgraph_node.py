"""LangGraph Node wrapper for multi-agent orchestration"""
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph
from .agent import DisasterIntakeAgent
from .schema import DisasterIntakeRequest

class IntakeState(TypedDict):
    raw_input: str
    source_platform: str
    normalized_request: dict | None
    error: str | None

def intake_node(state: IntakeState) -> IntakeState:
    """LangGraph node for disaster intake processing."""
    try:
        agent = DisasterIntakeAgent()
        result = agent.process(
            state["raw_input"], 
            state.get("source_platform", "unknown")
        )
        return {
            **state,
            "normalized_request": result.model_dump(),
            "error": None
        }
    except Exception as e:
        return {
            **state,
            "normalized_request": None,
            "error": str(e)
        }

def create_intake_graph() -> StateGraph:
    """Create standalone intake graph for testing."""
    graph = StateGraph(IntakeState)
    graph.add_node("intake", intake_node)
    graph.set_entry_point("intake")
    graph.set_finish_point("intake")
    return graph.compile()
