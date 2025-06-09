from flask import Flask, render_template, redirect, url_for, request, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date, datetime, timedelta
import traceback
import requests
import spacy
import os
import random
import json

try:
    import en_core_web_sm
    nlp = en_core_web_sm.load()
except ImportError:
    nlp = spacy.load("en_core_web_sm")

app = Flask(__name__)
app.secret_key = 'ywefewfwesdf'
app.config['SECRET_KEY'] = 'your_secret_key_here'

# DB 설정
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

# -------------------- 모델 정의 --------------------
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
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    word = db.Column(db.String(100))
    meaning = db.Column(db.String(200))

class Word(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(100), nullable=False)
    meaning = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, nullable=True)
    saved_at = db.Column(db.DateTime, default=datetime.utcnow)

class WordList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    word = db.Column(db.String(100), nullable=False)
    meaning = db.Column(db.String(200), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# -------------------- 외부 API --------------------
def search_itunes_tracks(artist, limit=10):
    url = "https://itunes.apple.com/search"
    params = {'term': artist, 'entity': 'song', 'limit': limit, 'country': 'US'}
    response = requests.get(url, params=params)
    return response.json().get('results', []) if response.status_code == 200 else []

def get_lyrics_ovh(artist, title):
    url = f"https://api.lyrics.ovh/v1/{artist}/{title}"
    response = requests.get(url)
    return response.json().get('lyrics') if response.status_code == 200 else None

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
        track = random.choice(tracks)
        lyrics = get_lyrics_ovh(track.get('artistName'), track.get('trackName'))
        if lyrics:
            return {
                'name': track.get('trackName'),
                'artist': track.get('artistName'),
                'album_cover': track.get('artworkUrl100', '').replace('100x100bb', '300x300bb'),
                'external_url': track.get('trackViewUrl')
            }, lyrics

# -------------------- NLP --------------------
def get_definition(word):
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
    response = requests.get(url)
    if response.status_code == 200:
        try:
            return response.json()[0]['meanings'][0]['definitions'][0]['definition']
        except (KeyError, IndexError):
            return "정의를 찾을 수 없음"
    return "정의를 찾을 수 없음"

def get_nouns_verbs(text):
    doc = nlp(text)
    return list(dict.fromkeys([t.text for t in doc if t.pos_ in ('NOUN', 'VERB')]))

def get_words_meanings(lyrics, count=10):
    words = get_nouns_verbs(lyrics)
    return [{'word': w, 'meaning': get_definition(w.lower())} for w in words[:count]]

# -------------------- 라우팅 --------------------
@app.route('/')
def index():
    return redirect(url_for('home'))

@app.route('/home')
def home():
    track, lyrics = get_track_with_lyrics()
    if not track:
        return "노래를 불러올 수 없습니다.", 500
    return render_template('homepage.html', track={
        'title': track['name'],
        'artist': track['artist'],
        'album_cover': track['album_cover'],
        'spotify_url': track['external_url'],
        'lyrics': lyrics
    })

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
        if User.query.filter((User.username == username) | (User.email == email)).first():
            return render_template('Wordify_Signup.html', error="이미 존재하는 사용자입니다.")

        hashed_pw = generate_password_hash(password)
        new_user = User(name=name, email=email, username=username, password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))

    return render_template('Wordify_Signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user, remember=True)
            today = date.today()
            if not Streak.query.filter_by(username=user.username, date=today).first():
                db.session.add(Streak(username=user.username, date=today))
                db.session.commit()
            return redirect(url_for('home'))
        return render_template('Wordify_Login.html', error="아이디 또는 비밀번호가 잘못되었습니다.")
    return render_template('Wordify_Login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.")
    return redirect(url_for('home'))

@app.route('/my-flashcard', methods=['GET', 'POST'])
@login_required
def my_flashcard():
    if request.method == 'POST':
        words_json = request.form.get('words_json')
        if words_json:
            session['quiz_words'] = words_json
        return redirect(url_for('my_flashcard'))

    words_json = session.pop('quiz_words', None)
    if words_json:
        quiz_words = json.loads(words_json)
    else:
        flashcards = Flashcard.query.filter_by(user_id=current_user.id).all()
        quiz_words = [{"word": f.word, "meaning": f.meaning} for f in flashcards]

    message = request.args.get('message')
    return render_template('flashcard.html', quiz_words=quiz_words, message=message)

@app.route('/save-to-word-list', methods=['POST'])
@login_required
def save_to_word_list():
    words_json = request.form.get('words_json')
    if not words_json:
        return redirect(url_for('my_flashcard', message='error'))

    try:
        words = json.loads(words_json)
        user_id = current_user.id
        existing = Word.query.filter_by(user_id=user_id).with_entities(Word.word).all()
        existing_set = set(w[0] for w in existing)

        new_words = [Word(word=w['word'], meaning=w['meaning'], user_id=user_id)
                     for w in words if w['word'] not in existing_set]

        if not new_words:
            return redirect(url_for('my_flashcard', message='already_saved'))

        db.session.add_all(new_words)
        db.session.commit()
        return redirect(url_for('my_flashcard', message='saved'))

    except Exception as e:
        db.session.rollback()
        print(e)
        return redirect(url_for('my_flashcard', message='error'))

@app.route('/delete_all', methods=['POST'])
@login_required
def delete_all_words():
    Word.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    flash("전체 단어 리스트가 삭제되었습니다.")
    return redirect(url_for('word_list'))

@app.route('/quiz')
def quiz():
    all_words = session.get('quiz_words', [])
    filtered = [w for w in all_words if w['meaning'] != "정의를 찾을 수 없음"]
    quiz_words = random.sample(filtered, min(5, len(filtered))) if filtered else []
    return render_template('quiz.html', quiz_words=quiz_words)

@app.route('/word_list')
@login_required
def word_list():
    word_list = Word.query.filter_by(user_id=current_user.id).all()
    return render_template('list.html', word_list=[{"word": w.word, "meaning": w.meaning} for w in word_list])

@app.route('/select')
@login_required
def select_song():
    track, lyrics = get_track_with_lyrics()
    flashcards = get_words_meanings(lyrics, 50)
    filtered = [f for f in flashcards if f['meaning'] != "정의를 찾을 수 없음"]
    selected = filtered[:10] if len(filtered) >= 10 else filtered
    session['flashcards'] = selected
    session['flashcard_index'] = 0
    session['quiz_words'] = selected
    return render_template('flashcard.html', flashcards=selected, quiz_words=selected)

@app.route('/streaks')
@login_required
def streaks_page():
    return render_template('streaks.html', username=current_user.username)

@app.route('/api/streaks/<username>', methods=['GET'])
@login_required
def get_streaks(username):
    streaks = Streak.query.filter_by(username=username).order_by(Streak.date.desc()).all()
    dates = [s.date for s in streaks]
    today = date.today()
    current_streak = 0
    expected = today

    for d in dates:
        if d == expected:
            current_streak += 1
            expected -= timedelta(days=1)
        else:
            break

    return jsonify({
        "dates": [d.isoformat() for d in dates],
        "current_streak": current_streak
    })

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=8090)
