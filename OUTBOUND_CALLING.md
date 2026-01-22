# Outbound Calling Guide

This guide explains how to make outbound calls using your LiveKit voice agent with Twilio SIP trunk integration.

## Prerequisites

1. **LiveKit Account** with SIP trunk configured
2. **Twilio Account** with phone numbers and SIP trunk
3. **Environment Variables** configured in `.env.local`:
   ```env
   LIVEKIT_URL=wss://your-instance.livekit.cloud
   LIVEKIT_API_KEY=your_api_key
   LIVEKIT_API_SECRET=your_api_secret
   LIVEKIT_TUNK_ID=your_twilio_trunk_id
   ```

## Setup

1. Make sure your LiveKit agent is running:
   ```bash
   python src/agent.py dev
   ```

2. Verify your Twilio SIP trunk is properly connected to LiveKit

## Making Outbound Calls

### Method 1: Using the CLI Tool (Recommended)

The easiest way to make an outbound call:

```bash
python make_call.py +1234567890
```

Replace `+1234567890` with the actual phone number you want to call.

**Important:** Phone numbers MUST be in E.164 format (starting with `+` followed by country code and number).

#### Examples:
```bash
# US number
python make_call.py +14155551234

# UK number
python make_call.py +442071234567

# India number
python make_call.py +919876543210
```

### Method 2: Using the Python Module

You can also use the outbound caller programmatically:

```python
from src.outbound_caller import create_outbound_call
import asyncio

async def make_call():
    result = await create_outbound_call(
        phone_number="+1234567890",
        room_name="my-call-room",  # Optional
        identity="caller-123",      # Optional
        metadata="customer_id=456"  # Optional
    )
    print(f"Call initiated: {result}")

asyncio.run(make_call())
```

### Method 3: Direct Script Execution

```bash
python src/outbound_caller.py +1234567890
```

## How It Works

1. **Call Initiation**: When you run the make_call script, it:
   - Creates a new LiveKit room
   - Initiates a SIP call through your Twilio trunk
   - Connects the call to the room

2. **Agent Connection**: Your running LiveKit agent automatically:
   - Detects the new room/call
   - Joins the room
   - Greets the caller
   - Handles the conversation using AI

3. **Call Flow**:
   ```
   You → CLI Tool → LiveKit API → Twilio SIP → Phone Call
                                              ↓
                                         Your Agent (AI)
   ```

## Response Structure

When a call is successfully created, you'll receive:

```json
{
  "success": true,
  "room_name": "outbound-1234567890",
  "room_sid": "RM_xxxxx",
  "phone_number": "+1234567890",
  "participant_id": "PA_xxxxx",
  "participant_identity": "caller-1234567890",
  "sip_call_id": "xxxxx"
}
```

## Troubleshooting

### Error: Missing environment variables
- Check that all required variables are set in `.env.local`
- Restart your agent after updating environment variables

### Error: Invalid phone number format
- Ensure the phone number starts with `+`
- Include the country code
- Remove spaces, dashes, or parentheses

### Error: SIP trunk not found
- Verify `LIVEKIT_TUNK_ID` matches your configured trunk ID in LiveKit console
- Check that the trunk is active and properly configured

### Call connects but agent doesn't respond
- Ensure your agent is running (`python src/agent.py dev`)
- Check agent logs for errors
- Verify your OpenAI API key is valid

### Call fails immediately
- Check your Twilio account has sufficient credits
- Verify the phone number is valid and can receive calls
- Review Twilio SIP trunk configuration in LiveKit console

## Advanced Usage

### Custom Room Names

```python
result = await create_outbound_call(
    phone_number="+1234567890",
    room_name="customer-support-call-12345"
)
```

### Adding Metadata

Pass customer information or context:

```python
result = await create_outbound_call(
    phone_number="+1234567890",
    metadata='{"customer_id": "12345", "order_id": "HT1004"}'
)
```

This metadata will be available to your agent through the participant metadata.

### Batch Calling

To make multiple calls:

```python
import asyncio
from src.outbound_caller import create_outbound_call

async def call_multiple(phone_numbers):
    tasks = [create_outbound_call(num) for num in phone_numbers]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results

# Usage
numbers = ["+1234567890", "+1234567891", "+1234567892"]
results = asyncio.run(call_multiple(numbers))
```

## Monitoring Calls

1. **LiveKit Dashboard**: View active rooms and participants
2. **Agent Logs**: Check `logs/tool_calls.log` for agent interactions
3. **Twilio Console**: Monitor SIP trunk usage and call logs

## Cost Considerations

- Each outbound call consumes LiveKit minutes
- Twilio charges per minute for SIP/PSTN calls
- Consider implementing call duration limits in your agent

## Security Best Practices

1. **Never commit** `.env.local` to version control
2. **Rotate** API keys regularly
3. **Restrict** API key permissions to necessary scopes only
4. **Monitor** unusual calling patterns
5. **Implement** rate limiting for production use

## Next Steps

- Add call recording functionality
- Implement call queuing system
- Add webhook notifications for call events
- Build a web dashboard for call management
- Add call analytics and reporting
