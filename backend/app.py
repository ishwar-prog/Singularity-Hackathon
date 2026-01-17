"""Streamlit Web UI for Disaster Relief Resource Scout"""
import streamlit as st
import json
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from agents.intake_agent import ExtendedDisasterAgent, DisasterIntakeRequest
from agents.intake_agent.extractors import extract_from_rss, extract_from_reddit

# Page config
st.set_page_config(
    page_title="Disaster Relief Scout",
    page_icon="🚨",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .urgency-critical { background-color: #ff4444; color: white; padding: 5px 15px; border-radius: 5px; font-weight: bold; }
    .urgency-high { background-color: #ff8800; color: white; padding: 5px 15px; border-radius: 5px; font-weight: bold; }
    .urgency-medium { background-color: #ffcc00; color: black; padding: 5px 15px; border-radius: 5px; font-weight: bold; }
    .urgency-low { background-color: #44aa44; color: white; padding: 5px 15px; border-radius: 5px; font-weight: bold; }
    .result-card { border: 1px solid #ddd; border-radius: 10px; padding: 20px; margin: 10px 0; }
    .metric-box { background: #f0f2f6; padding: 10px; border-radius: 5px; text-align: center; }
</style>
""", unsafe_allow_html=True)

# Initialize agent
@st.cache_resource
def get_agent():
    return ExtendedDisasterAgent()

agent = get_agent()

# Header
st.title("🚨 Disaster Relief Resource Scout")
st.markdown("*AI-powered disaster report intake and normalization*")

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    
    source_platform = st.selectbox(
        "Source Platform",
        ["auto-detect", "twitter", "facebook", "whatsapp", "sms", "web", "radio", "unknown"]
    )
    
    st.divider()
    
    st.header("📡 Live Feeds")
    
    if st.button("🌍 Fetch USGS Earthquakes", use_container_width=True):
        with st.spinner("Fetching live data..."):
            entries = extract_from_rss(feed_name="usgs_earthquakes")
            st.session_state['rss_entries'] = entries
            st.success(f"Found {len(entries)} alerts!")
    
    if st.button("🌊 Fetch GDACS Alerts", use_container_width=True):
        with st.spinner("Fetching live data..."):
            entries = extract_from_rss(feed_name="gdacs")
            st.session_state['rss_entries'] = entries
            st.success(f"Found {len(entries)} alerts!")
    
    if st.button("📰 Fetch ReliefWeb", use_container_width=True):
        with st.spinner("Fetching live data..."):
            entries = extract_from_rss(feed_name="reliefweb")
            st.session_state['rss_entries'] = entries
            st.success(f"Found {len(entries)} alerts!")

# Main content tabs
tab1, tab2, tab3, tab4 = st.tabs(["📝 Text Input", "🔗 URL Input", "📷 Image Input", "📡 Live Feeds"])

def display_result(result: DisasterIntakeRequest):
    """Display analysis result in a nice format"""
    
    # Urgency badge
    urgency_class = f"urgency-{result.urgency}"
    st.markdown(f'<span class="{urgency_class}">⚠️ {result.urgency.upper()}</span>', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("🔥 Disaster Type", result.disaster_type.upper())
    with col2:
        st.metric("📦 Need Type", result.need_type)
    with col3:
        st.metric("👥 People Affected", result.people_affected or "Unknown")
    with col4:
        st.metric("📊 Confidence", f"{result.confidence:.0%}")
    
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📍 Location")
        if result.location.raw_text:
            st.write(f"**Raw:** {result.location.raw_text}")
        if result.location.city:
            st.write(f"**City:** {result.location.city}")
        if result.location.region:
            st.write(f"**Region:** {result.location.region}")
        if result.location.country:
            st.write(f"**Country:** {result.location.country}")
        if not any([result.location.raw_text, result.location.city]):
            st.write("*Location not identified*")
    
    with col2:
        st.subheader("🏥 Vulnerable Groups")
        if result.vulnerable_groups:
            for group in result.vulnerable_groups:
                st.write(f"• {group.capitalize()}")
        else:
            st.write("*None identified*")
        
        if result.contact_info:
            st.subheader("📞 Contact")
            st.write(result.contact_info)
    
    st.divider()
    
    st.subheader("📝 Normalized Text")
    st.info(result.normalized_text)
    
    if result.flags:
        st.subheader("🚩 Flags")
        st.write(", ".join(result.flags))
    
    # Expandable JSON
    with st.expander("📋 View Full JSON"):
        st.json(result.model_dump())

# Tab 1: Text Input
with tab1:
    st.subheader("Enter disaster report text")
    
    text_input = st.text_area(
        "Paste emergency message, social media post, or any disaster-related text:",
        height=150,
        placeholder="Example: HELP! We are trapped on the roof at 123 Main Street. Water rising fast. 3 adults, 2 children, elderly woman with heart condition. Phone dying!"
    )
    
    col1, col2 = st.columns([1, 4])
    with col1:
        process_text = st.button("🔍 Analyze Text", type="primary", use_container_width=True)
    
    if process_text and text_input:
        with st.spinner("Processing with AI..."):
            try:
                platform = "unknown" if source_platform == "auto-detect" else source_platform
                result = agent.process_text(text_input, source=platform)
                st.success("✅ Analysis Complete!")
                display_result(result)
            except Exception as e:
                st.error(f"Error: {e}")

# Tab 2: URL Input
with tab2:
    st.subheader("Extract from URL")
    
    url_input = st.text_input(
        "Paste news article or social media URL:",
        placeholder="https://example.com/disaster-news-article"
    )
    
    col1, col2 = st.columns([1, 4])
    with col1:
        process_url = st.button("🔗 Extract & Analyze", type="primary", use_container_width=True)
    
    if process_url and url_input:
        with st.spinner("Extracting content from URL..."):
            try:
                result = agent.process_url(url_input)
                st.success("✅ Extraction Complete!")
                display_result(result)
            except Exception as e:
                st.error(f"Error: {e}")

# Tab 3: Image Input
with tab3:
    st.subheader("Analyze disaster image")
    
    upload_col, url_col = st.columns(2)
    
    with upload_col:
        st.write("**Upload Image**")
        uploaded_file = st.file_uploader("Choose an image", type=['jpg', 'jpeg', 'png', 'webp'])
        
        if uploaded_file:
            st.image(uploaded_file, caption="Uploaded Image", use_container_width=True)
            
            if st.button("🔍 Analyze Uploaded Image", type="primary"):
                with st.spinner("Analyzing image with AI Vision..."):
                    try:
                        # Save temp file
                        import tempfile
                        import os
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                            tmp.write(uploaded_file.getvalue())
                            tmp_path = tmp.name
                        
                        result = agent.process_image(tmp_path)
                        os.unlink(tmp_path)
                        
                        st.success("✅ Image Analysis Complete!")
                        display_result(result)
                    except Exception as e:
                        st.error(f"Error: {e}")
    
    with url_col:
        st.write("**Or paste image URL**")
        image_url = st.text_input("Image URL:", placeholder="https://example.com/disaster-image.jpg")
        
        if image_url:
            st.image(image_url, caption="Image from URL", use_container_width=True)
            
            if st.button("🔍 Analyze Image URL", type="primary"):
                with st.spinner("Analyzing image with AI Vision..."):
                    try:
                        result = agent.process_image(image_url)
                        st.success("✅ Image Analysis Complete!")
                        display_result(result)
                    except Exception as e:
                        st.error(f"Error: {e}")

# Tab 4: Live Feeds
with tab4:
    st.subheader("📡 Live Disaster Feeds")
    
    if 'rss_entries' in st.session_state and st.session_state['rss_entries']:
        entries = st.session_state['rss_entries']
        
        st.write(f"**{len(entries)} alerts found** - Click to analyze:")
        
        for i, entry in enumerate(entries[:10]):
            with st.expander(f"📌 {entry['text'][:80]}..."):
                st.write(entry['text'])
                st.write(f"🔗 [Source]({entry['url']})")
                
                if st.button(f"Analyze Alert #{i+1}", key=f"rss_{i}"):
                    with st.spinner("Processing..."):
                        try:
                            result = agent.process_text(entry['text'], source="web")
                            display_result(result)
                        except Exception as e:
                            st.error(f"Error: {e}")
    else:
        st.info("👈 Click a feed button in the sidebar to fetch live alerts!")
        
        st.markdown("""
        **Available Feeds:**
        - 🌍 **USGS Earthquakes** - Real-time significant earthquakes worldwide
        - 🌊 **GDACS** - Global Disaster Alert and Coordination System
        - 📰 **ReliefWeb** - Humanitarian news and reports
        """)

# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: #888;'>
    🚨 Disaster Relief Resource Scout | Built for Singularity Hackathon 2026<br>
    Powered by Groq LLaMA 3.3 | Real-time data from USGS, GDACS, ReliefWeb
</div>
""", unsafe_allow_html=True)
