from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from db.mongo_manager import get_db

class User:
    def __init__(self, username, email, password=""):
        self.username = username
        self.email = email
        self.password = password
    
    def create(self):
        db = get_db()
        
        existing_user = db.users.find_one({"email": self.email})
        if existing_user:
            return False
        
        hashed_password = generate_password_hash(self.password)
        user_data = {
            "username": self.username,
            "email": self.email,
            "password": hashed_password,
            "created_at": datetime.utcnow(),
            "is_active": True
        }
        db.users.insert_one(user_data)
        return True
    
    @staticmethod
    def validate(email, password):
        db = get_db()
        user = db.users.find_one({"email": email})
        if user and check_password_hash(user['password'], password):
            return True
        return False
    
    @staticmethod
    def get_by_email(email):
        """
        Get a user by email and return a User object
        """
        db = get_db()
        user_data = db.users.find_one({"email": email})
        if user_data:
            return User(user_data["username"], user_data["email"])
        return None
    
    @staticmethod
    def search_by_username(query, exclude_email=None):
        """
        Search for users by username
        Optionally exclude a user by email (typically the current user)
        """
        db = get_db()
        search_filter = {
            "username": {"$regex": query, "$options": "i"}
        }
        if exclude_email:
            search_filter["email"] = {"$ne": exclude_email}
        
        found_users = db.users.find(search_filter)
        return [User(user["username"], user["email"]) for user in found_users]