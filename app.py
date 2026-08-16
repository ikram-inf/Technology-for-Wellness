import os
import math
from datetime import datetime
from flask import Flask, request, send_from_directory, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

# ---------------------------------------------------------
# App setup
# ---------------------------------------------------------
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///starlog.db"
app.config["UPLOAD_FOLDER"] = "uploads"

db = SQLAlchemy(app)

ALLOWED = {
    "image": {"png", "jpg", "jpeg", "gif", "webp"},
    "audio": {"mp3", "wav", "m4a", "ogg"},
    "video": {"mp4", "mov", "webm"},
}

def detect_media_type(filename):
    ext = filename.rsplit(".", 1)[-1].lower()
    for media_type, extensions in ALLOWED.items():
        if ext in extensions:
            return media_type
    return None

# ---------------------------------------------------------
# Stars position
# ---------------------------------------------------------

def star_position(index):
    cx, cy = 500, 350
    angle = index * 137.508 * (math.pi / 180)
    radius = min(16 * math.sqrt(index + 1), 320)
    x = cx + radius * math.cos(angle)
    y = cy + radius * math.sin(angle) * 0.72
    return x, y



# ---------------------------------------------------------
# Tables
# ---------------------------------------------------------
class Mood(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String(20), unique=True, nullable=False)
    color = db.Column(db.String(7), nullable=False)


class Entry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    date = db.Column(db.DateTime, server_default=db.func.now())
    mood_id = db.Column(db.Integer, db.ForeignKey("mood.id"), nullable=False)
    mood = db.relationship("Mood", backref="entries")
    media_path = db.Column(db.String(200))
    media_type = db.Column(db.String(10))


def seed_moods():
    if Mood.query.first():
        return
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


with app.app_context():
    db.create_all()
    seed_moods()


# ---------------------------------------------------------
# Routes
# ---------------------------------------------------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/entries")
def list_entries():
    entries = Entry.query.order_by(Entry.date.desc()).all()
    return render_template("entries.html", entries=entries)

@app.route("/new")
def new_entry_form():
    moods = Mood.query.all()
    return render_template("new_entry.html", moods=moods)

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

@app.route("/entries", methods=["POST"])
def create_entry():
    text = request.form.get("text", "")
    mood_id = request.form.get("mood_id")

    media_path = None
    media_type = None

    file = request.files.get("media")
    if file and file.filename:
        media_type = detect_media_type(file.filename)
        if media_type:
            filename = secure_filename(file.filename)
            filename = f"{int(datetime.utcnow().timestamp())}_{filename}"
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            media_path = f"uploads/{filename}"

    entry = Entry(text=text, mood_id=mood_id, media_path=media_path, media_type=media_type)
    db.session.add(entry)
    db.session.commit()

    return redirect(url_for("journal"))

@app.route("/sky")
def sky():
    entries = Entry.query.order_by(Entry.date.asc()).all()
    for i, entry in enumerate(entries):
        entry.x, entry.y = star_position(i)

    # group entries by mood so we can draw a line connecting each group
    by_mood = {}
    for entry in entries:
        by_mood.setdefault(entry.mood.label, []).append(entry)

    constellations = []
    for label, group in by_mood.items():
        if len(group) >= 2:
            points = " ".join(f"{e.x},{e.y}" for e in group)
            constellations.append({"color": group[0].mood.color, "points": points})

    return render_template("sky.html", entries=entries, constellations=constellations)

@app.route("/entries/<int:entry_id>")
def entry_detail(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    return render_template("entry_detail.html", entry=entry)

@app.route("/journal")
def journal():
    entries = Entry.query.order_by(Entry.date.desc()).all()

    grouped = {}
    for entry in entries:
        day = entry.date.strftime("%B %-d, %Y")
        grouped.setdefault(day, []).append(entry)

    return render_template("journal.html", grouped=grouped)

if __name__ == "__main__":
    app.run(debug=True, port=5000)