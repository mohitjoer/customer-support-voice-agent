"""
Update or create LiveKit SIP outbound trunk with proper TLS/SRTP configuration.
"""
import asyncio
import os
from dotenv import load_dotenv
from livekit import api
from livekit.protocol import sip

load_dotenv(".env.local")

async def list_trunks():
    """List all existing outbound trunks"""
    lk_api = api.LiveKitAPI(
        url=os.getenv("LIVEKIT_URL"),
        api_key=os.getenv("LIVEKIT_API_KEY"),
        api_secret=os.getenv("LIVEKIT_API_SECRET"),
    )
    
    try:
        print("\n📋 Listing existing outbound trunks...")
        print("=" * 60)
        
        trunks = await lk_api.sip.list_outbound_trunk(
            sip.ListSIPOutboundTrunkRequest()
        )
        
        if not trunks.items:
            print("No outbound trunks found.")
            return None
        
        for trunk in trunks.items:
            print(f"\nTrunk ID: {trunk.sip_trunk_id}")
            print(f"Name: {trunk.name}")
            print(f"Address: {trunk.address}")
            print(f"Numbers: {trunk.numbers}")
            print(f"Transport: {trunk.transport}")
            print(f"Auth Username: {trunk.auth_username}")
            print("-" * 60)
        
        return trunks.items
        
    finally:
        await lk_api.aclose()


async def update_existing_trunk(trunk_id: str):
    """Update an existing trunk with TLS transport"""
    lk_api = api.LiveKitAPI(
        url=os.getenv("LIVEKIT_URL"),
        api_key=os.getenv("LIVEKIT_API_KEY"),
        api_secret=os.getenv("LIVEKIT_API_SECRET"),
    )
    
    try:
        print(f"\n🔄 Updating trunk {trunk_id}...")
        print("=" * 60)
        
        # Update trunk with TLS transport
        updated_trunk = await lk_api.sip.update_outbound_trunk(
            trunk_id=trunk_id,
            trunk=sip.SIPOutboundTrunkInfo(
                name="numtwi",
                address="numtwi.pstn.twilio.com",
                numbers=["+17657521562"],
                auth_username="Number001001",
                auth_password="Number001001",
                transport=sip.SIPTransport.SIP_TRANSPORT_TLS,  # This enables SRTP!
            )
        )
        
        print("✅ Trunk updated successfully!")
        print(f"Trunk ID: {updated_trunk.sip_trunk_id}")
        print(f"Name: {updated_trunk.name}")
        print(f"Transport: {updated_trunk.transport}")
        print(f"Address: {updated_trunk.address}")
        
    finally:
        await lk_api.aclose()


async def create_new_trunk():
    """Create a new outbound trunk with TLS transport"""
    lk_api = api.LiveKitAPI(
        url=os.getenv("LIVEKIT_URL"),
        api_key=os.getenv("LIVEKIT_API_KEY"),
        api_secret=os.getenv("LIVEKIT_API_SECRET"),
    )
    
    try:
        print("\n🆕 Creating new outbound trunk...")
        print("=" * 60)
        
        # Create trunk with TLS transport
        trunk = await lk_api.sip.create_outbound_trunk(
            sip.CreateSIPOutboundTrunkRequest(
                trunk=sip.SIPOutboundTrunkInfo(
                    name="numtwi",
                    address="numtwi.pstn.twilio.com",
                    numbers=["+17657521562"],
                    auth_username="Number001001",
                    auth_password="Number001001",
                    transport=sip.SIPTransport.SIP_TRANSPORT_TLS,  # This enables SRTP!
                )
            )
        )
        
        print("✅ Trunk created successfully!")
        print(f"Trunk ID: {trunk.sip_trunk_id}")
        print(f"Name: {trunk.name}")
        print(f"Transport: {trunk.transport}")
        print(f"Address: {trunk.address}")
        print(f"\n⚠️  IMPORTANT: Update your .env.local file:")
        print(f"LIVEKIT_TUNK_ID={trunk.sip_trunk_id}")
        
    finally:
        await lk_api.aclose()


async def main():
    """Main function to manage trunk"""
    import sys
    
    print("\n🔧 LiveKit SIP Trunk Management")
    print("=" * 60)
    
    # First, list existing trunks
    trunks = await list_trunks()
    
    if not trunks:
        print("\n💡 No trunks found. Creating a new one...")
        await create_new_trunk()
        return
    
    # If trunk ID is provided, update that trunk
    if len(sys.argv) > 1:
        trunk_id = sys.argv[1]
        await update_existing_trunk(trunk_id)
        return
    
    # Otherwise, ask user what to do
    print("\n❓ What would you like to do?")
    print("1. Update existing trunk (enter trunk ID)")
    print("2. Create new trunk")
    print("\nUsage:")
    print("  Update: python update_trunk.py <trunk_id>")
    print("  Create: python update_trunk.py")
    print("\nOr run with the trunk ID from above to update it.")


if __name__ == "__main__":
    asyncio.run(main())