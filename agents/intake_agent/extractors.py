"""Extractors for URL, Image, and Social Media content"""
import os
import re
import base64
import httpx
from typing import Optional
from pathlib import Path

# ============== URL EXTRACTOR ==============

def extract_from_url(url: str) -> dict:
    """Extract clean text content from any URL."""
    
    # Detect platform
    platform = detect_platform(url)
    
    # Try multiple extraction methods
    try:
        # Method 1: Try Firecrawl if available
        if os.getenv("FIRECRAWL_API_KEY"):
            return _extract_firecrawl(url, platform)
    except:
        pass
    
    # Method 2: Simple HTTP + HTML parsing (free)
    return _extract_simple(url, platform)


def detect_platform(url: str) -> str:
    """Detect source platform from URL."""
    url_lower = url.lower()
    if "twitter.com" in url_lower or "x.com" in url_lower:
        return "twitter"
    elif "facebook.com" in url_lower or "fb.com" in url_lower:
        return "facebook"
    elif "reddit.com" in url_lower:
        return "reddit"
    elif "bsky.app" in url_lower or "bluesky" in url_lower:
        return "bluesky"
    elif "whatsapp" in url_lower:
        return "whatsapp"
    elif any(x in url_lower for x in ["news", "cnn", "bbc", "reuters", "ap"]):
        return "web"
    return "web"


def _extract_simple(url: str, platform: str) -> dict:
    """Simple extraction using httpx + regex."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; DisasterBot/1.0)"}
        response = httpx.get(url, headers=headers, follow_redirects=True, timeout=15)
        html = response.text
        
        # Extract title
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else ""
        
        # Extract meta description
        desc_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if not desc_match:
            desc_match = re.search(r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*name=["\']description["\']', html, re.IGNORECASE)
        description = desc_match.group(1).strip() if desc_match else ""
        
        # Extract og:description (often better for social)
        og_match = re.search(r'<meta[^>]*property=["\']og:description["\'][^>]*content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        og_desc = og_match.group(1).strip() if og_match else ""
        
        # Extract main text content (strip HTML)
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Combine best content
        content = f"{title}\n\n{og_desc or description}\n\n{text[:2000]}"
        
        return {
            "text": content,
            "platform": platform,
            "url": url,
            "title": title
        }
    except Exception as e:
        return {
            "text": f"Failed to extract from {url}: {str(e)}",
            "platform": platform,
            "url": url,
            "title": ""
        }


def _extract_firecrawl(url: str, platform: str) -> dict:
    """Extract using Firecrawl API (better quality)."""
    from firecrawl import FirecrawlApp
    
    app = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))
    result = app.scrape_url(url, params={"formats": ["markdown"]})
    
    return {
        "text": result.get("markdown", ""),
        "platform": platform,
        "url": url,
        "title": result.get("metadata", {}).get("title", "")
    }


# ============== IMAGE EXTRACTOR ==============

def extract_from_image(image_source: str, api_key: str = None, provider: str = "auto") -> dict:
    """Extract disaster information from image using Vision model."""
    
    # Auto-detect provider
    if provider == "auto":
        if os.getenv("GOOGLE_API_KEY"):
            provider = "google"
        elif os.getenv("OPENAI_API_KEY"):
            provider = "openai"
        else:
            # Fallback to OCR only
            provider = "ocr"
    
    prompt = """Analyze this image for disaster-related information. Extract ALL visible details:

1. Type of disaster (flood, earthquake, fire, hurricane, etc.)
2. Visible damage level and description
3. Any people visible - estimated count, conditions (injured, stranded, etc.)
4. Location clues (street signs, landmarks, building names)
5. Any text visible in the image (signs, placards, SOS messages)
6. Visible urgent needs (medical, rescue, supplies)

Provide a detailed narrative for disaster response.
If NOT disaster-related, state that clearly."""

    if provider == "google":
        return _extract_image_google(image_source, prompt, api_key)
    elif provider == "openai":
        return _extract_image_openai(image_source, prompt, api_key)
    else:
        return _extract_image_ocr(image_source)


def _extract_image_google(image_source: str, prompt: str, api_key: str = None) -> dict:
    """Use Google Gemini Vision."""
    from google import genai
    from google.genai import types
    
    api_key = api_key or os.getenv("GOOGLE_API_KEY")
    client = genai.Client(api_key=api_key)
    
    # Download image and send as bytes
    if image_source.startswith(("http://", "https://")):
        response = httpx.get(image_source, timeout=15, follow_redirects=True)
        image_bytes = response.content
    else:
        with open(image_source, "rb") as f:
            image_bytes = f.read()
    
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                    types.Part.from_text(text=prompt),
                ]
            )
        ]
    )
    
    return {"text": response.text, "platform": "image", "source": image_source, "analysis_type": "google_vision"}


def _extract_image_openai(image_source: str, prompt: str, api_key: str = None) -> dict:
    """Use OpenAI GPT-4o Vision."""
    from openai import OpenAI
    
    client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
    
    # Prepare image
    if image_source.startswith(("http://", "https://")):
        image_url = image_source
    else:
        with open(image_source, "rb") as f:
            image_data = base64.b64encode(f.read()).decode()
        image_url = f"data:image/jpeg;base64,{image_data}"
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]
        }]
    )
    
    return {"text": response.choices[0].message.content, "platform": "image", "source": image_source, "analysis_type": "openai_vision"}


def _extract_image_ocr(image_source: str) -> dict:
    """Fallback: OCR only using pytesseract."""
    try:
        import pytesseract
        from PIL import Image
        import io
        
        if image_source.startswith(("http://", "https://")):
            response = httpx.get(image_source, timeout=15)
            img = Image.open(io.BytesIO(response.content))
        else:
            img = Image.open(image_source)
        
        text = pytesseract.image_to_string(img)
        return {"text": f"[OCR Extracted Text]:\n{text}", "platform": "image", "source": image_source, "analysis_type": "ocr"}
    except Exception as e:
        return {"text": f"Image analysis unavailable. Error: {e}", "platform": "image", "source": image_source, "analysis_type": "failed"}


# ============== REDDIT EXTRACTOR ==============

def extract_from_reddit(subreddit: str = "all", query: str = "disaster OR earthquake OR flood OR hurricane", limit: int = 10) -> list[dict]:
    """Extract disaster-related posts from Reddit (no API key needed for read)."""
    
    url = f"https://www.reddit.com/r/{subreddit}/search.json"
    params = {
        "q": query,
        "sort": "new",
        "limit": limit,
        "restrict_sr": "true" if subreddit != "all" else "false"
    }
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DisasterRelief/1.0"}
    
    try:
        response = httpx.get(url, params=params, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"Reddit API returned {response.status_code}")
            return []
        data = response.json()
    except Exception as e:
        print(f"Reddit extraction error: {e}")
        return []
    
    posts = []
    for post in data.get("data", {}).get("children", []):
        p = post["data"]
        posts.append({
            "text": f"{p.get('title', '')}\n\n{p.get('selftext', '')}",
            "platform": "reddit",
            "url": f"https://reddit.com{p.get('permalink', '')}",
            "subreddit": p.get("subreddit", ""),
            "score": p.get("score", 0),
            "created_utc": p.get("created_utc", 0)
        })
    
    return posts


# ============== RSS FEED EXTRACTOR ==============

DISASTER_FEEDS = {
    "usgs_earthquakes": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_week.atom",
    "gdacs": "https://www.gdacs.org/xml/rss.xml",
    "reliefweb": "https://reliefweb.int/updates/rss.xml",
}

def extract_from_rss(feed_url: str = None, feed_name: str = None) -> list[dict]:
    """Extract disaster alerts from RSS feeds."""
    import feedparser
    
    if feed_name and feed_name in DISASTER_FEEDS:
        feed_url = DISASTER_FEEDS[feed_name]
    
    if not feed_url:
        # Get all feeds
        all_entries = []
        for name, url in DISASTER_FEEDS.items():
            all_entries.extend(extract_from_rss(feed_url=url))
        return all_entries
    
    feed = feedparser.parse(feed_url)
    
    entries = []
    for entry in feed.entries[:20]:
        entries.append({
            "text": f"{entry.get('title', '')}\n\n{entry.get('summary', '')}",
            "platform": "web",
            "url": entry.get("link", ""),
            "published": entry.get("published", ""),
            "source_feed": feed_url
        })
    
    return entries
