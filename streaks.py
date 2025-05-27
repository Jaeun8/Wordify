from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import date

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///steaks.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'supersecretsteak'
CORS(app)

db = SQLAlchemy(app)

# ---------------------------
# Streak Model
# ---------------------------
class Streak(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False)
    date = db.Column(db.Date, default=date.today)

# ---------------------------
# API Routes
# ---------------------------
@app.route("/api/streaks/<username>", methods=["GET"])
def get_streaks(username):
    """Return all streak dates for a specific user."""
    streaks = Streak.query.filter_by(username=username).all()
    return jsonify([s.date.isoformat() for s in streaks])

@app.route("/api/streaks/add", methods=["POST"])
def add_streak():
    """Add today's streak for the user, if not already present."""
    data = request.json
    username = data.get("username")
    today = date.today()

    if not username:
        return jsonify({"error": "Username required"}), 400

    # Prevent duplicates
    existing = Streak.query.filter_by(username=username, date=today).first()
    if not existing:
        new_streak = Streak(username=username, date=today)
        db.session.add(new_streak)
        db.session.commit()

    return jsonify({"status": "success"})

# ---------------------------
# Run the app
# ---------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
