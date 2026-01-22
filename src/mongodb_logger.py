"""
MongoDB integration for logging call data and tool usage.
"""
import os
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from dotenv import load_dotenv

try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False

load_dotenv(".env.local")

logger = logging.getLogger("mongodb_logger")

# MongoDB Configuration
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "customer_support_db")


class MongoDBLogger:
    """Handles logging of call data and tool usage to MongoDB."""
    
    def __init__(self):
        self.client = None
        self.db = None
        self.enabled = False
        
        if not PYMONGO_AVAILABLE:
            logger.warning("pymongo not installed. MongoDB logging disabled.")
            return
        
        if not MONGODB_URI:
            logger.warning("MONGODB_URI not set. MongoDB logging disabled.")
            return
        
        try:
            self.client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
            # Test connection
            self.client.admin.command('ping')
            self.db = self.client[MONGODB_DB_NAME]
            self.enabled = True
            logger.info(f"MongoDB connected successfully to database: {MONGODB_DB_NAME}")
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            self.enabled = False
        except Exception as e:
            logger.error(f"MongoDB initialization error: {e}")
            self.enabled = False
    
    def upload_orders(self, orders: Dict[str, Any]) -> bool:
        """Upload/update orders to MongoDB. Creates or updates the orders collection."""
        if not self.enabled:
            return False
        
        try:
            orders_collection = self.db.orders
            
            # Clear existing orders and insert new ones
            orders_collection.delete_many({})
            
            # Convert dict to list of documents
            order_documents = list(orders.values())
            
            if order_documents:
                orders_collection.insert_many(order_documents)
                logger.info(f"Uploaded {len(order_documents)} orders to MongoDB")
            
            # Create index on order_id for faster lookups
            orders_collection.create_index("order_id", unique=True)
            
            return True
        except Exception as e:
            logger.error(f"Failed to upload orders to MongoDB: {e}")
            return False
    
    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single order from MongoDB by order_id (read-only)."""
        if not self.enabled:
            return None
        
        try:
            order = self.db.orders.find_one({"order_id": order_id})
            if order:
                # Remove MongoDB's _id field
                order.pop('_id', None)
            return order
        except Exception as e:
            logger.error(f"Failed to fetch order {order_id} from MongoDB: {e}")
            return None
            self.enabled = False
        except Exception as e:
            logger.error(f"MongoDB initialization error: {e}")
            self.enabled = False
    
    def log_tool_call(
        self,
        tool_name: str,
        order_id: str,
        result: Dict[str, Any],
        room_name: Optional[str] = None,
        participant_identity: Optional[str] = None,
    ) -> bool:
        """Log a tool call to MongoDB."""
        if not self.enabled:
            return False
        
        try:
            document = {
                "timestamp": datetime.utcnow(),
                "tool_name": tool_name,
                "order_id": order_id,
                "result": result,
                "room_name": room_name,
                "participant_identity": participant_identity,
            }
            
            self.db.tool_calls.insert_one(document)
            logger.debug(f"Logged tool call: {tool_name} for order {order_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to log tool call to MongoDB: {e}")
            return False
    
    def log_call_session(
        self,
        room_name: str,
        participant_identity: str,
        participant_phone: str,
        call_status: str,
        call_duration: Optional[float] = None,
        disconnect_reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Log a complete call session to MongoDB."""
        if not self.enabled:
            return False
        
        try:
            document = {
                "timestamp": datetime.utcnow(),
                "room_name": room_name,
                "participant_identity": participant_identity,
                "participant_phone": participant_phone,
                "call_status": call_status,
                "call_duration": call_duration,
                "disconnect_reason": disconnect_reason,
                "metadata": metadata or {},
            }
            
            self.db.call_sessions.insert_one(document)
            logger.info(f"Logged call session: {room_name} for {participant_phone}")
            return True
        except Exception as e:
            logger.error(f"Failed to log call session to MongoDB: {e}")
            return False
    
    def log_conversation_event(
        self,
        room_name: str,
        event_type: str,
        event_data: Dict[str, Any],
    ) -> bool:
        """Log a conversation event (greeting, goodbye, error, etc.) to MongoDB."""
        if not self.enabled:
            return False
        
        try:
            document = {
                "timestamp": datetime.utcnow(),
                "room_name": room_name,
                "event_type": event_type,
                "event_data": event_data,
            }
            
            self.db.conversation_events.insert_one(document)
            logger.debug(f"Logged conversation event: {event_type} in {room_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to log conversation event to MongoDB: {e}")
            return False
    
    def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")


# Global MongoDB logger instance
_mongo_logger = None


def get_mongo_logger() -> MongoDBLogger:
    """Get or create the global MongoDB logger instance."""
    global _mongo_logger
    if _mongo_logger is None:
        _mongo_logger = MongoDBLogger()
    return _mongo_logger


def log_to_mongodb(
    tool_name: str,
    order_id: str,
    result: Dict[str, Any],
    room_name: Optional[str] = None,
    participant_identity: Optional[str] = None,
) -> bool:
    """Convenience function to log tool calls to MongoDB."""
    mongo_logger = get_mongo_logger()
    return mongo_logger.log_tool_call(
        tool_name=tool_name,
        order_id=order_id,
        result=result,
        room_name=room_name,
        participant_identity=participant_identity,
    )
