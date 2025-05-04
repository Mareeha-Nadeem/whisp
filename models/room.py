from datetime import datetime
from db.mongo_manager import get_db
from models.user import User
from models.chat import Chat

class GroupChat(Chat):
    def __init__(self, sender, group_id, message_body, group_name=None):
        """
        Initialize the group chat object.
        sender should be a User object.
        group_id is the unique identifier for the group.
        """
        self.sender = sender  # User object for the sender
        self.group_id = group_id  # Group ID
        self.message_body = message_body  # The actual message
        self.timestamp = datetime.utcnow()  # Store the message timestamp
        self.group_name = group_name  # Optional group name parameter

    def save_to_db(self):
        """
        Save the group message to the database.
        """
        db = get_db()
        chat_data = {
            "sender_id": self.sender.email,
            "group_id": self.group_id,
            "message_body": self.message_body,
            "timestamp": self.timestamp,
            "is_group_message": True
        }
        db.group_chats.insert_one(chat_data)
        return "Group message sent successfully!"

    @staticmethod
    def create_group(creator_email, group_name, member_emails=[]):
        """
        Create a new group chat
        """
        db = get_db()
        
        # Add the creator to the members list if not already included
        if creator_email not in member_emails:
            member_emails.append(creator_email)
            
        group_data = {
            "name": group_name,
            "creator_id": creator_email,
            "members": member_emails,
            "created_at": datetime.utcnow()
        }
        
        result = db.groups.insert_one(group_data)
        return str(result.inserted_id)  # Return the group ID

    @staticmethod
    def get_user_groups(user_email):
        """
        Get all groups that a user is a member of
        """
        db = get_db()
        groups = db.groups.find({
            "members": user_email
        })
        
        user_groups = []
        for group in groups:
            # Get the last message for this group
            last_message = db.group_chats.find({
                "group_id": str(group["_id"])
            }).sort("timestamp", -1).limit(1)
            
            last_message_text = ""
            last_message_time = None
            last_message_sender = ""
            
            # Check if we have at least one message
            last_message_list = list(last_message)
            if last_message_list:
                last_message_obj = last_message_list[0]
                last_message_text = last_message_obj["message_body"]
                last_message_time = last_message_obj["timestamp"]
                
                # Get sender's username
                sender = User.get_by_email(last_message_obj["sender_id"])
                if sender:
                    last_message_sender = sender.username
            
            group_info = {
                "id": str(group["_id"]),
                "name": group["name"],
                "member_count": len(group["members"]),
                "last_message": last_message_text,
                "last_message_time": last_message_time,
                "last_message_sender": last_message_sender
            }
            
            user_groups.append(group_info)
            
        return user_groups

    @staticmethod
    def get_group_messages(group_id):
        """
        Get all messages for a specific group
        """
        db = get_db()
        messages = db.group_chats.find({
            "group_id": group_id
        }).sort("timestamp", 1)
        
        message_list = []
        for message in messages:
            sender = User.get_by_email(message["sender_id"])
            
            message_data = {
                "sender_id": message["sender_id"],
                "sender_name": sender.username if sender else "Unknown User",
                "message_body": message["message_body"],
                "timestamp": message["timestamp"]
            }
            
            message_list.append(message_data)
            
        return message_list

    @staticmethod
    def get_group_info(group_id):
        """
        Get information about a specific group
        """
        db = get_db()
        group = db.groups.find_one({"_id": db.ObjectId(group_id)})
        
        if not group:
            return None
            
        # Get all members with their usernames
        members = []
        for member_email in group["members"]:
            user = User.get_by_email(member_email)
            if user:
                members.append({
                    "email": member_email,
                    "username": user.username
                })
                
        group_info = {
            "id": str(group["_id"]),
            "name": group["name"],
            "creator_id": group["creator_id"],
            "members": members,
            "created_at": group["created_at"]
        }
        
        return group_info

    @staticmethod
    def add_member(group_id, member_email):
        """
        Add a member to a group
        """
        db = get_db()
        db.groups.update_one(
            {"_id": db.ObjectId(group_id)},
            {"$addToSet": {"members": member_email}}
        )
        return True

    @staticmethod
    def remove_member(group_id, member_email):
        """
        Remove a member from a group
        """
        db = get_db()
        db.groups.update_one(
            {"_id": db.ObjectId(group_id)},
            {"$pull": {"members": member_email}}
        )
        return True