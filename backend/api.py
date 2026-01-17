from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import re
import httpx
from datetime import datetime, timedelta
import base64
import tempfile
import json

# Load environment variables FIRST
from dotenv import load_dotenv
load_dotenv()

# Now import agents (they need the env vars)
from agents.intake_agent import ExtendedDisasterAgent
from agents.intake_agent.extractors import detect_platform

app = FastAPI(title="Disaster Intelligence Agent API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============== REQUEST MODELS ==============

class AnalysisRequest(BaseModel):
    text: str
    source: str = "web"

class ImageAnalysisRequest(BaseModel):
    image_url: str

# ============== AGENT CONFIGURATION ==============

agent = ExtendedDisasterAgent()

# Platform detection with credibility tiers
PLATFORM_CONFIG = {
    # Tier 1: Official Government Sources (highest trust)
    "usgs": {"patterns": ["usgs.gov"], "tier": 1, "name": "USGS Official", "trust": 0.95},
    "noaa": {"patterns": ["noaa.gov", "weather.gov", "nhc.noaa.gov"], "tier": 1, "name": "NOAA Weather", "trust": 0.95},
    "fema": {"patterns": ["fema.gov"], "tier": 1, "name": "FEMA", "trust": 0.95},
    "cdc": {"patterns": ["cdc.gov"], "tier": 1, "name": "CDC", "trust": 0.95},
    
    # Tier 2: Major News Agencies (high trust)
    "reuters": {"patterns": ["reuters.com"], "tier": 2, "name": "Reuters", "trust": 0.85},
    "ap_news": {"patterns": ["apnews.com"], "tier": 2, "name": "AP News", "trust": 0.85},
    "bbc": {"patterns": ["bbc.com", "bbc.co.uk"], "tier": 2, "name": "BBC News", "trust": 0.85},
    "cnn": {"patterns": ["cnn.com"], "tier": 2, "name": "CNN", "trust": 0.80},
    "nytimes": {"patterns": ["nytimes.com"], "tier": 2, "name": "NY Times", "trust": 0.85},
    "guardian": {"patterns": ["theguardian.com"], "tier": 2, "name": "The Guardian", "trust": 0.82},
    "aljazeera": {"patterns": ["aljazeera.com"], "tier": 2, "name": "Al Jazeera", "trust": 0.80},
    
    # Tier 3: Social Media (needs verification)
    "twitter": {"patterns": ["twitter.com", "x.com", "t.co"], "tier": 3, "name": "Twitter/X", "trust": 0.40},
    "reddit": {"patterns": ["reddit.com", "redd.it"], "tier": 3, "name": "Reddit", "trust": 0.35},
    "facebook": {"patterns": ["facebook.com", "fb.com"], "tier": 3, "name": "Facebook", "trust": 0.35},
    "instagram": {"patterns": ["instagram.com"], "tier": 3, "name": "Instagram", "trust": 0.30},
    "tiktok": {"patterns": ["tiktok.com"], "tier": 3, "name": "TikTok", "trust": 0.25},
    "youtube": {"patterns": ["youtube.com", "youtu.be"], "tier": 3, "name": "YouTube", "trust": 0.40},
    
    # Tier 4: Unknown sources (low trust)
    "unknown": {"patterns": [], "tier": 4, "name": "Unknown Source", "trust": 0.20},
}

# Known scam/fake donation patterns
SCAM_INDICATORS = [
    "send crypto", "bitcoin only", "wire transfer", "western union",
    "cash app only", "venmo only", "zelle only", "paypal friends",
    "urgent donate now", "100% goes to victims", "tax deductible guaranteed",
    "dm for donation link", "click link in bio", "limited time",
    "match your donation", "celebrity endorsed", "government approved",
]

LEGITIMATE_CHARITY_DOMAINS = [
    "redcross.org", "unicef.org", "savethechildren.org", "directrelief.org",
    "americares.org", "doctorswithoutborders.org", "globalgiving.org",
    "gofundme.com/f/", "habitat.org", "feedingamerica.org", "care.org",
]

# ============== HELPER FUNCTIONS ==============

def detect_platform_enhanced(url: str) -> dict:
    """Detect platform and assign trust tier."""
    url_lower = url.lower()
    
    for platform_id, config in PLATFORM_CONFIG.items():
        for pattern in config.get("patterns", []):
            if pattern in url_lower:
                return {
                    "platform": platform_id,
                    "platform_name": config["name"],
                    "tier": config["tier"],
                    "base_trust": config["trust"],
                    "is_official": config["tier"] <= 2
                }
    
    return {
        "platform": "web",
        "platform_name": "Web Source",
        "tier": 4,
        "base_trust": 0.30,
        "is_official": False
    }

def analyze_donation_links(text: str) -> dict:
    """Analyze text for donation links and scam indicators."""
    text_lower = text.lower()
    
    # Check for scam indicators
    scam_flags = []
    for indicator in SCAM_INDICATORS:
        if indicator in text_lower:
            scam_flags.append(indicator)
    
    # Check for legitimate charities
    legitimate_found = []
    for domain in LEGITIMATE_CHARITY_DOMAINS:
        if domain in text_lower:
            legitimate_found.append(domain)
    
    # Extract URLs from text
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(url_pattern, text)
    
    donation_urls = []
    for url in urls:
        url_lower_check = url.lower()
        is_legitimate = any(domain in url_lower_check for domain in LEGITIMATE_CHARITY_DOMAINS)
        is_suspicious = any(indicator in url_lower_check for indicator in ["bit.ly", "tinyurl", "t.co", "goo.gl"])
        
        donation_urls.append({
            "url": url[:100],
            "is_legitimate_charity": is_legitimate,
            "is_shortened_suspicious": is_suspicious
        })
    
    # Calculate donation trust score
    if legitimate_found and not scam_flags:
        donation_trust = "verified"
        donation_score = 0.9
    elif scam_flags:
        donation_trust = "scam_likely"
        donation_score = 0.1
    elif donation_urls:
        donation_trust = "unverified"
        donation_score = 0.4
    else:
        donation_trust = "none_found"
        donation_score = None
    
    return {
        "donation_trust": donation_trust,
        "donation_score": donation_score,
        "scam_indicators_found": scam_flags[:5],
        "legitimate_charities_found": legitimate_found,
        "donation_urls": donation_urls[:3]
    }

def check_content_freshness(text: str) -> dict:
    """Check if content might be outdated or recycled."""
    text_lower = text.lower()
    
    # Date patterns that might indicate old content
    year_pattern = r'\b(201[0-9]|202[0-4])\b'
    years_found = re.findall(year_pattern, text)
    
    current_year = datetime.now().year
    old_years = [y for y in years_found if int(y) < current_year - 1]
    
    # Check for phrases indicating recycled content
    recycled_indicators = [
        "years ago", "last year", "throwback", "remember when",
        "old footage", "archive", "historical", "from 20"
    ]
    recycled_flags = [ind for ind in recycled_indicators if ind in text_lower]
    
    if old_years or recycled_flags:
        return {
            "freshness": "potentially_outdated",
            "old_years_mentioned": old_years[:3],
            "recycled_indicators": recycled_flags[:3],
            "warning": "Content may be outdated or recycled from past events"
        }
    
    return {
        "freshness": "appears_current",
        "old_years_mentioned": [],
        "recycled_indicators": [],
        "warning": None
    }

def extract_people_estimates(text: str) -> dict:
    """Extract estimates of people affected from text."""
    text_lower = text.lower()
    
    patterns = [
        (r'(\d+(?:,\d+)?(?:\.\d+)?)\s*(?:million|m)\s*(?:people|affected|displaced|homeless|dead|injured)', 1000000),
        (r'(\d+(?:,\d+)?(?:\.\d+)?)\s*(?:thousand|k)\s*(?:people|affected|displaced|homeless|dead|injured)', 1000),
        (r'(\d+(?:,\d+)?)\s*(?:people|victims|residents|families|households)\s*(?:affected|displaced|homeless|evacuated|dead|killed|injured)', 1),
        (r'(?:affected|displaced|homeless|evacuated|dead|killed|injured)\s*(?:approximately|about|around|over|more than)?\s*(\d+(?:,\d+)?)', 1),
    ]
    
    estimates = {
        "affected": None,
        "displaced": None,
        "dead": None,
        "injured": None,
        "evacuated": None,
        "missing": None
    }
    
    for pattern, multiplier in patterns:
        matches = re.findall(pattern, text_lower)
        for match in matches:
            num_str = match.replace(',', '')
            try:
                num = int(float(num_str) * multiplier)
                if 'dead' in pattern or 'killed' in pattern:
                    estimates["dead"] = num
                elif 'injured' in pattern:
                    estimates["injured"] = num
                elif 'displaced' in pattern or 'homeless' in pattern:
                    estimates["displaced"] = num
                elif 'evacuated' in pattern:
                    estimates["evacuated"] = num
                elif 'missing' in pattern:
                    estimates["missing"] = num
                else:
                    estimates["affected"] = num
            except:
                pass
    
    return {k: v for k, v in estimates.items() if v is not None}

def calculate_comprehensive_credibility(result: dict, platform_info: dict, text: str, donation_analysis: dict, freshness: dict) -> dict:
    """Calculate comprehensive credibility score with detailed factors."""
    
    factors = []
    score = platform_info.get("base_trust", 0.3)
    
    tier = platform_info.get("tier", 4)
    tier_names = {1: "Official Government", 2: "Major News Agency", 3: "Social Media", 4: "Unknown"}
    factors.append({
        "category": "Source",
        "factor": f"{tier_names.get(tier, 'Unknown')} Source ({platform_info.get('platform_name', 'Unknown')})",
        "impact": f"Base: {int(platform_info.get('base_trust', 0.3) * 100)}%",
        "positive": tier <= 2
    })
    
    ai_confidence = result.get("confidence", 0.5)
    if ai_confidence >= 0.8:
        score += 0.1
        factors.append({"category": "AI", "factor": "High AI Confidence", "impact": "+10%", "positive": True})
    elif ai_confidence < 0.4:
        score -= 0.15
        factors.append({"category": "AI", "factor": "Low AI Confidence", "impact": "-15%", "positive": False})
    
    location = result.get("location", {})
    if location.get("latitude") and location.get("longitude"):
        score += 0.1
        factors.append({"category": "Location", "factor": "GPS Coordinates Available", "impact": "+10%", "positive": True})
    elif location.get("city") or location.get("country"):
        score += 0.05
        factors.append({"category": "Location", "factor": "Named Location Found", "impact": "+5%", "positive": True})
    else:
        score -= 0.1
        factors.append({"category": "Location", "factor": "No Location Data", "impact": "-10%", "positive": False})
    
    if freshness.get("freshness") == "potentially_outdated":
        score -= 0.25
        factors.append({"category": "Freshness", "factor": "Potentially Outdated/Recycled Content", "impact": "-25%", "positive": False})
    else:
        factors.append({"category": "Freshness", "factor": "Content Appears Current", "impact": "+0%", "positive": True})
    
    if donation_analysis.get("donation_trust") == "scam_likely":
        score -= 0.3
        factors.append({"category": "Donations", "factor": "SCAM INDICATORS DETECTED", "impact": "-30%", "positive": False})
    elif donation_analysis.get("donation_trust") == "verified":
        score += 0.05
        factors.append({"category": "Donations", "factor": "Verified Charity Links", "impact": "+5%", "positive": True})
    elif donation_analysis.get("donation_urls"):
        factors.append({"category": "Donations", "factor": "Unverified Donation Links", "impact": "-5%", "positive": False})
        score -= 0.05
    
    sensational = ["BREAKING", "EXCLUSIVE", "SHOCKING", "VIRAL", "YOU WON'T BELIEVE", "SHARE NOW"]
    found_sensational = [s for s in sensational if s in text.upper()]
    if found_sensational:
        score -= 0.1
        factors.append({"category": "Language", "factor": f"Sensationalist: {', '.join(found_sensational[:2])}", "impact": "-10%", "positive": False})
    
    if result.get("contact_info"):
        score += 0.05
        factors.append({"category": "Contact", "factor": "Contact Info Provided", "impact": "+5%", "positive": True})
    
    if result.get("people_affected") or result.get("vulnerable_groups"):
        score += 0.05
        factors.append({"category": "Details", "factor": "Specific Impact Data", "impact": "+5%", "positive": True})
    
    score = max(0.05, min(0.99, score))
    
    if score >= 0.80:
        status = "verified"
        status_text = "HIGHLY CREDIBLE"
        recommendation = "This report appears credible and can be acted upon with confidence."
    elif score >= 0.60:
        status = "likely_credible"
        status_text = "LIKELY CREDIBLE"
        recommendation = "This report is probably legitimate but verify key details before major resource allocation."
    elif score >= 0.40:
        status = "needs_verification"
        status_text = "NEEDS VERIFICATION"
        recommendation = "Cross-reference with official sources before taking action."
    elif score >= 0.25:
        status = "suspicious"
        status_text = "SUSPICIOUS"
        recommendation = "Multiple red flags detected. Verify thoroughly before sharing or acting."
    else:
        status = "likely_fake"
        status_text = "LIKELY FAKE/SCAM"
        recommendation = "DO NOT SHARE. High likelihood of misinformation or scam."
    
    return {
        "score": round(score, 2),
        "percentage": int(score * 100),
        "status": status,
        "status_text": status_text,
        "recommendation": recommendation,
        "factors": factors
    }

# ============== API ENDPOINTS ==============

@app.get("/")
async def root():
    return {"status": "online", "service": "Disaster Intelligence Agent", "version": "2.0"}

@app.post("/analyze")
async def analyze_disaster(request: AnalysisRequest):
    """Main analysis endpoint for text and URLs."""
    try:
        original_input = request.text
        platform_info = {"platform": "user_report", "platform_name": "User Report", "tier": 3, "base_trust": 0.40, "is_official": False}
        
        is_url = request.text.strip().startswith(("http://", "https://"))
        
        if is_url:
            platform_info = detect_platform_enhanced(request.text)
            result = agent.process_url(request.text)
        else:
            result = agent.process_text(request.text, source=request.source)
        
        result_dict = result.model_dump()
        
        donation_analysis = analyze_donation_links(original_input + " " + result_dict.get("normalized_text", ""))
        freshness = check_content_freshness(original_input + " " + result_dict.get("normalized_text", ""))
        people_estimates = extract_people_estimates(original_input + " " + result_dict.get("normalized_text", ""))
        
        if people_estimates:
            result_dict["people_estimates"] = people_estimates
            if not result_dict.get("people_affected") and people_estimates.get("affected"):
                result_dict["people_affected"] = people_estimates["affected"]
        
        credibility = calculate_comprehensive_credibility(result_dict, platform_info, original_input, donation_analysis, freshness)
        
        result_dict["source_analysis"] = {
            "platform": platform_info["platform"],
            "platform_name": platform_info["platform_name"],
            "trust_tier": platform_info["tier"],
            "is_official_source": platform_info["is_official"],
            "input_type": "url" if is_url else "text"
        }
        
        result_dict["credibility"] = credibility
        result_dict["donation_analysis"] = donation_analysis
        result_dict["freshness_analysis"] = freshness
        
        result_dict["agent_workflow"] = {
            "steps_completed": [
                "Input Classification",
                "Content Extraction" if is_url else "Text Processing",
                "Disaster Classification",
                "Location Extraction",
                "Urgency Assessment",
                "Donation Link Analysis",
                "Freshness Verification",
                "Credibility Scoring"
            ],
            "model_used": "Gemini/Groq LLM",
            "processing_timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        return result_dict
        
    except Exception as e:
        import traceback
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.post("/analyze-image")
async def analyze_image(request: ImageAnalysisRequest):
    """Analyze disaster from image URL."""
    try:
        result = agent.process_image(request.image_url)
        result_dict = result.model_dump()
        
        if not result_dict["location"].get("city") and not result_dict["location"].get("latitude"):
            result_dict["location"]["raw_text"] = result_dict["location"].get("raw_text") or "Location could not be determined from image"
        
        donation_analysis = analyze_donation_links(result_dict.get("normalized_text", ""))
        freshness = {"freshness": "unknown", "warning": "Cannot determine freshness from image alone"}
        
        platform_info = {"platform": "image", "platform_name": "Image Analysis", "tier": 4, "base_trust": 0.25, "is_official": False}
        
        credibility = calculate_comprehensive_credibility(result_dict, platform_info, "", donation_analysis, freshness)
        credibility["factors"].append({
            "category": "Media",
            "factor": "Image Source - Requires Visual Verification",
            "impact": "-15%",
            "positive": False
        })
        credibility["score"] = max(0.1, credibility["score"] - 0.15)
        credibility["percentage"] = int(credibility["score"] * 100)
        
        result_dict["source_analysis"] = {
            "platform": "image_url",
            "platform_name": "Image URL",
            "trust_tier": 4,
            "is_official_source": False,
            "input_type": "image_url",
            "image_url": request.image_url
        }
        
        result_dict["credibility"] = credibility
        result_dict["donation_analysis"] = donation_analysis
        result_dict["freshness_analysis"] = freshness
        
        result_dict["agent_workflow"] = {
            "steps_completed": [
                "Image Download",
                "Vision AI Analysis",
                "Scene Description",
                "Disaster Classification",
                "Location Extraction (from visual cues)",
                "Damage Assessment",
                "Credibility Scoring"
            ],
            "model_used": "Gemini Vision",
            "processing_timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        return result_dict
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image analysis failed: {str(e)}")

@app.post("/analyze-image-upload")
async def analyze_image_upload(file: UploadFile = File(...)):
    """Analyze uploaded image file."""
    try:
        contents = await file.read()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file.filename.split('.')[-1] if '.' in file.filename else 'jpg'}") as tmp:
            tmp.write(contents)
            tmp_path = tmp.name
        
        try:
            result = agent.process_image(tmp_path)
            result_dict = result.model_dump()
            
            if not result_dict["location"].get("city") and not result_dict["location"].get("latitude"):
                result_dict["location"]["raw_text"] = result_dict["location"].get("raw_text") or "Location could not be determined from image"
            
            donation_analysis = analyze_donation_links(result_dict.get("normalized_text", ""))
            freshness = {"freshness": "unknown", "warning": "Cannot determine freshness from image alone"}
            
            platform_info = {"platform": "image_upload", "platform_name": "Direct Upload", "tier": 3, "base_trust": 0.35, "is_official": False}
            
            credibility = calculate_comprehensive_credibility(result_dict, platform_info, "", donation_analysis, freshness)
            credibility["factors"].append({
                "category": "Media",
                "factor": "Direct Image Upload - User Provided",
                "impact": "+5%",
                "positive": True
            })
            
            result_dict["source_analysis"] = {
                "platform": "image_upload",
                "platform_name": "Direct Upload",
                "trust_tier": 3,
                "is_official_source": False,
                "input_type": "image_upload",
                "filename": file.filename
            }
            
            result_dict["credibility"] = credibility
            result_dict["donation_analysis"] = donation_analysis
            result_dict["freshness_analysis"] = freshness
            
            result_dict["agent_workflow"] = {
                "steps_completed": [
                    "File Upload Processing",
                    "Image Validation",
                    "Vision AI Analysis",
                    "Scene Description",
                    "Disaster Classification",
                    "Location Extraction (from visual cues)",
                    "Damage Assessment",
                    "Credibility Scoring"
                ],
                "model_used": "Gemini Vision",
                "processing_timestamp": datetime.utcnow().isoformat() + "Z"
            }
            
            return result_dict
            
        finally:
            os.unlink(tmp_path)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image upload analysis failed: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
