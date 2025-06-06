from flask import Flask, render_template, request, redirect, flash, session, url_for, jsonify
from flask_socketio import SocketIO, leave_room
from models.chat_service import ChatService
from models.user import User
from models.chat import Chat
from datetime import datetime
import json
from bson import ObjectId
from db.mongo_manager import get_db
# Custom JSON encoder to handle ObjectId
class MongoJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super(MongoJSONEncoder, self).default(obj)

app = Flask(__name__)
app.secret_key = 'change-this-in-prod'
app.json_encoder = MongoJSONEncoder  # Use custom JSON encoder

socketio = SocketIO(app, cors_allowed_origins="*")

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('landing.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if User.validate(email, password):
            session['user_id'] = email
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        user = User(request.form['username'], request.form['email'], request.form['password'])
        if not user.create():
            flash('Email already exists', 'error')
            return redirect(url_for('signup'))
        flash('Account created successfully', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    u = User.get_by_email(session['user_id'])
    if not u:
        session.clear()
        return redirect(url_for('login'))
    return render_template('dashboard.html', current_user_name=u.username)

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('login'))

@app.route('/search_users')
def search_users():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    q = request.args.get('query', '')
    if not q:
        return jsonify({'users': []})
    service = ChatService(session['user_id'])
    return jsonify({'users': service.search_users(q)})

@app.route('/get_recent_chats')
def get_recent_chats():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    service = ChatService(session['user_id'])
    return jsonify({'chats': service.get_recent_chats()})

@app.route('/get_messages/<other_email>')
def get_messages(other_email):
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    current = session['user_id']
    db = get_db()

    # build the field name you set in delete_message():
    delete_field = f'deleted_for_{current.replace("@", "_at_")}'

    raw_msgs = db.chats.find(
        {
            '$or': [
                {'sender_id':   current, 'receiver_id': other_email},
                {'sender_id': other_email, 'receiver_id':   current}
            ],
            # *this* line prevents deleted messages from ever being loaded
            delete_field: { '$ne': True }
        }
    ).sort('timestamp', 1)

    messages = []
    for m in raw_msgs:
        messages.append({
            '_id':          str(m['_id']),
            'sender_id':    m['sender_id'],
            'message_body': m['message_body'],
            'timestamp':    m['timestamp'].isoformat(),
            'is_delivered': m.get('is_delivered', False),
            'is_seen':      m.get('is_seen', False),
            'reactions':    m.get('reactions', [])
        })

    # mark anything delivered
    db.chats.update_many(
        {'sender_id': other_email, 'receiver_id': current, 'is_delivered': False},
        {'$set': {'is_delivered': True}}
    )

    return jsonify({'messages': messages})


    return jsonify({'messages': messages})
@socketio.on('connect')
def on_connect():
    if 'user_id' in session:
        ChatService(session['user_id'], socketio).handle_connect()

@socketio.on('load_recent_chats')
def on_load_recent_chats():
    ChatService(session.get('user_id', ''), socketio).handle_load_recent_chats()

@socketio.on('disconnect')
def on_disconnect():
    if 'user_id' in session:
        leave_room(session['user_id'])
# Add this route to your app.py file:

@app.route('/send_message', methods=['POST'])
def send_message():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    receiver_id = request.form['receiver_id']
    message_body = request.form['message_body']
    
    if not receiver_id or not message_body.strip():
        return jsonify({'success': False, 'error': 'Invalid request'}), 400
    
    service = ChatService(session['user_id'], socketio)
    msg_id = service.send_message(receiver_id, message_body)
    
    if msg_id:
        return jsonify({
            'success': True, 
            'message_id': str(msg_id)
        })
    else:
        return jsonify({'success': False, 'error': 'Failed to send message'}), 500

@app.route('/react', methods=['POST'])
def react():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    msg_id = request.form['message_id']
    emoji  = request.form['emoji']
    user   = session['user_id']

    try:
        oid = ObjectId(msg_id)
        db = get_db()
        # Add or update this user's reaction
        result = db.chats.update_one(
          {'_id': oid},
          {'$pull': {'reactions': {'by': user}}}  # remove any prior by same user
        )
        db.chats.update_one(
          {'_id': oid},
          {'$push': {'reactions': {'emoji': emoji, 'by': user}}}
        )
        # Broadcast via Socket.IO if you want real-time updates
        socketio.emit('message_reaction', {
          'message_id': msg_id,
          'emoji': emoji,
          'username': user
        }, room=msg_id)
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f"React error: {e}")
        return jsonify({'success': False, 'error': 'Server error'}), 500
# In app.py (paste-3.txt)
@app.route('/delete_everyone/<msg_id>', methods=['POST'])
def delete_everyone(msg_id):
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify(success=False, error="Not logged in"), 401
            
        print(f"Attempting to delete message {msg_id} for everyone by user {user_id}")
        result = Chat.delete_for_everyone(msg_id, user_id)
        print(f"Delete result: {result}")
        
        if isinstance(result, tuple) and len(result) == 2:
            success, placeholder = result
            return jsonify(success=success, placeholder=placeholder)
        else:
            return jsonify(success=False, error="Invalid result format"), 500
    except Exception as e:
        print(f"Error in delete_everyone route: {e}")
        return jsonify(success=False, error=str(e)), 500

@app.route('/delete_message/<msg_id>', methods=['DELETE'])
def delete_message(msg_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    success = Chat.delete_message(msg_id, session['user_id'])
    return jsonify({'success': success})

@app.route('/mark_message_seen/<msg_id>', methods=['POST'])
def mark_message_seen(msg_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    success = Chat.mark_as_read(msg_id, session['user_id'])
    if success:
        # (optional) broadcast a socket event so the sender sees “👁 Seen”
        socketio.emit('message_status_update', {
            'message_id': msg_id,
            'is_delivered': True,
            'is_seen': True
        }, room=Chat.get_sender(msg_id))
    return jsonify({'success': success})

@app.route('/edit_message', methods=['POST'])
def edit_message():
    try:
        if 'user_id' not in session:
            return jsonify({'success': False, 'error': 'Not logged in'}), 401
            
        msg_id = request.form['message_id']
        new_body = request.form['new_body']
        success = Chat.edit_message(msg_id, session['user_id'], new_body)
        
        if success and socketio:
            # Get the message to find the receiver
            db = get_db()
            try:
                message = db.chats.find_one({'_id': ObjectId(msg_id)})
                if message:
                    # Identify the other party who should receive the update
                    other_email = message['receiver_id'] if message['sender_id'] == session['user_id'] else message['sender_id']
                    
                    # Emit the update to the other participant
                    socketio.emit('message_edited', {
                        'message_id': msg_id,
                        'new_body': new_body
                    }, room=other_email)
            except Exception as e:
                print(f"Error finding message recipient: {e}")
                
        return jsonify({'success': success})
    except Exception as e:
        print(f"Error in edit_message route: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    socketio.run(app, debug=True)