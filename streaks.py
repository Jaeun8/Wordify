from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from datetime import date

# This will be initialized in app.py and passed into the app
db = SQLAlchemy()

# Create Blueprint
streaks_bp = Blueprint('streaks_bp', __name__)

# ---------------------------
# Model
# ---------------------------
class Streak(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False)
    date = db.Column(db.Date, default=date.today)

# ---------------------------
# Routes
# ---------------------------
@streaks_bp.route('/streaks')
@login_required
def streaks_page():
    return render_template('streaks.html', username=current_user.username)

@streaks_bp.route("/api/streaks/<username>", methods=["GET"])
@login_required
def get_streaks(username):
    streaks = Streak.query.filter_by(username=username).all()
    return jsonify([s.date.isoformat() for s in streaks])

@streaks_bp.route("/api/streaks/add", methods=["POST"])
@login_required
def add_streak():
    data = request.json
    username = data.get("username") or current_user.username
    today = date.today()

    if not username:
        return jsonify({"error": "Username required"}), 400

    existing = Streak.query.filter_by(username=username, date=today).first()
    if not existing:
        new_streak = Streak(username=username, date=today)
        db.session.add(new_streak)
        db.session.commit()

    return jsonify({"status": "success"})
