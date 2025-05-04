from flask import Flask, render_template, request, redirect, flash, session, url_for, jsonify
from flask_socketio import SocketIO, send, emit, join_room, leave_room

from models.user import User
from models.chat import Chat
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'yeh-secret-key-tu-change-karna-prod-mein'
socketio = SocketIO(app)

@app.route("/")
def home():
    if 'user_id' in session:  # ya jo bhi key tum login pe store karti ho
        return redirect(url_for('dashboard'))  # dashboard route ka naam
    return render_template('landing.html')

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        
        if User.validate(email, password):
            session["user_id"] = email
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password", "danger")
            return redirect(url_for("login"))
    
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    current_user = User.get_by_email(session["user_id"])
    if not current_user:
        session.clear()
        return redirect(url_for("login"))
    
    return render_template("dashboard.html", current_user_name=current_user.username)

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully", "info")
    return redirect(url_for("login"))

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")
    
    username = request.form["username"]
    email = request.form["email"]
    password = request.form["password"]
    
    user = User(username, email, password)
    
    if not user.create():
        flash("Email already exists! Try logging in", "error")
        return redirect("/signup")
    
    flash("Account created successfully!", "success")
    return redirect("/login")

@app.route("/search_users")
def search_users():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    query = request.args.get("query", "")
    if not query:
        return jsonify({"users": []})
    
    users = User.search_by_username(query, exclude_email=session["user_id"])
    
    user_list = []
    for user in users:
        user_list.append({
            "username": user.username,
            "email": user.email
        })
    
    return jsonify({"users": user_list})

@app.route("/get_recent_chats")
def get_recent_chats():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    user_email = session["user_id"]
    recent_chats = Chat.get_recent_chats(user_email)

    if not recent_chats:
        print("No recent chats found.")

    chat_list = []
    for chat in recent_chats:
        chat_list.append({
            "username": chat["username"],
            "email": chat["email"],
            "last_message": chat["last_message"],
            "last_message_time": chat["last_message_time"].isoformat() if chat["last_message_time"] else None
        })

    return jsonify({"chats": chat_list})


@app.route("/get_messages/<receiver_email>")
def get_messages(receiver_email):
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    sender_email = session["user_id"]
    messages = Chat.get_messages(sender_email, receiver_email)
    
    formatted_messages = []
    for message in messages:
        formatted_messages.append({
            "sender_id": message["sender"].email,
            "receiver_id": message["receiver"].email,
            "message_body": message["message_body"],
            "timestamp": message["timestamp"].isoformat()
        })
    
    return jsonify({"messages": formatted_messages})

@app.route("/send_message", methods=["POST"])
def send_message():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    sender_email = session["user_id"]
    receiver_email = request.form["receiver_id"]
    message_body = request.form["message_body"]
    
    sender = User.get_by_email(sender_email)
    receiver = User.get_by_email(receiver_email)
    
    if not sender or not receiver:
        return jsonify({"success": False, "error": "Invalid sender or receiver"}), 400
    
    chat = Chat(sender, receiver, message_body)
    chat.save_to_db()
    
    # Emit the message to the receiver in real-time
    socketio.emit('new_message', {'message': message_body, 'sender': sender.username, 'receiver': receiver.username}, room=receiver_email)
    
    return jsonify({"success": True, "message": "Message sent successfully"})

@socketio.on('connect')
def handle_connect():
    email = session.get("user_id")
    if email:
        # Join the user to their personal room (using email)
        join_room(email)
        print(f"{email} connected.")

@socketio.on('disconnect')
def handle_disconnect():
    email = session.get("user_id")
    if email:
        leave_room(email)
        print(f"{email} disconnected.")

if __name__ == '__main__':
    socketio.run(app, debug=True)
