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
import lyricsgenius
import re

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

# Genius API 설정
GENIUS_API_TOKEN = "YOUR_NEW_TOKEN"
genius = lyricsgenius.Genius(
    GENIUS_API_TOKEN,
    timeout=5,
    skip_non_songs=True,
    excluded_terms=["(Remix)", "(Live)"]
)
genius._session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Connection': 'keep-alive'
})

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

@app.context_processor
def inject_user():
    from flask_login import current_user
    return dict(current_user=current_user)

# -------------------- 외부 API --------------------
def search_itunes_tracks(artist, limit=10):
    url = "https://itunes.apple.com/search"
    params = {'term': artist, 'entity': 'song', 'limit': limit, 'country': 'US'}
    response = requests.get(url, params=params)
    return response.json().get('results', []) if response.status_code == 200 else []

def get_lyrics_genius(artist, title):
    """
    Genius API를 이용해 가사를 가져오고, 영어 가사만 반환합니다.
    """
    try:
        song = genius.search_song(title, artist)
        if not song or not song.lyrics:
            print(f"[Genius] '{artist} - {title}' 가사 없음")
            return None

        lyrics = song.lyrics

        # 영어 가사만 남기기 (한글/스페인어 등 비영어 알파벳이 30% 이상이면 제외)
        english_lines = [line for line in lyrics.split('\n') if re.match(r'^[\[\]A-Za-z0-9\s\,\.\'\"\!\?\-\(\)\:]+$', line) or line.strip() == '']
        english_ratio = len(english_lines) / (len(lyrics.split('\n')) + 1e-5)
        if english_ratio < 0.5:
            print(f"[Genius] 영어 가사 비율이 낮음, 다른 언어일 가능성 높음")
            return None

        lyrics = '\n'.join(english_lines)

        # 기존 전처리 유지
        if "Lyrics\n" in lyrics:
            lyrics = lyrics.split("Lyrics\n", 1)[-1]
        match = re.search(r"(\[.*?\])", lyrics)
        if match:
            lyrics = lyrics[match.start():]
        for key in ["You might also like", "Embed", "More on Genius"]:
            if key in lyrics:
                lyrics = lyrics.split(key, 1)[0]
        lyrics = re.sub(r'\d+Embed', '', lyrics)
        lyrics = re.sub(r'\n{2,}', '\n\n', lyrics)
        return lyrics.strip()
    except Exception as e:
        print(f"[Genius] 가사 오류: {e}")
        return None

def get_track_with_lyrics():
    pop_artists = [
        'Taylor Swift', 'Ed Sheeran', 'Ariana Grande', 'Bruno Mars', 'Billie Eilish',
        'Dua Lipa', 'The Weeknd', 'Justin Bieber', 'Katy Perry', 'Shawn Mendes',
        'Maroon 5', 'Halsey', 'Selena Gomez', 'Post Malone', 'Lady Gaga',
        'Beyoncé', 'Rihanna', 'Sam Smith', 'Charlie Puth'
    ]
    
    for _ in range(20):  # 최대 20번만 시도
        artist = random.choice(pop_artists)
        tracks = search_itunes_tracks(artist)
        # 아티스트명이 정확히 일치하는 곡만 필터링
        filtered_tracks = [t for t in tracks if t.get('artistName', '').lower() == artist.lower()]
        if not filtered_tracks:
            continue
        track = random.choice(filtered_tracks)
        lyrics = get_lyrics_genius(track.get('artistName'), track.get('trackName'))
        if lyrics:
            return {
                'name': track.get('trackName'),
                'artist': track.get('artistName'),
                'album_cover': track.get('artworkUrl100', '').replace('100x100bb', '300x300bb'),
                'external_url': track.get('trackViewUrl')
            }, lyrics
    return None, None

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

            # 오늘 로그인 기록이 없으면 추가 (중복 저장 방지)
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
        if isinstance(words_json, str):
            quiz_words = json.loads(words_json)
        else:
            quiz_words = words_json
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
        # WordList 테이블에서 이미 저장된 단어 조회
        existing = WordList.query.filter_by(user_id=user_id).with_entities(WordList.word).all()
        existing_set = set(w[0] for w in existing)

        # 새 단어만 저장
        new_words = [WordList(word=w['word'], meaning=w['meaning'], user_id=user_id)
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

@app.route('/quiz', methods=['GET', 'POST'])
def quiz():
    if request.method == 'POST':
        words_json = request.form.get('words_json')
        if words_json:
            try:
                quiz_words = json.loads(words_json)
            except:
                quiz_words = []
        else:
            quiz_words = []
        return render_template('quiz.html', quiz_words=quiz_words)
    
    # GET 요청 시 기본 처리
    return render_template('quiz.html', quiz_words=[])

@app.route('/word_list')
@login_required
def word_list():
    word_objs = WordList.query.filter_by(user_id=current_user.id).all()
    words = [{"word": w.word, "meaning": w.meaning} for w in word_objs]
    return render_template('list.html', words=words)


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
    # 날짜 기준으로 내림차순 정렬 (최근 기록부터)
    streaks = Streak.query.filter_by(username=username).order_by(Streak.date.desc()).all()
    dates = [s.date for s in streaks]

    # 현재 연속 streak 계산
    today = date.today()
    current_streak = 0
    expected_day = today

    for d in dates:
        if d == expected_day:
            current_streak += 1
            expected_day -= timedelta(days=1)
        elif (expected_day - d).days == 1:
            # 하루 차이로 연속이 끊김
            break
        else:
            break

    return jsonify({
        "dates": [d.isoformat() for d in dates],
        "current_streak": current_streak
    })

@app.route('/playlist')
def playlist():
    track_list = []
    seen_titles = set()

    while len(track_list) < 5:
        track, lyrics = get_track_with_lyrics()
        if not track or not lyrics:
            break  # fail gracefully

        if track['name'] in seen_titles:
            continue
        seen_titles.add(track['name'])

        track['lyrics'] = lyrics
        track_list.append(track)

    return render_template('music.html', tracks=track_list)

@app.route('/api/refresh-tracks')
def refresh_tracks():
    tracks = []
    for _ in range(5):
        track, lyrics = get_track_with_lyrics()
        track['lyrics'] = lyrics
        tracks.append(track)
    return jsonify(tracks)

@app.route('/make-flashcard', methods=['POST'])
def make_flashcard():
    data = request.get_json()
    words = data.get('words', [])
    # 세션이나 다른 방법으로 단어들 넘기기
    session['flashcard_words'] = words
    return redirect(url_for('flashcard_page'))

@app.route('/generate-flashcard', methods=['POST'])
@login_required
def generate_flashcard():
    try:
        data = request.get_json()
        lyrics = data.get('lyrics', '')
        if not lyrics:
            return jsonify({'error': '가사가 없습니다.'}), 400

        flashcards = get_words_meanings(lyrics, count=30)
        filtered = [f for f in flashcards if f['meaning'] != "정의를 찾을 수 없음"]
        selected = filtered[:10] if len(filtered) >= 10 else filtered

        session['quiz_words'] = selected
        return redirect(url_for('my_flashcard'))

    except Exception as e:
        print("[Flashcard 생성 실패]", e)
        traceback.print_exc()
        return jsonify({'error': '서버 오류'}), 500



if __name__ == "__main__":
    # Render.com은 환경변수 PORT를 제공
    port = int(os.environ.get('PORT', 8090))
    app.run(host='0.0.0.0', port=port)
