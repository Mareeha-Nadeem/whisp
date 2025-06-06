from datetime import datetime, timedelta
from flask import session, jsonify
from flask_socketio import emit, join_room
from models.user import User
from models.chat import Chat
from db.mongo_manager import get_db
from bson import ObjectId
import os
import uuid

class ChatService(Chat):
    def __init__(self, current_user_email: str, socketio=None):
        
        self.current_user_email = current_user_email
        self.socketio = socketio
        self.db = get_db()
    
    def search_users(self, query: str) -> list:
        found = User.search_by_username(query, exclude_email=self.current_user_email)
        return [{'username': u.username, 'email': u.email} for u in found]
    
    def send_message(self, receiver_email: str, message_body: str, attachment=None):
        sender = User.get_by_email(self.current_user_email)
        receiver = User.get_by_email(receiver_email)
        if not sender or not receiver:
            return False
        
        attachment_type = None
        attachment_path = None
        
        # Process attachment if present
        if attachment and hasattr(attachment, 'filename'):
            # Determine type based on file extension
            ext = os.path.splitext(attachment.filename)[1].lower()
            if ext in ['.jpg', '.jpeg', '.png', '.gif']:
                attachment_type = 'image'
            elif ext in ['.mp4', '.webm', '.ogg']:
                attachment_type = 'video'
            else:
                attachment_type = 'file'
                
            # Generate a unique filename and save the file
            unique_filename = f"{uuid.uuid4()}{ext}"
            upload_dir = f"static/uploads/{attachment_type}s"
            
            # Create directory if it doesn't exist
            os.makedirs(upload_dir, exist_ok=True)
            
            file_path = os.path.join(upload_dir, unique_filename)
            attachment.save(file_path)
            
            # Store relative path to be served to clients
            attachment_path = f"/uploads/{attachment_type}s/{unique_filename}"
        
        chat = Chat(sender, receiver, message_body, attachment_type, attachment_path)
        msg_id = chat.save_to_db()
        
        # emit to receiver if socketio provided
        if self.socketio:
            chat_data = {
                'email': sender.email,
                'username': sender.username,
                'last_message': message_body if not attachment_type else f"[{attachment_type}] {message_body}",
                'last_message_time': datetime.utcnow().isoformat(),
                'message_id': str(msg_id)
            }
            self.socketio.emit('new_chat_update', chat_data, room=receiver_email)
            
            # Emit a real-time message update
            self.socketio.emit('new_message', {
                'message_id': str(msg_id),
                'sender_id': sender.email,
                'sender_name': sender.username,
                'message_body': message_body,
                'attachment_type': attachment_type,
                'attachment_path': attachment_path,
                'timestamp': datetime.utcnow().isoformat(),
                'is_delivered': True,
                'is_seen': False
            }, room=receiver_email)
        return msg_id
    
    def get_messages(self, other_email: str) -> list:
        raw = Chat.get_messages(self.current_user_email, other_email)
        result = []
        for m in raw:
            # Make sure to convert ObjectId to string
            msg_data = {
                '_id': str(m['_id']),
                'sender_id': m['sender_id'],
                'receiver_id': m['receiver_id'],
                'message_body': m['message_body'],
                'timestamp': m['timestamp'].isoformat() if isinstance(m['timestamp'], datetime) else m['timestamp'],
                'is_delivered': m.get('is_delivered', True),
                'is_seen': m.get('is_read', False),
                'reactions': m.get('reactions', [])
            }
            
            # Add attachment info if present
            if 'attachment_type' in m and 'attachment_path' in m:
                msg_data['attachment_type'] = m['attachment_type']
                msg_data['attachment_path'] = m['attachment_path']
                
            result.append(msg_data)
        return result
    
    def get_recent_chats(self) -> list:
        cursor = self.db.chats.find({
            '$or': [
                {'sender_id': self.current_user_email},
                {'receiver_id': self.current_user_email}
            ]
        }).sort('timestamp', -1)
        
        seen = set()
        recent = []
        for doc in cursor:
            other = doc['receiver_id'] if doc['sender_id'] == self.current_user_email else doc['sender_id']
            if other in seen:
                continue
            seen.add(other)
            
            user = User.get_by_email(other)
            last_message = doc['message_body']
            
            # Add attachment info to preview if present
            if 'attachment_type' in doc:
                last_message = f"[{doc['attachment_type']}] {last_message}"
                
            recent.append({
                'email': other,
                'username': user.username if user else other,
                'last_message': last_message,
                'last_message_time': doc['timestamp'].isoformat() if isinstance(doc['timestamp'], datetime) else doc['timestamp']
            })
        return recent
    
    def handle_connect(self):
        user = session.get('user_id')
        if user:
            join_room(user)
    
    def handle_load_recent_chats(self):
        if 'user_id' not in session:
            emit('error', {'msg': 'Not logged in'})
            return
        chats = self.get_recent_chats()
        emit('recent_chats', {'chats': chats})