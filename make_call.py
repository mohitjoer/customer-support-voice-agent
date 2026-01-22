"""
Simple CLI tool for making outbound calls.
Usage: python make_call.py <phone_number>
"""
import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.outbound_caller import create_outbound_call


async def make_call(phone_number: str):
    """Make an outbound call to the specified phone number."""
    print(f"\n📞 Initiating outbound call to {phone_number}...")
    print("=" * 60)
    
    try:
        result = await create_outbound_call(phone_number)
        
        print("\n✅ Call initiated successfully!")
        print("=" * 60)
        print(f"📱 Phone Number: {result['phone_number']}")
        print(f"🏠 Room Name: {result['room_name']}")
        print(f"🆔 Room SID: {result['room_sid']}")
        print(f"👤 Participant ID: {result['participant_id']}")
        print(f"📞 SIP Call ID: {result['sip_call_id']}")
        print("=" * 60)
        print("\n🤖 The AI agent will handle the call automatically.")
        print("💡 The call is now active and connected to your LiveKit agent.\n")
        
        return True
        
    except Exception as e:
        print("\n❌ Failed to initiate call!")
        print("=" * 60)
        print(f"Error: {e}")
        print("=" * 60)
        print("\n💡 Troubleshooting tips:")
        print("1. Verify your .env.local file has all required variables:")
        print("   - LIVEKIT_URL")
        print("   - LIVEKIT_API_KEY")
        print("   - LIVEKIT_API_SECRET")
        print("   - LIVEKIT_TUNK_ID")
        print("2. Make sure the phone number is in E.164 format (+1234567890)")
        print("3. Verify your Twilio SIP trunk is properly configured")
        print("4. Ensure your LiveKit agent is running (python src/agent.py dev)\n")
        return False


def main():
    if len(sys.argv) < 2:
        print("\n📞 Outbound Call CLI")
        print("=" * 60)
        print("Usage: python make_call.py <phone_number>")
        print("\nExample:")
        print("  python make_call.py +1234567890")
        print("\nNote: Phone number must be in E.164 format (starting with +)")
        print("=" * 60)
        sys.exit(1)
    
    phone_number = sys.argv[1]
    
    # Validate basic format
    if not phone_number.startswith("+"):
        print("\n❌ Error: Phone number must be in E.164 format")
        print("Example: +1234567890")
        sys.exit(1)
    
    success = asyncio.run(make_call(phone_number))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
