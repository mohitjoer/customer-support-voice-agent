"""
Diagnostic tool to check Twilio SIP trunk and call configuration.
"""
import asyncio
import os
from dotenv import load_dotenv
from livekit import api

load_dotenv(".env.local")

LIVEKIT_URL = os.getenv("LIVEKIT_URL")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")
LIVEKIT_TRUNK_ID = os.getenv("LIVEKIT_TUNK_ID")


async def diagnose():
    """Run diagnostics on the SIP trunk configuration."""
    
    print("\n" + "="*70)
    print("🔍 LiveKit + Twilio SIP Trunk Diagnostics")
    print("="*70)
    
    # Check environment variables
    print("\n1️⃣  Checking Environment Variables...")
    print("-" * 70)
    
    issues = []
    
    if not LIVEKIT_URL:
        issues.append("❌ LIVEKIT_URL is not set")
    else:
        print(f"✅ LIVEKIT_URL: {LIVEKIT_URL}")
    
    if not LIVEKIT_API_KEY:
        issues.append("❌ LIVEKIT_API_KEY is not set")
    else:
        print(f"✅ LIVEKIT_API_KEY: {LIVEKIT_API_KEY[:10]}...")
    
    if not LIVEKIT_API_SECRET:
        issues.append("❌ LIVEKIT_API_SECRET is not set")
    else:
        print(f"✅ LIVEKIT_API_SECRET: {LIVEKIT_API_SECRET[:10]}...")
    
    if not LIVEKIT_TRUNK_ID:
        issues.append("❌ LIVEKIT_TUNK_ID is not set")
    else:
        print(f"✅ LIVEKIT_TRUNK_ID: {LIVEKIT_TRUNK_ID}")
    
    if issues:
        print("\n❌ Configuration Issues Found:")
        for issue in issues:
            print(f"   {issue}")
        return
    
    # Try to connect to LiveKit API
    print("\n2️⃣  Testing LiveKit API Connection...")
    print("-" * 70)
    
    try:
        lk_api = api.LiveKitAPI(
            url=LIVEKIT_URL,
            api_key=LIVEKIT_API_KEY,
            api_secret=LIVEKIT_API_SECRET,
        )
        
        # Try to list rooms
        rooms = await lk_api.room.list_rooms(api.ListRoomsRequest())
        print(f"✅ Successfully connected to LiveKit")
        print(f"   Active rooms: {len(rooms.rooms)}")
        
        # Try to get SIP trunk info
        print("\n3️⃣  Checking SIP Trunk Configuration...")
        print("-" * 70)
        
        try:
            # List SIP trunks
            trunks_response = await lk_api.sip.list_sip_trunk(api.ListSIPTrunkRequest())
            trunks = trunks_response.items
            
            print(f"✅ Found {len(trunks)} SIP trunk(s) configured")
            
            trunk_found = False
            for trunk in trunks:
                print(f"\n   Trunk ID: {trunk.sip_trunk_id}")
                print(f"   Name: {trunk.name or 'N/A'}")
                print(f"   Outbound Enabled: {trunk.outbound_number or 'N/A'}")
                
                if trunk.sip_trunk_id == LIVEKIT_TRUNK_ID:
                    trunk_found = True
                    print(f"   ✅ This matches your LIVEKIT_TUNK_ID")
            
            if not trunk_found:
                print(f"\n   ⚠️  WARNING: Your LIVEKIT_TRUNK_ID ({LIVEKIT_TRUNK_ID}) was not found!")
                print(f"   Available trunk IDs:")
                for trunk in trunks:
                    print(f"      - {trunk.sip_trunk_id}")
            
        except Exception as e:
            print(f"⚠️  Could not retrieve SIP trunk info: {e}")
        
        await lk_api.aclose()
        
    except Exception as e:
        print(f"❌ Failed to connect to LiveKit: {e}")
        return
    
    # Provide recommendations
    print("\n4️⃣  Recommendations")
    print("-" * 70)
    print("""
📋 Next Steps to Debug Your Call Issue:

1. **Check Twilio Console:**
   - Go to: https://console.twilio.com/us1/monitor/logs/calls
   - Look for calls to +919829007613
   - Check the error message or status

2. **Verify Phone Number:**
   - Indian numbers must include country code: +91
   - Your number: +919829007613
   - Make sure this number can receive calls

3. **Check LiveKit SIP Configuration:**
   - Go to: https://cloud.livekit.io/projects
   - Navigate to: Settings → SIP
   - Verify Twilio trunk is properly configured
   - Check outbound calling is enabled
   - Verify the trunk has outbound numbers configured

4. **Twilio Account Check:**
   - Ensure your Twilio account has credits
   - Verify international calling is enabled (for India: +91)
   - Check if your account is in trial mode (trial accounts have restrictions)
   - If trial mode: You can only call verified numbers

5. **Test with Different Number:**
   - Try calling a verified/test number first
   - If you're in Twilio trial, verify +919829007613 in Twilio console

6. **Check LiveKit Logs:**
   - The quick disconnect suggests the call didn't establish
   - This usually means Twilio couldn't route the call

⚠️  MOST COMMON ISSUE:
   If your Twilio account is in TRIAL MODE, you can only call phone
   numbers that you've verified in the Twilio console. 
   
   Solution: Either verify +919829007613 in Twilio, or upgrade your account.
""")
    
    print("="*70)
    print("✅ Diagnostics Complete")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(diagnose())
