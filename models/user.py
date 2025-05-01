from werkzeug.security import generate_password_hash, check_password_hash
from db.mongo_manager import get_db

class User:
    def __init__(self, username, password):
        self.username = username
        self.password = password

    def save_to_db(self):
        db = get_db()
        users_collection = db['users']
        hashed_password = generate_password_hash(self.password)
        users_collection.insert_one({
            "username": self.username,
            "password": hashed_password
        })

    @staticmethod
    def find_by_username(username):
        db = get_db()
        users_collection = db['users']
        user_data = users_collection.find_one({"username": username})
        return user_data

    @staticmethod
    def verify_password(stored_password, provided_password):
        return check_password_hash(stored_password, provided_password)
