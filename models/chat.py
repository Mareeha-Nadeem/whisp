from datetime import datetime
from bson import ObjectId            
from db.mongo_manager import get_db
from models.user import User

class Chat:
    def __init__(self, sender, receiver, message_body):
        """
        Initialize the chat object with sender, receiver, and content.
        sender and receiver should be User objects.
        """
        self.sender = sender
        self.receiver = receiver
        self.message_body = message_body
        self.timestamp = datetime.utcnow()

    def save_to_db(self):
        """
        Save the message to the database. Initialize read status to False.
        """
        db = get_db()
        chat_data = {
            "sender_id":    self.sender.email,
            "receiver_id":  self.receiver.email,
            "message_body": self.message_body,
            "timestamp":    self.timestamp,
            "is_read":      False,
            "read_at":      None
        }
        db.chats.insert_one(chat_data)
        return True

    @staticmethod
    def delete_message(message_id: str, user_email: str) -> bool:
        db = get_db()
        result = db.chats.delete_one({
            "_id": ObjectId(message_id),
            "sender_id": user_email
        })
        return result.deleted_count == 1

    @staticmethod
    def edit_message(message_id: str, user_email: str, new_body: str) -> bool:
        db = get_db()
        result = db.chats.update_one(
            {"_id": ObjectId(message_id), "sender_id": user_email},
            {"$set": {"message_body": new_body, "edited_at": datetime.utcnow()}}
        )
        return result.modified_count == 1

    @staticmethod
    def get_messages(sender_email, receiver_email):
        db = get_db()
        messages = db.chats.find({
            "$or": [
                {"sender_id": sender_email, "receiver_id": receiver_email},
                {"sender_id": receiver_email, "receiver_id": sender_email}
            ]
        }).sort("timestamp", 1)

        messages_with_user_objects = []
        for m in messages:
            sender = User.get_by_email(m["sender_id"])
            receiver = User.get_by_email(m["receiver_id"])
            messages_with_user_objects.append({
                "message_body": m["message_body"],
                "timestamp": m["timestamp"],
                "sender": sender,
                "receiver": receiver
            })
        return messages_with_user_objects

    @staticmethod
    def get_recent_chats(current_user_email: str) -> list[dict]:
        """
        Retrieve the most recent chat for each conversation partner.
        Returns a list of dicts with keys: email, username, last_message, last_message_time (datetime).
        """
        db = get_db()
        # Fetch all chats involving the user, sorted by newest first
        cursor = db.chats.find({
            "$or": [
                {"sender_id": current_user_email},
                {"receiver_id": current_user_email}
            ]
        }).sort("timestamp", -1)

        seen = set()
        recent = []
        for doc in cursor:
            # Identify the other participant
            if doc["sender_id"] == current_user_email:
                other_email = doc["receiver_id"]
            else:
                other_email = doc["sender_id"]

            # Skip if we've already added this partner
            if other_email in seen:
                continue
            seen.add(other_email)

            # Lookup user info
            user = User.get_by_email(other_email)
            username = user.username if user else other_email

            recent.append({
                "email": other_email,
                "username": username,
                "last_message": doc["message_body"],
                "last_message_time": doc["timestamp"]
            })
        return recent

    @staticmethod
    def mark_as_read(message_id: str, reader_email: str) -> bool:
        db = get_db()
        res = db.chats.update_one(
            {"_id": ObjectId(message_id), "receiver_id": reader_email},
            {"$set": {"is_read": True, "read_at": datetime.utcnow()}}
        )
        return res.modified_count == 1

    @staticmethod
    def get_message_info(message_id: str) -> dict:
        db = get_db()
        doc = db.chats.find_one({"_id": ObjectId(message_id)}, {"is_read":1, "read_at":1})
        return {"is_read": doc.get("is_read", False), "read_at": doc.get("read_at")}
