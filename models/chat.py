from datetime import datetime
from db.mongo_manager import get_db
from models.user import User  # Importing User class to use for sender/receiver

class Chat:
    def __init__(self, sender, receiver, message_body):
        """
        Initialize the chat object with sender, receiver, and message content.
        sender and receiver should be User objects.
        """
        self.sender = sender  # User object for the sender
        self.receiver = receiver  # User object for the receiver
        self.message_body = message_body  # The actual message
        self.timestamp = datetime.utcnow()  # Store the message timestamp

    def save_to_db(self):
        """
        Save the message to the database. Only store the user IDs (not the whole User object) for efficiency.
        """
        db = get_db()
        chat_data = {
            "sender_id": self.sender.email,  # Store sender's email or user_id
            "receiver_id": self.receiver.email,  # Store receiver's email or user_id
            "message_body": self.message_body,
            "timestamp": self.timestamp
        }
        db.chats.insert_one(chat_data)  # Insert the chat message into MongoDB
        return "Message sent successfully!"

    @staticmethod
    def get_messages(sender_email, receiver_email):
        """
        Retrieve all chat messages between sender and receiver from the database.
        """
        db = get_db()
        messages = db.chats.find({
            "$or": [
                {"sender_id": sender_email, "receiver_id": receiver_email},
                {"sender_id": receiver_email, "receiver_id": sender_email}
            ]
        }).sort("timestamp", 1)  # Sort by timestamp (ascending order)

        # Convert each message to include sender and receiver as User objects
        messages_with_user_objects = []
        for message in messages:
            sender = User.get_by_email(message["sender_id"])  # Get actual User object
            receiver = User.get_by_email(message["receiver_id"])  # Get actual User object

            message_data = {
                "message_body": message["message_body"],
                "timestamp": message["timestamp"],
                "sender": sender,
                "receiver": receiver
            }
            messages_with_user_objects.append(message_data)

        return messages_with_user_objects
    
    @staticmethod
    def get_recent_chats(user_email):
        """
        Get a list of recent chats for a specific user.
        Returns a list of users with their latest message.
        """
        db = get_db()
        
        # Find all chats where the user is either sender or receiver
        all_chats = db.chats.find({
            "$or": [
                {"sender_id": user_email},
                {"receiver_id": user_email}
            ]
        }).sort("timestamp", -1)  # Sort by timestamp (descending order)
        
        # Track unique conversations by other user's email
        recent_chats = {}
        
        for chat in all_chats:
            # Determine the other person in the conversation
            other_email = chat["receiver_id"] if chat["sender_id"] == user_email else chat["sender_id"]
            
            # Only add to recent_chats if we haven't seen this user yet
            if other_email not in recent_chats:
                other_user = User.get_by_email(other_email)
                if other_user:
                    recent_chats[other_email] = {
                        "username": other_user.username,
                        "email": other_email,
                        "last_message": chat["message_body"],
                        "last_message_time": chat["timestamp"]
                    }
        
        # Convert dictionary to list for return
        return list(recent_chats.values())