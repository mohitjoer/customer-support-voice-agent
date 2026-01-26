import logging
import os
import json
import re
from datetime import datetime
import asyncio

from dotenv import load_dotenv
from livekit import rtc, api
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    function_tool,
    RunContext,
    cli,
    inference,
    room_io,
)
from livekit.plugins import noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# LiveKit and Twilio Configuration
LIVEKIT_URL = os.getenv("LIVEKIT_URL")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")
LIVEKIT_TRUNK_ID = os.getenv("LIVEKIT_TUNK_ID")  # Outbound trunk
LIVEKIT_INBOUND_TRUNK_ID = os.getenv("LIVEKIT_INBOUND_TRUNK_ID")  # Inbound trunk  

# Ensure logs directory exists and configure a dedicated file logger for tool calls
LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)
TOOL_LOG_PATH = os.path.join(LOGS_DIR, "tool_calls.log")

# Add a file handler to the module logger that writes tool call summaries
if not any(isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", None) == TOOL_LOG_PATH for h in logger.handlers):
    fh = logging.FileHandler(TOOL_LOG_PATH)
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)

# Import MongoDB logger
try:
    from .mongodb_logger import get_mongo_logger, log_to_mongodb
except ImportError:
    try:
        from mongodb_logger import get_mongo_logger, log_to_mongodb
    except ImportError:
        # MongoDB logging not available
        def log_to_mongodb(*args, **kwargs):
            return False
        def get_mongo_logger():
            return None


def write_tool_log(tool_name: str, order_id: str, result: dict, room_name: str = None, participant_identity: str = None) -> None:
    """Append a JSON line summarizing a tool call to the tool log file and MongoDB."""
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "tool": tool_name,
        "order_id": order_id,
        "result": result,
    }
    try:
        # Write to file
        with open(TOOL_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        
        # Write to MongoDB
        log_to_mongodb(
            tool_name=tool_name,
            order_id=order_id,
            result=result,
            room_name=room_name,
            participant_identity=participant_identity,
        )
    except Exception:
        logger.exception("Failed to write tool log")


def normalize_order_id(raw: str) -> str:
    """Normalize spoken/typed order IDs to canonical uppercase alphanumeric form.

    Examples:
      "ht one zero zero four" -> "HT1004"
      "ht-1004" -> "HT1004"
      "ht1004" -> "HT1004"
    """
    if not raw:
        return ""
    # Keep only alphanumeric characters
    s = re.sub(r"[^0-9A-Za-z]", "", raw)
    return s.upper()

# Ensure ORDERS is defined at module level so linters/IDE can see the name.
ORDERS: dict = {}
try:
    from .fake_data import ORDERS  # type: ignore
except Exception:
    try:
        from fake_data import ORDERS  # type: ignore
    except Exception:
        ORDERS = {}


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""
You are a professional voice-based customer support assistant for High Time Store, running inside a LiveKit voice agent.

As soon as the user connects, greet the user with a short and polite welcome on behalf of High Time Store.

The user interacts with you through real-time speech.
Your responses must be short, natural, smooth, and suitable for spoken conversation.
Avoid emojis, symbols, and complex formatting.
Keep responses pause-friendly and low latency.

You support only the following actions:
- Check order status
- Track shipment
- Cancel an order
- Modify an order (address, quantity, item)
- Reorder a previous order
- Reschedule delivery
- Check payment status
- Provide invoice or receipt
- Check refund status
- Initiate a refund
- Assist with payment failures
- Change payment method

Order handling rules:
- Always ask for the order ID first if it is not provided.
- Use the order ID to fetch order details.

Verification rules:
- Do not verify identity for read-only actions:
  order status, shipment tracking, payment status, invoice or receipt, refund status.
- Require email verification for sensitive actions:
  cancel order, modify order, reschedule delivery, initiate refund, change payment method.
- Ask the user to confirm the order email ID.
- Proceed only if the email matches the order record.
- If verification fails, politely deny the action and offer escalation to a human agent.

Call completion:
- When the customer's request is fully resolved and they indicate they have no more questions, politely thank them and say goodbye.
- After saying goodbye, IMMEDIATELY call the end_call tool to disconnect the call.
- Always end the call after the conversation is complete.
- If the customer says goodbye, thanks, or indicates they're done, confirm their issue is resolved, say goodbye, and end the call.
- Do not wait for the customer to explicitly ask you to hang up - proactively end the call when the conversation naturally concludes.

LiveKit behavior:
- Assume streaming audio input and output.
- Handle interruptions gracefully.
- Never speak over the user.
- Escalate to a human agent when needed.

Tone:
Professional, calm, efficient, and friendly.
""",
        )

    @function_tool
    async def check_order_status(self, context: RunContext, order_id: str):
        """Read-only tool: Return order status and basic details for the given order_id."""
        logger.info("check_order_status called for %s", order_id)
        key = normalize_order_id(order_id)
        
        # Fetch order from MongoDB
        mongo_logger = get_mongo_logger()
        order = mongo_logger.get_order(key) if mongo_logger and mongo_logger.enabled else ORDERS.get(key)
        
        if not order:
            result = f"No order found with ID {key}."
            write_tool_log("check_order_status", key, {"error": result})
            return result

        result = {
            "order_id": order["order_id"],
            "status": order["status"],
            "items": order.get("items", []),
        }
        write_tool_log("check_order_status", key, result)
        return result

    @function_tool
    async def track_shipment(self, context: RunContext, order_id: str):
        """Read-only tool: Return shipment tracking information for the order."""
        logger.info("track_shipment called for %s", order_id)
        key = normalize_order_id(order_id)
        
        # Fetch order from MongoDB
        mongo_logger = get_mongo_logger()
        order = mongo_logger.get_order(key) if mongo_logger and mongo_logger.enabled else ORDERS.get(key)
        
        if not order:
            result = f"No order found with ID {key}."
            write_tool_log("track_shipment", key, {"error": result})
            return result

        result = order.get("shipment", {"status": "Unknown"})
        write_tool_log("track_shipment", key, result)
        return result

    @function_tool
    async def payment_status(self, context: RunContext, order_id: str):
        """Read-only tool: Return payment status and method details for the order."""
        logger.info("payment_status called for %s", order_id)
        key = normalize_order_id(order_id)
        
        # Fetch order from MongoDB
        mongo_logger = get_mongo_logger()
        order = mongo_logger.get_order(key) if mongo_logger and mongo_logger.enabled else ORDERS.get(key)
        
        if not order:
            result = f"No order found with ID {key}."
            write_tool_log("payment_status", key, {"error": result})
            return result

        result = order.get("payment", {"status": "Unknown"})
        write_tool_log("payment_status", key, result)
        return result

    @function_tool
    async def invoice_request(self, context: RunContext, order_id: str):
        """Read-only tool: Return invoice/receipt information for the order."""
        logger.info("invoice_request called for %s", order_id)
        key = normalize_order_id(order_id)
        
        # Fetch order from MongoDB
        mongo_logger = get_mongo_logger()
        order = mongo_logger.get_order(key) if mongo_logger and mongo_logger.enabled else ORDERS.get(key)
        
        if not order:
            result = f"No order found with ID {key}."
            write_tool_log("invoice_request", key, {"error": result})
            return result

        result = order.get("invoice", {"error": "No invoice available"})
        write_tool_log("invoice_request", key, result)
        return result

    @function_tool
    async def refund_status(self, context: RunContext, order_id: str):
        """Read-only tool: Return refund status for the order."""
        logger.info("refund_status called for %s", order_id)
        key = normalize_order_id(order_id)
        
        # Fetch order from MongoDB
        mongo_logger = get_mongo_logger()
        order = mongo_logger.get_order(key) if mongo_logger and mongo_logger.enabled else ORDERS.get(key)
        
        if not order:
            result = f"No order found with ID {key}."
            write_tool_log("refund_status", key, {"error": result})
            return result

        result = order.get("refund", {"status": "None", "amount": 0.0})
        write_tool_log("refund_status", key, result)
        return result

    @function_tool
    async def cancel_order(self, context: RunContext, order_id: str, email: str):
        """Sensitive tool: Cancel an order after email verification."""
        logger.info("cancel_order called for %s", order_id)
        key = normalize_order_id(order_id)
        
        # Fetch order from MongoDB
        mongo_logger = get_mongo_logger()
        order = mongo_logger.get_order(key) if mongo_logger and mongo_logger.enabled else ORDERS.get(key)

        if not order:
            result = f"No order found with ID {key}."
            write_tool_log("cancel_order", key, {"error": result})
            return result

        if order.get("email") != email:
            result = "Email verification failed. Order cancellation denied."
            write_tool_log("cancel_order", key, {"error": result})
            return result

        order["status"] = "Cancelled"
        result = {"order_id": key, "status": "Cancelled"}
        write_tool_log("cancel_order", key, result)
        return result

    @function_tool
    async def modify_order(
        self,
        context: RunContext,
        order_id: str,
        email: str,
        updates: str,
    ):
        """Sensitive tool: Modify order details after email verification.
        
        Args:
            order_id: The order ID to modify
            email: Email address for verification
            updates: JSON string describing changes (e.g., '{"address": "123 New St", "quantity": 2}')
        """
        logger.info("modify_order called for %s", order_id)
        key = normalize_order_id(order_id)
        
        # Fetch order from MongoDB (read-only)
        mongo_logger = get_mongo_logger()
        order = mongo_logger.get_order(key) if mongo_logger and mongo_logger.enabled else ORDERS.get(key)

        if not order:
            result = f"No order found with ID {key}."
            write_tool_log("modify_order", key, {"error": result})
            return result

        if order.get("email") != email:
            result = "Email verification failed. Order modification denied."
            write_tool_log("modify_order", key, {"error": result})
            return result

        # Parse updates from JSON string
        try:
            updates_dict = json.loads(updates) if isinstance(updates, str) else updates
        except json.JSONDecodeError:
            result = "Invalid updates format. Please provide valid JSON."
            write_tool_log("modify_order", key, {"error": result})
            return result

        order.update(updates_dict)
        result = {"order_id": key, "updated_fields": updates_dict}
        write_tool_log("modify_order", key, result)
        return result

    @function_tool
    async def reschedule_delivery(
        self,
        context: RunContext,
        order_id: str,
        email: str,
        new_delivery_date: str,
    ):
        """Sensitive tool: Reschedule delivery after email verification."""
        logger.info("reschedule_delivery called for %s", order_id)
        key = normalize_order_id(order_id)
        
        # Fetch order from MongoDB (read-only)
        mongo_logger = get_mongo_logger()
        order = mongo_logger.get_order(key) if mongo_logger and mongo_logger.enabled else ORDERS.get(key)

        if not order:
            result = f"No order found with ID {key}."
            write_tool_log("reschedule_delivery", key, {"error": result})
            return result

        if order.get("email") != email:
            result = "Email verification failed. Delivery reschedule denied."
            write_tool_log("reschedule_delivery", key, {"error": result})
            return result

        order["delivery_date"] = new_delivery_date
        result = {"order_id": key, "delivery_date": new_delivery_date}
        write_tool_log("reschedule_delivery", key, result)
        return result

    @function_tool
    async def initiate_refund(
        self,
        context: RunContext,
        order_id: str,
        email: str,
    ):
        """Sensitive tool: Initiate refund after email verification."""
        logger.info("initiate_refund called for %s", order_id)
        key = normalize_order_id(order_id)
        
        # Fetch order from MongoDB (read-only)
        mongo_logger = get_mongo_logger()
        order = mongo_logger.get_order(key) if mongo_logger and mongo_logger.enabled else ORDERS.get(key)

        if not order:
            result = f"No order found with ID {key}."
            write_tool_log("initiate_refund", key, {"error": result})
            return result

        if order.get("email") != email:
            result = "Email verification failed. Refund initiation denied."
            write_tool_log("initiate_refund", key, {"error": result})
            return result

        refund = {
            "status": "Initiated",
            "amount": order.get("payment", {}).get("amount", 0.0),
        }
        order["refund"] = refund
        result = {"order_id": key, "refund": refund}
        write_tool_log("initiate_refund", key, result)
        return result

    @function_tool
    async def change_payment_method(
        self,
        context: RunContext,
        order_id: str,
        email: str,
        new_payment_method: str,
    ):
        """Sensitive tool: Change payment method after email verification."""
        logger.info("change_payment_method called for %s", order_id)
        key = normalize_order_id(order_id)
        
        # Fetch order from MongoDB (read-only)
        mongo_logger = get_mongo_logger()
        order = mongo_logger.get_order(key) if mongo_logger and mongo_logger.enabled else ORDERS.get(key)

        if not order:
            result = f"No order found with ID {key}."
            write_tool_log("change_payment_method", key, {"error": result})
            return result

        if order.get("email") != email:
            result = "Email verification failed. Payment method change denied."
            write_tool_log("change_payment_method", key, {"error": result})
            return result

        order["payment"]["method"] = new_payment_method
        result = {
            "order_id": key,
            "payment_method": new_payment_method,
        }
        write_tool_log("change_payment_method", key, result)
        return result

    @function_tool
    async def end_call(self, context: RunContext):
        """End the call after the conversation is complete. Call this when the customer is satisfied and the conversation is finished."""
        try:
            write_tool_log("end_call", "N/A", {"action": "call_ended"})

            if getattr(self, "_session", None):
                await self._session.say(text="धन्यवाद। आपका दिन शुभ हो।", allow_interruptions=False)
                await asyncio.sleep(2)

            if getattr(self, "room", None) and getattr(self, "api", None):
                await self.api.room.delete_room(api.DeleteRoomRequest(room=self.room.name))

            return "Call ended"
        except Exception as e:
            logger.error(f"❌ End error: {e}")
            return f"Error: {e}"
           


# Create the server (NO parameters)
server = AgentServer()


def prewarm(proc: JobProcess):
    """Prewarm function to load VAD model"""
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm

# Configure inbound SIP trunk to accept incoming calls
server.sip_inbound_trunks = [LIVEKIT_INBOUND_TRUNK_ID] if LIVEKIT_INBOUND_TRUNK_ID else []


# IMPORTANT: Add agent_name parameter here in the decorator
@server.rtc_session(agent_name="high-time-store-support")
async def my_agent(ctx: JobContext):
    """Main agent session handler"""
    # Logging setup
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }
    
    # Track call start time for duration calculation
    call_start_time = datetime.utcnow()
    room_name = ctx.room.name
    participant_identity = None
    participant_phone = None

    # Set up a voice AI pipeline using OpenAI, Cartesia, AssemblyAI, and the LiveKit turn detector
    session = AgentSession(
        stt=inference.STT(model="assemblyai/universal-streaming", language="en"),
        llm=inference.LLM(model="openai/gpt-4.1-mini"),
        tts=inference.TTS(
            model="cartesia/sonic-3", voice="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    # Start the session, which initializes the voice pipeline and warms up the models
    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: noise_cancellation.BVCTelephony()
                if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                else noise_cancellation.BVC(),
            ),
        ),
    )

    # Join the room and connect to the user
    await ctx.connect()
    
    # Wait for participants and get their info
    try:
        # Get first remote participant
        if ctx.room.remote_participants:
            first_participant = list(ctx.room.remote_participants.values())[0]
            participant_identity = first_participant.identity
            # Extract phone number from identity (format: caller-919829007613)
            if participant_identity and participant_identity.startswith("caller-"):
                participant_phone = "+" + participant_identity.replace("caller-", "")
    except Exception as e:
        logger.error(f"Error getting participant info: {e}")
    
    # Log call session start to MongoDB
    mongo_logger = get_mongo_logger()
    if mongo_logger and mongo_logger.enabled:
        mongo_logger.log_conversation_event(
            room_name=room_name,
            event_type="call_started",
            event_data={
                "participant_identity": participant_identity,
                "participant_phone": participant_phone,
                "timestamp": call_start_time.isoformat(),
            }
        )
    
    # Send an initial greeting message
    await session.say("Hello! Welcome to High Time Store customer support. How can I help you today?")
    
    # Log greeting event
    if mongo_logger and mongo_logger.enabled:
        mongo_logger.log_conversation_event(
            room_name=room_name,
            event_type="greeting_sent",
            event_data={"message": "Hello! Welcome to High Time Store customer support. How can I help you today?"}
        )
    
    # Wait for session to complete
    try:
        await session.wait()
    except Exception as e:
        logger.error(f"Session error: {e}")
    finally:
        # Calculate call duration
        call_end_time = datetime.utcnow()
        call_duration = (call_end_time - call_start_time).total_seconds()
        
        # Log call session completion to MongoDB
        if mongo_logger and mongo_logger.enabled:
            mongo_logger.log_call_session(
                room_name=room_name,
                participant_identity=participant_identity or "unknown",
                participant_phone=participant_phone or "unknown",
                call_status="completed",
                call_duration=call_duration,
                disconnect_reason="normal",
                metadata={
                    "call_start": call_start_time.isoformat(),
                    "call_end": call_end_time.isoformat(),
                }
            )


if __name__ == "__main__":
    cli.run_app(server)