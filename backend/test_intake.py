"""Quick test for Intake Agent"""
import json
from dotenv import load_dotenv
load_dotenv()

from agents.intake_agent import DisasterIntakeAgent, normalize_disaster_report

# Test cases
TEST_CASES = [
    {
        "text": "HELP! Trapped on roof at 45 Oak Lane, Miami. Flooding. 2 kids, grandmother diabetic. Water rising. Call 555-1234",
        "source": "twitter",
        "expected_urgency": "critical"
    },
    {
        "text": "Necesitamos agua y comida. Estamos en el refugio de la escuela San Jose. 50 personas aqui.",
        "source": "whatsapp", 
        "expected_urgency": "high"
    },
    {
        "text": "Anyone know if the evacuation center is still open tomorrow?",
        "source": "facebook",
        "expected_urgency": "low"
    },
    {
        "text": "Buy cheap watches now! Best deals!",
        "source": "sms",
        "expected_urgency": "low"  # Should be flagged as spam with low confidence
    }
]

def run_tests():
    agent = DisasterIntakeAgent()
    
    for i, case in enumerate(TEST_CASES):
        print(f"\n{'='*60}")
        print(f"TEST {i+1}: {case['text'][:50]}...")
        print(f"{'='*60}")
        
        result = agent.process(case["text"], case["source"])
        print(json.dumps(result.model_dump(), indent=2))
        
        # Validation
        assert result.request_id is not None
        assert result.timestamp is not None
        print(f"✅ Urgency: {result.urgency} | Confidence: {result.confidence}")

if __name__ == "__main__":
    run_tests()
