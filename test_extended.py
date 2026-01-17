"""Test Extended Agent - URL, Image, RSS extraction"""
import json
from dotenv import load_dotenv
load_dotenv()

from agents.intake_agent import ExtendedDisasterAgent, process_disaster_input

def test_url_extraction():
    """Test extracting from a news URL"""
    print("\n" + "="*60)
    print("TEST: URL Extraction (USGS Earthquake Page)")
    print("="*60)
    
    agent = ExtendedDisasterAgent()
    
    # Test with USGS earthquake page
    url = "https://earthquake.usgs.gov/earthquakes/eventpage/us7000n22w/executive"
    result = agent.process_url(url)
    
    print(json.dumps(result.model_dump(), indent=2))
    print(f"✅ Disaster Type: {result.disaster_type} | Urgency: {result.urgency}")


def test_rss_feeds():
    """Test RSS feed extraction"""
    print("\n" + "="*60)
    print("TEST: RSS Feed Extraction (USGS Earthquakes)")
    print("="*60)
    
    from agents.intake_agent.extractors import extract_from_rss
    
    # Just get raw RSS data first
    entries = extract_from_rss(feed_name="usgs_earthquakes")
    
    if entries:
        print(f"Found {len(entries)} earthquake alerts")
        print(f"\nLatest: {entries[0]['text'][:200]}...")
        
        # Process first one through agent
        agent = ExtendedDisasterAgent()
        result = agent.process_text(entries[0]["text"], source="web")
        print(f"\n✅ Processed: {result.disaster_type} | {result.urgency} | Confidence: {result.confidence}")
    else:
        print("No RSS entries found")


def test_reddit():
    """Test Reddit extraction"""
    print("\n" + "="*60)
    print("TEST: Reddit Extraction")
    print("="*60)
    
    from agents.intake_agent.extractors import extract_from_reddit
    
    posts = extract_from_reddit(subreddit="tropicalweather", query="hurricane OR storm", limit=3)
    
    if posts:
        print(f"Found {len(posts)} posts")
        for i, post in enumerate(posts[:2]):
            print(f"\n--- Post {i+1} ---")
            print(f"Text: {post['text'][:150]}...")
            print(f"URL: {post['url']}")
    else:
        print("No Reddit posts found")


def test_image_analysis():
    """Test image analysis with Gemini Vision"""
    print("\n" + "="*60)
    print("TEST: Image Analysis (Gemini Vision)")
    print("="*60)
    
    import os
    if not os.getenv("GOOGLE_API_KEY"):
        print("⚠️ GOOGLE_API_KEY not set, skipping image test")
        return
    
    # Test with a public disaster image URL
    image_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/8/89/2011_Tohoku_earthquake_-_Fires_in_Yamada_town.jpg/800px-2011_Tohoku_earthquake_-_Fires_in_Yamada_town.jpg"
    
    agent = ExtendedDisasterAgent()
    result = agent.process_image(image_url)
    
    print(json.dumps(result.model_dump(), indent=2))
    print(f"✅ Disaster Type: {result.disaster_type} | Urgency: {result.urgency}")


def test_auto_detect():
    """Test auto-detection of input type"""
    print("\n" + "="*60)
    print("TEST: Auto-Detection")
    print("="*60)
    
    inputs = [
        "HELP! Flooding in downtown, people stranded on rooftops!",
        "https://earthquake.usgs.gov/earthquakes/map/",
    ]
    
    agent = ExtendedDisasterAgent()
    
    for inp in inputs:
        print(f"\nInput: {inp[:50]}...")
        result = agent.process_any(inp)
        print(f"✅ Type: {result.disaster_type} | Need: {result.need_type} | Urgency: {result.urgency}")


if __name__ == "__main__":
    print("🚨 EXTENDED DISASTER AGENT TESTS 🚨")
    
    # Run tests
    test_rss_feeds()
    test_reddit()
    test_url_extraction()
    test_image_analysis()
    test_auto_detect()
