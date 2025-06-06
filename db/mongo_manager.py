from pymongo import MongoClient

# MongoDB Atlas connection string
uri = "mongodb+srv://mareehanadeem:bloomitup@whisp.68hz4zz.mongodb.net/whisp_db?retryWrites=true&w=majority&appName=Whisp"

# Create a MongoClient instance using the URI
client = MongoClient(uri)

try:
    # Ping the server to check the connection
    client.admin.command('ping')
    print("MongoDB connected successfully!")
except Exception as e:
    print(f"Error: {e}")

# Accessing the database
db = client['whisp_db']

# Function to return the database connection
def get_db():
    return db