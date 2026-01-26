import asyncio
import os
from livekit import api
from dotenv import load_dotenv

load_dotenv('.env.local')

async def setup_inbound():
    lkapi = api.LiveKitAPI()
    
    # Create inbound trunk
    trunk_request = api.CreateSIPInboundTrunkRequest(
        trunk=api.SIPInboundTrunkInfo(
            name="vobiz-inbound",
            numbers=[os.getenv("VOBIZ_INBOUND_NUMBER")],  # +912271264242
            allowed_addresses=["192.0.2.0/24", "192.0.2.100"],  # Vobiz IPs
        )
    )
    
    trunk = await lkapi.sip.create_sip_inbound_trunk(trunk_request)
    print(f"✅ Created inbound trunk: {trunk.sip_trunk_id}")
    
    # Create dispatch rule
    dispatch_request = api.CreateSIPDispatchRuleRequest(
        rule=api.SIPDispatchRule(
            name="inbound-test",
            trunk_ids=[trunk.sip_trunk_id],
            rule=api.SIPDispatchRuleIndividual(
                room_prefix="call-",
            ),
        ),
        room_config=api.RoomConfiguration(
            agents=[
                api.RoomAgentDispatch(
                    agent_name="high-time-store-support",  # Must match agent code
                )
            ]
        ),
    )
    
    dispatch = await lkapi.sip.create_sip_dispatch_rule(dispatch_request)
    print(f"✅ Created dispatch rule: {dispatch.sip_dispatch_rule_id}")
    
    await lkapi.aclose()

if __name__ == "__main__":
    asyncio.run(setup_inbound())