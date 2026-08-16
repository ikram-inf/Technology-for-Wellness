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
# Tables
# ---------------------------------------------------------
class Mood(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(20), unique=True, nullable=False)
    color = db.Column(db.String(7), nullable=False)  # hex code, e.g. "#ffd166"


class Entry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    date = db.Column(db.DateTime, server_default=db.func.now())
    mood_id = db.Column(db.Integer, db.ForeignKey("mood.id"), nullable=False)

    # this lets us write entry.mood.color and entry.mood.label directly
    mood = db.relationship("Mood", backref="entries")

def seed_moods():
    if Mood.query.first():
        return  # already seeded, don't duplicate

    moods = [
        Mood(label="Joy", color="#ffd166"),
        Mood(label="Calm", color="#6ec6ca"),
        Mood(label="Love", color="#ff8fab"),
        Mood(label="Gratitude", color="#8ecae6"),
        Mood(label="Sadness", color="#6a7fdb"),
        Mood(label="Anxious", color="#b98cce"),
        Mood(label="Anger", color="#e8604c"),
        Mood(label="Neutral", color="#cbd0e0"),
    ]
    db.session.add_all(moods)
    db.session.commit()

# Create the database file + tables if they don't exist yet.
with app.app_context():
    db.create_all()
    seed_moods()

# ---------------------------------------------------------
# Routes
# ---------------------------------------------------------
@app.route("/")
def hello():
    return "<h1>hello sky</h1><p>Flask is running and talking to SQLite.</p>"

