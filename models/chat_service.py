from datetime import datetime, timedelta
from models.user import User
from models.chat import Chat

class ChatService:
    def __init__(self, current_user_email):
        self.current_user_email = current_user_email

    def send_message(self, receiver_email: str, message_body: str) -> bool:
        """
        Save a new message from the current user to the receiver.
        Returns True on success.
        """
        sender = User.get_by_email(self.current_user_email)
        receiver = User.get_by_email(receiver_email)
        if not sender or not receiver or not message_body.strip():
            return False

        chat = Chat(sender, receiver, message_body)
        chat.save_to_db()
        return True

    def get_messages(self, other_email: str) -> list[dict]:
        """
        Retrieve the full conversation between the current user and another user.
        Returns a list of dicts with:
          - sender: 'You' or other username
          - message_body
          - timestamp (raw ISO)
        """
        raw = Chat.get_messages(self.current_user_email, other_email)
        result = []
        for m in raw:
            sender_label = 'You' if m['sender'].email == self.current_user_email else m['sender'].username
            result.append({
                'sender': sender_label,
                'message_body': m['message_body'],
                'timestamp': m['timestamp'].isoformat()
            })
        return result

    def get_recent_chats(self) -> list[dict]:
        """
        Get each distinct conversation partner, their last message, and a formatted timestamp.
        Returns a list of dicts:
          - username
          - email
          - last_message
          - last_message_time (raw ISO)
          - formatted_time (human-friendly)
        """
        raw = Chat.get_recent_chats(self.current_user_email)
        recent = []
        for c in raw:
            recent.append({
                'username': c['username'],
                'email':    c['email'],
                'last_message': c['last_message'],
                'last_message_time': c['last_message_time'].isoformat(),
                'formatted_time': self.format_time(c['last_message_time'])
            })
        return recent

    def search_users(self, query: str) -> list[dict]:
        """
        Search for users by username (case-insensitive), excluding the current user.
        Returns list of dicts: username, email.
        """
        found = User.search_by_username(query, exclude_email=self.current_user_email)
        return [{'username': u.username, 'email': u.email} for u in found]

    @staticmethod
    def format_time(ts: datetime) -> str:
        """
        Mirror your JS logic: 
         - if today → "HH:MM"
         - if yesterday → "Yesterday"
         - else → "YYYY-MM-DD"
        """
        if not ts:
            return ''
        now = datetime.utcnow()
        if ts.date() == now.date():
            return ts.strftime('%H:%M')
        if ts.date() == (now - timedelta(days=1)).date():
            return 'Yesterday'
        return ts.strftime('%Y-%m-%d')
