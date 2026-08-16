import os
import math
import random
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
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

db = SQLAlchemy(app)

ALLOWED = {
    "image": {"png", "jpg", "jpeg", "gif", "webp"},
    "audio": {"mp3", "wav", "m4a", "ogg"},
    "video": {"mp4", "mov", "webm"},
}

ACTIVITIES = [
    # targeted at low walking
    {"text": "Take a 10-minute walk around the block, no destination needed.", "metric": "walking", "moods": None},
    {"text": "Walk to get a coffee or tea instead of making it at home.", "metric": "walking", "moods": None},
    {"text": "Put on a song and walk around your place for one full track.", "metric": "walking", "moods": None},
    {"text": "Take the stairs a few extra times today, just to move.", "metric": "walking", "moods": None},

    # targeted at low water
    {"text": "Drink a full glass of water right now — an easy win.", "metric": "water", "moods": None},
    {"text": "Refill a water bottle and keep it next to you for the next hour.", "metric": "water", "moods": None},
    {"text": "Swap your next drink for water instead.", "metric": "water", "moods": None},

    # targeted at low went_out
    {"text": "Step outside for five minutes, even just onto a balcony or doorstep.", "metric": "went_out", "moods": None},
    {"text": "Eat your next meal or snack outside if you can.", "metric": "went_out", "moods": None},
    {"text": "Open a window and let some fresh air into the room.", "metric": "went_out", "moods": None},

    # targeted at low happiness / heavy moods
    {"text": "Message a friend, even just to say hi — no big reason needed.", "metric": "happiness", "moods": ["Sadness", "Anxious", "Anger"]},
    {"text": "Revisit a happy memory in your sky and sit with it for a minute.", "metric": "happiness", "moods": ["Sadness", "Anxious", "Anger"]},
    {"text": "Call someone you trust, even for five minutes.", "metric": "happiness", "moods": ["Sadness", "Anxious", "Anger"]},
    {"text": "Write down three small things that went okay today.", "metric": "happiness", "moods": ["Sadness", "Anxious", "Anger"]},
    {"text": "Put on your favorite comfort song and just listen.", "metric": "happiness", "moods": ["Sadness", "Anxious", "Anger"]},

    # light-mood momentum (keep a good streak going)
    {"text": "Since you're feeling good — go for a walk and enjoy it.", "metric": None, "moods": ["Joy", "Calm", "Gratitude", "Love"]},
    {"text": "Share this good mood with someone — send them a message.", "metric": None, "moods": ["Joy", "Calm", "Gratitude", "Love"]},
    {"text": "Write down what's making today feel good, so you can look back on it.", "metric": None, "moods": ["Joy", "Calm", "Gratitude", "Love"]},

    # general / no strong signal either way
    {"text": "Take a short break — step away from the screen for a bit.", "metric": None, "moods": None},
    {"text": "Do some light stretching for five minutes.", "metric": None, "moods": None},
    {"text": "Make a warm drink and sit somewhere quiet for a bit.", "metric": None, "moods": None},
]

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
    radius = min(28 * math.sqrt(index + 1), 320)  
    x = cx + radius * math.cos(angle)
    y = cy + radius * math.sin(angle) * 0.72
    return x, y

# ---------------------------------------------------------
# Wellness grade and tips
# ---------------------------------------------------------

def wellness_grade(check):
    score = (check.walking + check.water + check.happiness + check.went_out) / 4

    if score >= 8:
        letter = "A"
    elif score >= 6:
        letter = "B"
    elif score >= 4:
        letter = "C"
    else:
        letter = "D"

    return round(score, 1), letter


def wellness_tips(check):
    tips = []

    if check.walking < 5:
        tips.append("🚶 Try a short walk today — even ten minutes helps.")
    if check.water < 5:
        tips.append("💧 Drink a glass of water now — easy win.")
    if check.happiness < 5:
        tips.append("💬 Reach out to a friend, or revisit a happy memory in your sky.")
    if check.went_out < 5:
        tips.append("🌤️ Step outside, even just for a few minutes of fresh air.")

    if not tips:
        tips.append("✨ You're doing well across the board — keep it up.")

    return tips

def suggest_activity():
    last_entry = Entry.query.order_by(Entry.date.desc()).first()
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    today_check = next(
        (c for c in WellnessCheck.query.all() if c.date.strftime("%Y-%m-%d") == today_str),
        None
    )
    mood_label = last_entry.mood.label if last_entry else None

    if not last_entry and not today_check:
        return {"text": "Write your first memory, or do today's wellness check-in, to get a suggestion."}

    # 1. If a wellness metric is clearly low, prioritize activities targeting it
    if today_check:
        scores = {
            "walking": today_check.walking,
            "went_out": today_check.went_out,
            "water": today_check.water,
            "happiness": today_check.happiness,
        }
        lowest_metric = min(scores, key=scores.get)
        if scores[lowest_metric] < 6:
            matches = [a for a in ACTIVITIES if a["metric"] == lowest_metric]
            if matches:
                return random.choice(matches)

    # 2. Otherwise, match on mood
    if mood_label:
        mood_matches = [
            a for a in ACTIVITIES
            if a["moods"] and mood_label in a["moods"]
        ]
        if mood_matches:
            return random.choice(mood_matches)

    # 3. Fall back to general activities
    general = [a for a in ACTIVITIES if a["metric"] is None and a["moods"] is None]
    return random.choice(general)

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

class WellnessCheck(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, server_default=db.func.now())
    walking = db.Column(db.Integer, nullable=False)
    water = db.Column(db.Integer, nullable=False)
    happiness = db.Column(db.Integer, nullable=False)
    went_out = db.Column(db.Integer, nullable=False)


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
    today = datetime.utcnow().strftime("%Y-%m-%d")
    now_time = datetime.utcnow().strftime("%H:%M")
    return render_template("new_entry.html", moods=moods, today=today, now_time=now_time)

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

@app.route("/entries", methods=["POST"])
def create_entry():
    text = request.form.get("text", "")
    mood_id = request.form.get("mood_id")
    date_str = request.form.get("date")   # "2026-08-15"
    time_str = request.form.get("time")   # "14:30"

    if date_str and time_str:
        entry_date = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    elif date_str:
        entry_date = datetime.strptime(date_str, "%Y-%m-%d")
    else:
        entry_date = datetime.utcnow()

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

    entry = Entry(text=text, mood_id=mood_id, date=entry_date, media_path=media_path, media_type=media_type)
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

    # every distinct day that has at least one entry, newest first
    all_days = sorted({entry.date.date() for entry in entries}, reverse=True)

    day_param = request.args.get("day")  

    if day_param:
        selected_day = datetime.strptime(day_param, "%Y-%m-%d").date()
    elif all_days:
        selected_day = all_days[0]  # default to most recent day with entries
    else:
        selected_day = None

    day_entries = [e for e in entries if e.date.date() == selected_day] if selected_day else []

    # find this day's position among days that have entries, for Previous/Next
    prev_day = next_day = None
    if selected_day and selected_day in all_days:
        idx = all_days.index(selected_day)
        # all_days is newest-first, so "next" in time is idx-1, "previous" in time is idx+1
        next_day = all_days[idx - 1] if idx > 0 else None
        prev_day = all_days[idx + 1] if idx < len(all_days) - 1 else None

    return render_template(
        "journal.html",
        all_days=all_days,
        selected_day=selected_day,
        day_entries=day_entries,
        prev_day=prev_day,
        next_day=next_day,
    )

@app.errorhandler(413)
def file_too_large(e):
    return render_template("error.html",
                            title="File too big",
                            message="That file is too large to upload. Try a smaller photo, or a shorter clip."), 413

@app.route("/wellness")
def wellness():
    checks = WellnessCheck.query.order_by(WellnessCheck.date.desc()).all()
    today_str = datetime.utcnow().strftime("%Y-%m-%d")

    today_check = next(
        (c for c in checks if c.date.strftime("%Y-%m-%d") == today_str), None
    )

    latest_score = latest_grade = None
    latest_tips = []
    if checks:
        latest_score, latest_grade = wellness_grade(checks[0])
        latest_tips = wellness_tips(checks[0])

    return render_template(
        "wellness.html",
        checks=checks,
        today=today_str,
        today_check=today_check,
        latest_score=latest_score,
        latest_grade=latest_grade,
        latest_tips=latest_tips,
    )

@app.route("/wellness", methods=["POST"])
def save_wellness():
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    checks = WellnessCheck.query.all()
    existing = next(
        (c for c in checks if c.date.strftime("%Y-%m-%d") == today_str), None
    )

    if existing:
        return redirect(url_for("wellness"))  # already checked in, ignore resubmission

    check = WellnessCheck(
        walking=int(request.form.get("walking")),
        water=int(request.form.get("water")),
        happiness=int(request.form.get("happiness")),
        went_out=int(request.form.get("went_out")),
    )
    db.session.add(check)
    db.session.commit()
    return redirect(url_for("wellness"))

@app.route("/brighter")
def brighter():
    suggestion = suggest_activity()
    return render_template("brighter.html", suggestion=suggestion)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)