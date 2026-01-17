"""Extended Disaster Intake Agent with URL, Image, and Social Media support"""
import json
from typing import Union
from pathlib import Path

from .agent import DisasterIntakeAgent
from .schema import DisasterIntakeRequest
from .extractors import (
    extract_from_url,
    extract_from_image,
    extract_from_reddit,
    extract_from_rss,
    detect_platform
)


class ExtendedDisasterAgent:
    """
    Extended agent that can process:
    - Raw text
    - URLs (news, social media)
    - Images (photos, screenshots)
    - Reddit posts
    - RSS feeds
    """
    
    def __init__(self, provider: str = "auto", model: str = None):
        self.intake_agent = DisasterIntakeAgent(provider=provider, model=model)
    
    def process_any(self, input_data: str) -> DisasterIntakeRequest:
        """
        Auto-detect input type and process accordingly.
        
        Args:
            input_data: Can be:
                - Plain text
                - URL (http:// or https://)
                - File path to image (.jpg, .png, .webp)
        """
        input_data = input_data.strip()
        
        # Check if URL
        if input_data.startswith(("http://", "https://")):
            # Check if image URL
            if any(input_data.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']):
                return self.process_image(input_data)
            return self.process_url(input_data)
        
        # Check if local image file
        if Path(input_data).exists() and any(input_data.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']):
            return self.process_image(input_data)
        
        # Default: treat as text
        return self.process_text(input_data)
    
    def process_text(self, text: str, source: str = "unknown") -> DisasterIntakeRequest:
        """Process raw text input."""
        return self.intake_agent.process(text, source)
    
    def process_url(self, url: str) -> DisasterIntakeRequest:
        """Extract content from URL and process."""
        extracted = extract_from_url(url)
        result = self.intake_agent.process(
            extracted["text"], 
            source_platform=extracted["platform"]
        )
        # Add URL to flags for reference
        if url not in result.flags:
            result.flags.append(f"source_url:{url[:100]}")
        return result
    
    def process_image(self, image_source: str) -> DisasterIntakeRequest:
        """Analyze image and process extracted content."""
        extracted = extract_from_image(image_source)
        result = self.intake_agent.process(
            extracted["text"],
            source_platform="image"
        )
        result.flags.append("extracted_from_image")
        return result
    
    def process_reddit(self, subreddit: str = "all", query: str = "disaster", limit: int = 5) -> list[DisasterIntakeRequest]:
        """Fetch and process Reddit posts."""
        posts = extract_from_reddit(subreddit, query, limit)
        results = []
        for post in posts:
            try:
                result = self.intake_agent.process(post["text"], source_platform="reddit")
                result.flags.append(f"reddit:{post.get('subreddit', '')}")
                results.append(result)
            except Exception as e:
                print(f"Error processing Reddit post: {e}")
        return results
    
    def process_rss_feeds(self) -> list[DisasterIntakeRequest]:
        """Fetch and process all configured RSS feeds."""
        entries = extract_from_rss()
        results = []
        for entry in entries:
            try:
                result = self.intake_agent.process(entry["text"], source_platform="web")
                result.flags.append(f"rss_feed")
                results.append(result)
            except Exception as e:
                print(f"Error processing RSS entry: {e}")
        return results
    
    def batch_process(self, inputs: list[str]) -> list[DisasterIntakeRequest]:
        """Process multiple inputs of any type."""
        return [self.process_any(inp) for inp in inputs]


# Quick function
def process_disaster_input(input_data: str, provider: str = "auto") -> dict:
    """One-liner to process any disaster input."""
    agent = ExtendedDisasterAgent(provider=provider)
    result = agent.process_any(input_data)
    return result.model_dump()
