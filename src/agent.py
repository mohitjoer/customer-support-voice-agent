import logging
import os
import json
import re
from datetime import datetime

from dotenv import load_dotenv
from livekit import rtc
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


def write_tool_log(tool_name: str, order_id: str, result: dict) -> None:
    """Append a JSON line summarizing a tool call to the tool log file."""
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "tool": tool_name,
        "order_id": order_id,
        "result": result,
    }
    try:
        with open(TOOL_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
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

As soon as the call connects, greet the user with a short and polite welcome on behalf of High Time Store.

The user interacts with you through real-time speech.
Your responses must be short, natural,smooth, and suitable for spoken conversation.
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
        order = ORDERS.get(key)
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
        order = ORDERS.get(key)
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
        order = ORDERS.get(key)
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
        order = ORDERS.get(key)
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
        order = ORDERS.get(key)
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
        order = ORDERS.get(key)

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
        order = ORDERS.get(key)

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
        order = ORDERS.get(key)

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
        order = ORDERS.get(key)

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
        order = ORDERS.get(key)

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

server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session()
async def my_agent(ctx: JobContext):
    # Logging setup
    # Add any other context you want in all log entries here
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

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


if __name__ == "__main__":
    cli.run_app(server)
