"""Agent 1: Disaster Intake & Normalization Agent"""
import json
import os
from typing import Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from .schema import DisasterIntakeRequest, SCHEMA_JSON

def get_llm(provider: str = "auto", model: str = None, temperature: float = 0.0):
    """Get LLM - auto-detects available free provider."""
    
    if provider == "auto":
        if os.getenv("GROQ_API_KEY"):
            provider = "groq"
        elif os.getenv("GOOGLE_API_KEY"):
            provider = "google"
        elif os.getenv("OPENAI_API_KEY"):
            provider = "openai"
        else:
            provider = "ollama"  # Free local fallback
    
    if provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(model=model or "llama-3.3-70b-versatile", temperature=temperature)
    
    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=model or "gemini-1.5-flash", temperature=temperature)
    
    elif provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=model or "llama3.1", temperature=temperature, format="json")
    
    else:  # openai
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model or "gpt-4o-mini",
            temperature=temperature,
            model_kwargs={"response_format": {"type": "json_object"}}
        )

SYSTEM_PROMPT = """You are Agent 1: Disaster Intake & Normalization Agent.

Your ONLY task is to convert raw disaster-related input text into a STRICT JSON object.

Rules:
1. Output valid JSON ONLY - no explanations, no markdown.
2. DO NOT invent or hallucinate missing data.
3. If data is missing, use null, "unknown", or best classification with LOW confidence.
4. Detect input language, translate to English internally before processing.
5. Infer urgency conservatively. When human safety is implied, prefer higher urgency.
6. If input is irrelevant/spam, set need_type = "unknown" and confidence < 0.3.

Urgency Mapping:
- critical: trapped, bleeding, life-threatening, children/elderly in danger
- high: no food/water, medical need, stranded
- medium: assistance requested without danger
- low: informational or future need

Schema:
{schema}

Return ONLY the JSON object matching this schema exactly."""

class DisasterIntakeAgent:
    def __init__(self, provider: str = "auto", model: str = None, temperature: float = 0.0):
        self.llm = get_llm(provider, model, temperature)
        self.parser = JsonOutputParser(pydantic_object=DisasterIntakeRequest)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", "Process this disaster report:\n\n{input_text}\n\nSource platform: {source_platform}")
        ])
        self.chain = self.prompt | self.llm | self.parser

    def process(self, input_text: str, source_platform: str = "unknown") -> DisasterIntakeRequest:
        """Process raw disaster text into normalized schema."""
        result = self.chain.invoke({
            "input_text": input_text,
            "source_platform": source_platform,
            "schema": json.dumps(SCHEMA_JSON, indent=2)
        })
        
        # Remove None values for auto-generated fields (let Pydantic defaults handle them)
        if result.get("request_id") in [None, "unknown"]:
            result.pop("request_id", None)
        if result.get("timestamp") in [None, "unknown"]:
            result.pop("timestamp", None)
        
        # Validate and create Pydantic model
        return DisasterIntakeRequest(**result)

    def process_batch(self, inputs: list[dict]) -> list[DisasterIntakeRequest]:
        """Process multiple inputs."""
        return [self.process(i["text"], i.get("source", "unknown")) for i in inputs]


# Standalone function for quick use
def normalize_disaster_report(
    text: str, 
    source: str = "unknown",
    provider: str = "auto"
) -> dict:
    """Quick function to normalize a disaster report."""
    agent = DisasterIntakeAgent(provider=provider)
    result = agent.process(text, source)
    return result.model_dump()


if __name__ == "__main__":
    # Test example
    test_input = """
    HELP! We are trapped on the roof at 123 Main Street, Springfield. 
    Water rising fast. 3 adults, 2 children, one elderly woman with heart condition.
    Phone dying. Please send rescue boats ASAP!
    """
    
    agent = DisasterIntakeAgent()  # Auto-detects free provider
    result = agent.process(test_input, "twitter")
    print(json.dumps(result.model_dump(), indent=2))
