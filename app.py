from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# ---------------------------------------------------------
# App setup
# ---------------------------------------------------------
app = Flask(__name__)

# SQLite database — this creates a file called starlog.db
# right next to this app.py. 
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///starlog.db"

db = SQLAlchemy(app)


# ---------------------------------------------------------
# A test table, just to prove the database connection works.
# ---------------------------------------------------------
class Ping(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(100))


# Create the database file + tables if they don't exist yet.
with app.app_context():
    db.create_all()


# ---------------------------------------------------------
# Routes
# ---------------------------------------------------------
@app.route("/")
def hello():
    return "<h1>hello sky</h1><p>Flask is running and talking to SQLite.</p>"

