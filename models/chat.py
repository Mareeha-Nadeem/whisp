from datetime import datetime
from bson import ObjectId            
from db.mongo_manager import get_db
from models.user import User
from flask import session
from flask import app
import os
import uuid

class Chat:
    def __init__(self, sender, receiver, message_body, attachment_type=None, attachment_path=None):
        self.sender = sender
        self.receiver = receiver 
        self.message_body = message_body
        self.timestamp = datetime.utcnow()
        self.attachment_type = attachment_type  # 'image', 'video', 'file'
        self.attachment_path = attachment_path
        self.db = get_db()
    
    def save_to_db(self):
        chat_doc = {
            'sender_id': self.sender.email,
            'receiver_id': self.receiver.email,
            'message_body': self.message_body,
            'timestamp': self.timestamp,
            'is_delivered': False,
            'is_read': False
        }
        
        # Add attachment info if present
        if self.attachment_type and self.attachment_path:
            chat_doc['attachment_type'] = self.attachment_type
            chat_doc['attachment_path'] = self.attachment_path
        
        result = self.db.chats.insert_one(chat_doc)
        return result.inserted_id
    
    @staticmethod
    def delete_message(message_id, user_email):
        db = get_db()
        try:
            message_id = ObjectId(message_id)
            # For simplicity, we're just marking it as deleted for the current user
            # In a real app, you might want to have a more sophisticated approach
            result = db.chats.update_one(
                {'_id': message_id, '$or': [{'sender_id': user_email}, {'receiver_id': user_email}]},
                {'$set': {f'deleted_for_{user_email.replace("@", "_at_")}': True}}
            )
            return result.modified_count > 0
        except Exception as e:
            print(f"Error deleting message: {e}")
            return False
    
    @staticmethod 
    def edit_message(message_id: str, user_email: str, new_body: str) -> bool:
        db = get_db()
        try:
            result = db.chats.update_one(
                {"_id": ObjectId(message_id), "sender_id": user_email},
                {"$set": {"message_body": new_body, "edited_at": datetime.utcnow()}}
            )
            return result.modified_count == 1
        except Exception as e:
            print(f"Error editing message: {e}")
            return False
    
    @staticmethod
    def get_other_party(message_id):
        """Get the other participant in a chat based on the message ID"""
        db = get_db()
        try:
            message = db.chats.find_one({'_id': ObjectId(message_id)})
            if not message:
                return None
                
            # If the user requesting is the sender, return the receiver, and vice versa
            user_email = session.get('user_id', '')
            if message['sender_id'] == user_email:
                return message['receiver_id']
            elif message['receiver_id'] == user_email:
                return message['sender_id']
            return None
        except Exception as e:
            print(f"Error getting other party: {e}")
            return None

    @staticmethod
    def get_messages(user1_email, user2_email):
        db = get_db()
        delete_field1 = f'deleted_for_{user1_email.replace("@", "_at_")}'
        
        messages = db.chats.find({
            '$or': [
                {'sender_id': user1_email, 'receiver_id': user2_email},
                {'sender_id': user2_email, 'receiver_id': user1_email}
            ],
            # Add this condition to filter out deleted messages
            delete_field1: {'$ne': True}
        }).sort('timestamp', 1)  
        
        # Mark messages as delivered when retrieved by recipient
        db.chats.update_many(
            {'sender_id': user2_email, 'receiver_id': user1_email, 'is_delivered': False},
            {'$set': {'is_delivered': True}}
        )
        
        return list(messages)

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
    
    @staticmethod
    def add_reaction(message_id, emoji, user_email):
        db = get_db()
        try:
            message_id = ObjectId(message_id)
            db.chats.update_one(
                {'_id': message_id},
                {'$pull': {'reactions': {'by': user_email}}}  # Remove existing reaction from this user
            )
            db.chats.update_one(
                {'_id': message_id},
                {'$push': {'reactions': {'emoji': emoji, 'by': user_email}}}
            )
            return True
        except Exception as e:
            print(f"Error adding reaction: {e}")
            return False
    
    @staticmethod
    def delete_for_everyone(message_id, user_email):
        db = get_db()
        try:
            oid = ObjectId(message_id)
            # First, ensure the user is actually the sender
            chat_doc = db.chats.find_one({'_id': oid, 'sender_id': user_email})
            if not chat_doc:
                return False, "Not authorized"

            # Get username directly from database
            user_doc = db.users.find_one({'email': user_email})
            sender_name = user_doc['username'] if user_doc else "User"
            
            placeholder = f"{sender_name} deleted a message"

            result = db.chats.update_one(
                {'_id': oid},
                {
                    '$set': {
                        'message_body': placeholder,
                        'deleted_for_everyone': True,
                        'edited_at': datetime.utcnow()
                    }
                }
            )
            
            # Print for debugging
            print(f"Delete for everyone: user_email={user_email}, name={sender_name}, success={result.modified_count}")
            
            return (result.modified_count == 1, placeholder)
        except Exception as e:
            print(f"Error deleting message for everyone: {e}")
            return False, str(e)
            
    @staticmethod
    def get_sender(message_id):
        """Get the sender email for a message"""
        db = get_db()
        try:
            message = db.chats.find_one({'_id': ObjectId(message_id)})
            if message:
                return message['sender_id']
            return None
        except Exception as e:
            print(f"Error getting sender: {e}")
            return None