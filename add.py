from app import app, db, Entry, Mood
from datetime import datetime

with app.app_context():
    mood = Mood.query.filter_by(label="Joy").first()

    entry = Entry(
        text="Une belle journée",
        mood_id=mood.id,
        date=datetime(2026, 8, 15)
    )
    db.session.add(entry)
    db.session.commit()
    print("Ajouté, id =", entry.id)