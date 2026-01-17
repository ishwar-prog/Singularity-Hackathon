#!/usr/bin/env python3
"""Interactive CLI for Disaster Intake Agent"""
import json
from dotenv import load_dotenv
load_dotenv()

from agents.intake_agent import ExtendedDisasterAgent

def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║        🚨 DISASTER RELIEF RESOURCE SCOUT 🚨                  ║
║                                                              ║
║  Paste any of the following:                                 ║
║  • Raw text (emergency message)                              ║
║  • URL (news article, social media post)                     ║
║  • Image path or URL (.jpg, .png)                           ║
║                                                              ║
║  Commands: 'rss' = fetch live disaster feeds                 ║
║            'quit' = exit                                     ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    agent = ExtendedDisasterAgent()
    
    while True:
        try:
            print("\n" + "─"*60)
            user_input = input("📥 Enter text/URL/image path: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
            
            if user_input.lower() == 'rss':
                print("\n📡 Fetching live disaster feeds...")
                from agents.intake_agent.extractors import extract_from_rss
                entries = extract_from_rss()
                print(f"Found {len(entries)} alerts:\n")
                for i, entry in enumerate(entries[:5], 1):
                    print(f"{i}. {entry['text'][:100]}...")
                    print(f"   🔗 {entry['url']}\n")
                continue
            
            print("\n⏳ Processing...")
            result = agent.process_any(user_input)
            
            # Pretty print result
            print("\n" + "="*60)
            print("📋 ANALYSIS RESULT")
            print("="*60)
            print(f"🆔 Request ID: {result.request_id}")
            print(f"⏰ Timestamp: {result.timestamp}")
            print(f"🌐 Platform: {result.source_platform}")
            print(f"🗣️ Language: {result.source_language}")
            print()
            print(f"🔥 Disaster Type: {result.disaster_type.upper()}")
            print(f"📦 Need Type: {result.need_type}")
            print(f"⚠️ URGENCY: {result.urgency.upper()}")
            print(f"👥 People Affected: {result.people_affected or 'Unknown'}")
            print(f"🏥 Vulnerable Groups: {', '.join(result.vulnerable_groups) or 'None identified'}")
            print()
            print(f"📍 Location: {result.location.raw_text or 'Unknown'}")
            if result.location.city:
                print(f"   City: {result.location.city}")
            print(f"📞 Contact: {result.contact_info or 'None'}")
            print()
            print(f"📊 Confidence: {result.confidence:.0%}")
            if result.flags:
                print(f"🚩 Flags: {', '.join(result.flags)}")
            print()
            print("📝 Normalized Text:")
            print(f"   {result.normalized_text[:200]}...")
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()
