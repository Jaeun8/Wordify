from flask import Flask, render_template, redirect, url_for, request, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date
import traceback
import requests
import spacy
import os
import random

try:
    import en_core_web_sm
    nlp = en_core_web_sm.load()
except ImportError:
    nlp = spacy.load("en_core_web_sm")


app = Flask(__name__)
app.secret_key = 'ywefewfwesdf'
app.config['SECRET_KEY'] = 'your_secret_key_here'

# 1) 데이터베이스 경로 및 폴더 처리 - instance 폴더가 없으면 생성
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_FOLDER = os.path.join(BASE_DIR, 'instance')

if not os.path.exists(INSTANCE_FOLDER):
    os.makedirs(INSTANCE_FOLDER)

DB_PATH = os.path.join(INSTANCE_FOLDER, 'db.sqlite')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


# -------------- 모델 ----------------
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

class Flashcard(db.Model):
    __tablename__ = 'flashcard'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    word = db.Column(db.String(100))
    meaning = db.Column(db.String(200))


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# --------- iTunes API 관련 함수 --------------

def search_itunes_tracks(artist, limit=10):
    url = f"https://itunes.apple.com/search"
    params = {
        'term': artist,
        'entity': 'song',
        'limit': limit,
        'country': 'US'
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        return data.get('results', [])
    return []

def get_lyrics_ovh(artist, title):
    url = f"https://api.lyrics.ovh/v1/{artist}/{title}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data.get('lyrics', None)
    else:
        return None

def get_track_with_lyrics():
    pop_artists = [
        'Taylor Swift', 'Ed Sheeran', 'Ariana Grande', 'Bruno Mars', 'Billie Eilish',
        'Dua Lipa', 'The Weeknd', 'Justin Bieber', 'Katy Perry', 'Shawn Mendes',
        'Maroon 5', 'Halsey', 'Selena Gomez', 'Post Malone', 'Lady Gaga',
        'Beyoncé', 'Rihanna', 'Sam Smith', 'Charlie Puth'
    ]
    while True:
        artist = random.choice(pop_artists)
        tracks = search_itunes_tracks(artist)
        if not tracks:
            continue
        random_track = random.choice(tracks)

        track_name = random_track.get('trackName')
        artist_name = random_track.get('artistName')
        album_cover = random_track.get('artworkUrl100', '').replace('100x100bb', '300x300bb')
        itunes_url = random_track.get('trackViewUrl')

        lyrics = get_lyrics_ovh(artist_name, track_name)
        if lyrics:
            return {
                'name': track_name,
                'artist': artist_name,
                'album_cover': album_cover,
                'external_url': itunes_url
            }, lyrics


# ---------------- NLP & 단어 뜻 관련 함수 ------------------

def get_definition(word):
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        try:
            return data[0]['meanings'][0]['definitions'][0]['definition']
        except (KeyError, IndexError):
            return "\uc815\uc758\ub97c \ucc3e\uc744 \uc218 \uc5c6\uc74c"
    else:
        return "\uc815\uc758\ub97c \ucc3e\uc744 \uc218 \uc5c6\uc74c"

def get_nouns_verbs(text):
    doc = nlp(text)
    filtered_words = [token.text for token in doc if token.pos_ in ('NOUN', 'VERB')]
    unique_words = list(dict.fromkeys(filtered_words))
    return unique_words

def get_words_meanings(lyrics, count=10):
    words = get_nouns_verbs(lyrics)
    result = []
    for w in words[:count]:
        meaning = get_definition(w.lower())
        result.append({'word': w, 'meaning': meaning})
    return result


# ---------------- Routes ----------------

@app.route('/')
def index():
    return redirect(url_for('home'))

@app.route('/home')
def home():
    track_data, lyrics = get_track_with_lyrics()
    if not track_data:
        return "\ub178\ub798\ub97c \ubd88\ub7ec\uc62c \uc218 \uc5c6\uc2b5\ub2c8\ub2e4.", 500

    track_info = {
        'title': track_data['name'],
        'artist': track_data['artist'],
        'album_cover': track_data['album_cover'],
        'spotify_url': track_data['external_url'],
        'lyrics': lyrics
    }
    return render_template('homepage.html', track=track_info)

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

            today = date.today()
            if not Streak.query.filter_by(username=user.username, date=today).first():
                db.session.add(Streak(username=user.username, date=today))
                db.session.commit()

            return redirect(url_for('home'))
        else:
            return render_template('Wordify_Login.html', error="아이디 또는 비밀번호가 잘못되었습니다.")

    return render_template('Wordify_Login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

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
        return jsonify({"message": "Streak added"}), 200
    else:
        return jsonify({"message": "Already exists"}), 200

@app.route('/my-flashcard')
@login_required
def my_flashcard():
    flashcards = Flashcard.query.filter_by(user_id=current_user.id).all()
    quiz_words = [{"word": f.word, "meaning": f.meaning} for f in flashcards]
    return render_template('flashcard.html', flashcards=flashcards, quiz_words=quiz_words)


@app.route('/select')
@login_required
def select_song():
    track_data, lyrics = get_track_with_lyrics()
    if not track_data:
        return redirect(url_for('home'))

    flashcards = get_words_meanings(lyrics, count=10)
    session['flashcards'] = flashcards
    session['flashcard_index'] = 0
    session['quiz_words'] = flashcards

    return render_template('flashcard.html', flashcards=flashcards, quiz_words=flashcards)


@app.route('/flashcard/save', methods=['POST'])
@login_required
def save_flashcard():
    data = request.json
    word = data.get('word')
    meaning = data.get('meaning')
    user_id = current_user.id

    if not word or not meaning:
        return jsonify({"error": "Word and meaning are required"}), 400

    flashcard = Flashcard(user_id=user_id, word=word, meaning=meaning)
    db.session.add(flashcard)
    db.session.commit()
    return jsonify({"message": "Flashcard saved"}), 200

@app.route('/next-track')
def next_track():
    track_data, lyrics = get_track_with_lyrics()
    if not track_data:
        return jsonify({'error': 'No track found'}), 404

    track_info = {
        'title': track_data['name'],
        'artist': track_data['artist'],
        'album_cover': track_data['album_cover'],
        'spotify_url': track_data['external_url'],
        'lyrics': lyrics
    }
    return jsonify(track_info)

@app.route('/quiz')
def quiz():
    quiz_words = session.get('quiz_words', [])
    return render_template('quiz.html', quiz_words=quiz_words)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)