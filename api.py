from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
from agents.intake_agent import ExtendedDisasterAgent
from agents.intake_agent.extractors import detect_platform
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import re
import httpx
from datetime import datetime, timedelta
import base64
import tempfile

app = FastAPI(title="Disaster Management API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalysisRequest(BaseModel):
    text: str
    source: str = "web"
    user_lat: Optional[float] = None
    user_lon: Optional[float] = None

class ImageAnalysisRequest(BaseModel):
    image_url: str
    user_lat: Optional[float] = None
    user_lon: Optional[float] = None

agent = ExtendedDisasterAgent()

# Platform detection patterns
PLATFORM_PATTERNS = {
    "twitter": ["twitter.com", "x.com", "t.co"],
    "facebook": ["facebook.com", "fb.com", "fb.me"],
    "reddit": ["reddit.com", "redd.it"],
    "instagram": ["instagram.com", "instagr.am"],
    "youtube": ["youtube.com", "youtu.be"],
    "linkedin": ["linkedin.com"],
    "tiktok": ["tiktok.com"],
    "bluesky": ["bsky.app"],
    "mastodon": ["mastodon.social", "mastodon.online"],
    "usgs": ["usgs.gov"],
    "noaa": ["noaa.gov", "weather.gov"],
    "cnn": ["cnn.com"],
    "bbc": ["bbc.com", "bbc.co.uk"],
    "reuters": ["reuters.com"],
    "ap_news": ["apnews.com"],
    "nytimes": ["nytimes.com"],
    "guardian": ["theguardian.com"],
}

def detect_platform_enhanced(url: str) -> dict:
    """Enhanced platform detection with credibility info."""
    url_lower = url.lower()
    
    for platform, patterns in PLATFORM_PATTERNS.items():
        for pattern in patterns:
            if pattern in url_lower:
                is_official = platform in ["usgs", "noaa", "reuters", "ap_news", "bbc"]
                return {
                    "platform": platform,
                    "is_official_source": is_official,
                    "credibility_boost": 0.3 if is_official else 0.0
                }
    
    return {"platform": "web", "is_official_source": False, "credibility_boost": 0.0}

def calculate_credibility(result: dict, platform_info: dict, text: str) -> dict:
    """Calculate credibility score and verification status."""
    score = 0.5  # Base score
    factors = []
    
    # Factor 1: Official source
    if platform_info.get("is_official_source"):
        score += 0.25
        factors.append({"factor": "Official Government/News Source", "impact": "+25%", "positive": True})
    
    # Factor 2: Confidence from AI
    ai_confidence = result.get("confidence", 0.5)
    if ai_confidence > 0.8:
        score += 0.15
        factors.append({"factor": "High AI Analysis Confidence", "impact": "+15%", "positive": True})
    elif ai_confidence < 0.4:
        score -= 0.15
        factors.append({"factor": "Low AI Confidence - Verify Manually", "impact": "-15%", "positive": False})
    
    # Factor 3: Location data present
    location = result.get("location", {})
    if location.get("city") or location.get("latitude"):
        score += 0.1
        factors.append({"factor": "Verifiable Location Data", "impact": "+10%", "positive": True})
    else:
        score -= 0.1
        factors.append({"factor": "No Location Data - Hard to Verify", "impact": "-10%", "positive": False})
    
    # Factor 4: Check for sensationalist language
    sensational_words = ["BREAKING", "EXCLUSIVE", "SHOCKING", "YOU WON'T BELIEVE", "VIRAL"]
    if any(word in text.upper() for word in sensational_words):
        score -= 0.15
        factors.append({"factor": "Sensationalist Language Detected", "impact": "-15%", "positive": False})
    
    # Factor 5: Timestamp freshness
    timestamp = result.get("timestamp", "")
    try:
        ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        age = datetime.now(ts.tzinfo) - ts
        if age < timedelta(hours=24):
            factors.append({"factor": "Recent Report (< 24h)", "impact": "+5%", "positive": True})
            score += 0.05
        elif age > timedelta(days=7):
            factors.append({"factor": "Potentially Outdated (> 7 days)", "impact": "-20%", "positive": False})
            score -= 0.2
    except:
        pass
    
    # Factor 6: Contact info present
    if result.get("contact_info"):
        score += 0.1
        factors.append({"factor": "Contact Information Provided", "impact": "+10%", "positive": True})
    
    # Clamp score
    score = max(0.1, min(1.0, score))
    
    # Determine status
    if score >= 0.75:
        status = "verified"
        status_text = "Likely Credible"
    elif score >= 0.5:
        status = "unverified"
        status_text = "Needs Verification"
    elif score >= 0.3:
        status = "suspicious"
        status_text = "Low Credibility"
    else:
        status = "fake"
        status_text = "Potentially False/Outdated"
    
    return {
        "score": round(score, 2),
        "status": status,
        "status_text": status_text,
        "factors": factors
    }

@app.post("/analyze")
async def analyze_disaster(request: AnalysisRequest):
    try:
        platform_info = {"platform": request.source, "is_official_source": False, "credibility_boost": 0.0}
        
        # Check if it's a URL
        if request.text.startswith(("http://", "https://")):
            platform_info = detect_platform_enhanced(request.text)
            result = agent.process_url(request.text)
        else:
            result = agent.process_text(request.text, source=request.source)
        
        result_dict = result.model_dump()
        
        # Add user location if provided and no location detected
        if request.user_lat and request.user_lon:
            if not result_dict["location"].get("latitude"):
                result_dict["location"]["latitude"] = request.user_lat
                result_dict["location"]["longitude"] = request.user_lon
                result_dict["location"]["raw_text"] = result_dict["location"].get("raw_text", "") + " (User's current location)"
        
        # Enhanced platform info
        result_dict["detected_platform"] = platform_info["platform"]
        result_dict["is_official_source"] = platform_info["is_official_source"]
        
        # Calculate credibility
        credibility = calculate_credibility(result_dict, platform_info, request.text)
        result_dict["credibility"] = credibility
        
        return result_dict
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze-image")
async def analyze_image(request: ImageAnalysisRequest):
    try:
        result = agent.process_image(request.image_url)
        result_dict = result.model_dump()
        
        # Add user location if provided
        if request.user_lat and request.user_lon:
            if not result_dict["location"].get("latitude"):
                result_dict["location"]["latitude"] = request.user_lat
                result_dict["location"]["longitude"] = request.user_lon
                result_dict["location"]["raw_text"] = result_dict["location"].get("raw_text", "") + " (User's current location)"
        
        result_dict["detected_platform"] = "image_upload"
        result_dict["is_official_source"] = False
        
        # Calculate credibility for image
        credibility = calculate_credibility(result_dict, {"is_official_source": False}, "")
        credibility["factors"].append({"factor": "Image Source - Requires Visual Verification", "impact": "-10%", "positive": False})
        credibility["score"] = max(0.1, credibility["score"] - 0.1)
        result_dict["credibility"] = credibility
        
        return result_dict
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze-image-upload")
async def analyze_image_upload(
    file: UploadFile = File(...),
    user_lat: Optional[float] = Form(None),
    user_lon: Optional[float] = Form(None)
):
    try:
        # Save uploaded file temporarily
        contents = await file.read()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file.filename.split('.')[-1]}") as tmp:
            tmp.write(contents)
            tmp_path = tmp.name
        
        try:
            result = agent.process_image(tmp_path)
            result_dict = result.model_dump()
            
            # Add user location
            if user_lat and user_lon:
                if not result_dict["location"].get("latitude"):
                    result_dict["location"]["latitude"] = user_lat
                    result_dict["location"]["longitude"] = user_lon
                    result_dict["location"]["raw_text"] = result_dict["location"].get("raw_text", "") + " (User's current location)"
            
            result_dict["detected_platform"] = "image_upload"
            result_dict["is_official_source"] = False
            
            # Calculate credibility
            credibility = calculate_credibility(result_dict, {"is_official_source": False}, "")
            credibility["factors"].append({"factor": "Direct Image Upload - User Provided", "impact": "0%", "positive": True})
            result_dict["credibility"] = credibility
            
            return result_dict
        finally:
            os.unlink(tmp_path)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
