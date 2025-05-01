from flask import Flask, render_template
from db.mongo_manager import get_db

from models.auth import auth_bp
app = Flask(__name__)


@app.route('/')
def home():
    return render_template('login.html')

app.register_blueprint(auth_bp)

if __name__ == '__main__':
    app.run(debug=True)


