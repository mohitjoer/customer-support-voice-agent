"""
Outbound calling functionality using LiveKit and Twilio SIP trunk.
"""
import asyncio
import logging
import os
from typing import Optional

from dotenv import load_dotenv
from livekit import api

load_dotenv(".env.local")

logger = logging.getLogger("outbound_caller")

# LiveKit and Twilio Configuration
LIVEKIT_URL = os.getenv("LIVEKIT_URL")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")
LIVEKIT_TRUNK_ID = os.getenv("LIVEKIT_TUNK_ID")


async def create_outbound_call(
    phone_number: str,
    room_name: Optional[str] = None,
    identity: Optional[str] = None,
    metadata: Optional[str] = None,
) -> dict:
    """
    Create an outbound call using LiveKit SIP with Twilio trunk.
    
    Args:
        phone_number: The phone number to call (E.164 format, e.g., +1234567890)
        room_name: Optional room name (will be auto-generated if not provided)
        identity: Optional participant identity
        metadata: Optional metadata to attach to the call
    
    Returns:
        Dictionary containing room details and call information
    """
    if not all([LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, LIVEKIT_TRUNK_ID]):
        raise ValueError(
            "Missing required environment variables: LIVEKIT_URL, LIVEKIT_API_KEY, "
            "LIVEKIT_API_SECRET, LIVEKIT_TUNK_ID"
        )
    
    # Validate phone number format
    if not phone_number.startswith("+"):
        raise ValueError("Phone number must be in E.164 format (e.g., +1234567890)")
    
    # Create LiveKit API client
    lk_api = api.LiveKitAPI(
        url=LIVEKIT_URL,
        api_key=LIVEKIT_API_KEY,
        api_secret=LIVEKIT_API_SECRET,
    )
    
    # Generate room name if not provided
    if not room_name:
        import time
        room_name = f"outbound-{int(time.time())}"
    
    # Generate identity if not provided
    if not identity:
        identity = f"caller-{phone_number.replace('+', '')}"
    
    try:
        # Create the room first
        logger.info(f"Creating room: {room_name}")
        room = await lk_api.room.create_room(
            api.CreateRoomRequest(name=room_name)
        )
        logger.info(f"Room created: {room.name}")
        
        # Create SIP outbound call
        logger.info(f"Creating outbound call to {phone_number}")
        sip_request = api.CreateSIPParticipantRequest(
            sip_trunk_id=LIVEKIT_TRUNK_ID,
            sip_call_to=phone_number,
            room_name=room_name,
            participant_identity=identity,
            participant_name=f"Caller {phone_number}",
            participant_metadata=metadata or "",
            # REMOVED: secure_media=True - this field doesn't exist!
            # SRTP is handled automatically by the trunk's TLS configuration
        )
        
        sip_participant = await lk_api.sip.create_sip_participant(sip_request)
        
        logger.info(f"Outbound call initiated successfully")
        logger.info(f"SIP Participant ID: {sip_participant.participant_id}")
        logger.info(f"Room: {room_name}")
        
        return {
            "success": True,
            "room_name": room_name,
            "room_sid": room.sid,
            "phone_number": phone_number,
            "participant_id": sip_participant.participant_id,
            "participant_identity": sip_participant.participant_identity,
            "sip_call_id": sip_participant.sip_call_id,
        }
        
    except Exception as e:
        logger.error(f"Failed to create outbound call: {e}")
        raise
    finally:
        await lk_api.aclose()


async def main():
    """
    Example usage for testing outbound calls.
    """
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python outbound_caller.py <phone_number>")
        print("Example: python outbound_caller.py +1234567890")
        sys.exit(1)
    
    phone_number = sys.argv[1]
    
    try:
        result = await create_outbound_call(phone_number)
        print("\n✅ Outbound call created successfully!")
        print(f"📞 Calling: {result['phone_number']}")
        print(f"🏠 Room: {result['room_name']}")
        print(f"🆔 Participant ID: {result['participant_id']}")
        print(f"📞 SIP Call ID: {result['sip_call_id']}")
        print("\nThe agent will handle the call automatically.")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())