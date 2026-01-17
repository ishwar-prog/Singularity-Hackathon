"""Disaster Intake Schema - DO NOT MODIFY"""
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
import uuid

class Location(BaseModel):
    raw_text: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None

class DisasterIntakeRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    
    # Source metadata
    source_platform: Literal["twitter", "facebook", "whatsapp", "sms", "web", "radio", "unknown"] = "unknown"
    source_language: str = "en"
    original_text: str
    normalized_text: str
    
    # Classification
    disaster_type: Literal["earthquake", "flood", "hurricane", "wildfire", "tsunami", "tornado", "landslide", "drought", "other", "unknown"] = "unknown"
    need_type: Literal["medical", "food", "water", "shelter", "rescue", "evacuation", "supplies", "information", "other", "unknown"] = "unknown"
    
    # Urgency & Impact
    urgency: Literal["critical", "high", "medium", "low"] = "medium"
    people_affected: Optional[int] = None
    vulnerable_groups: list[Literal["children", "elderly", "disabled", "pregnant", "injured"]] = []
    
    # Location
    location: Location = Field(default_factory=Location)
    
    # Contact
    contact_info: Optional[str] = None
    
    # Confidence
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    flags: list[str] = []

SCHEMA_JSON = DisasterIntakeRequest.model_json_schema()
