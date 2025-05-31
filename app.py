from flask import Flask, render_template, redirect, url_for, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date
import traceback

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ------------------- Models -------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)

class Streak(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False)
    date = db.Column(db.Date, default=date.today)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ------------------- Routes -------------------
@app.route('/')
@login_required
def home():
    dummy_track = {
        "title": "예시 제목",
        "artist": "예시 아티스트",
        "lyrics": "예시 가사입니다.",
        "album_cover": "https://via.placeholder.com/150",
        "spotify_url": "#"
    }
    return render_template('homepage.html', track=dummy_track)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('your-name')
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm-password')

        if not all([name, email, username, password, confirm_password]):
            return render_template('Wordify_Signup.html', error="모든 필드를 입력해주세요.")
        if password != confirm_password:
            return render_template('Wordify_Signup.html', error="비밀번호가 일치하지 않습니다.")
        
        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()
        if existing_user:
            return render_template('Wordify_Signup.html', error="이미 존재하는 사용자입니다.")
        
        try:
            hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
            new_user = User(name=name, email=email, username=username, password=hashed_pw)
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('login'))
        except Exception as e:
            print(traceback.format_exc())
            return render_template('Wordify_Signup.html', error=f"회원가입 중 오류 발생: {str(e)}")

    return render_template('Wordify_Signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            return render_template('Wordify_Login.html', error="모든 필드를 입력해주세요.")

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user, remember=True)
            return redirect(url_for('home'))
        else:
            return render_template('Wordify_Login.html', error="아이디 또는 비밀번호가 잘못되었습니다.")
    
    return render_template('Wordify_Login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/streaks')
@login_required
def streaks_page():
    return render_template('streaks.html', username=current_user.username)

@app.route('/api/streaks/<username>', methods=['GET'])
@login_required
def get_streaks(username):
    streaks = Streak.query.filter_by(username=username).all()
    return jsonify([s.date.isoformat() for s in streaks])

@app.route('/api/streaks/add', methods=['POST'])
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

# ------------------- App Launch -------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
