from flask import Flask, render_template, redirect, url_for, request, session, jsonify
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import random
import requests
import spacy

app = Flask(__name__)
app.secret_key = 'ywefewfwesdf'  # 세션을 위해 필요함

CLIENT_ID = '8cee760b960c48e1af9c1f26673889ca'
CLIENT_SECRET = 'e552578ee4bd4427913ae20d7dbe9483'
REDIRECT_URI = 'http://127.0.0.1:8090/callback'
SCOPE = 'user-read-private'

sp_oauth = SpotifyOAuth(client_id=CLIENT_ID,
                        client_secret=CLIENT_SECRET,
                        redirect_uri=REDIRECT_URI,
                        scope=SCOPE)

@app.route('/streaks')
def streaks():
    return render_template('streaks.html')  

@app.route('/flashcard')
def flashcard():
    return render_template('flashcard.html')  

@app.route('/quiz')
def quiz():
    return render_template('quiz.html')  

@app.route('/login')
def login_page():
    return render_template('Wordify_Login.html')  

@app.route('/signup')
def signup_page():
    return render_template('Wordify_Signup.html')  


# 가사 API
def get_lyrics_ovh(artist, title):
    url = f"https://api.lyrics.ovh/v1/{artist}/{title}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data.get('lyrics', None)
    else:
        return None

# 랜덤 트랙 & 가사
def get_track_with_lyrics(sp):
    pop_artists = [
        'Taylor Swift', 'Ed Sheeran', 'Ariana Grande', 'Bruno Mars', 'Billie Eilish',
        'Dua Lipa', 'The Weeknd', 'Justin Bieber', 'Katy Perry', 'Shawn Mendes',
        'Maroon 5', 'Halsey', 'Selena Gomez', 'Post Malone', 'Lady Gaga',
        'Beyoncé', 'Rihanna', 'Sam Smith', 'Charlie Puth'
    ]
    while True:
        artist = random.choice(pop_artists)
        results = sp.search(q=f'artist:"{artist}"', type='track', limit=10)
        tracks = results['tracks']['items']

        if not tracks:
            continue

        random_track = random.choice(tracks)
        lyrics = get_lyrics_ovh(random_track['artists'][0]['name'], random_track['name'])

        if lyrics:
            return random_track, lyrics

@app.route('/')
def login():
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/callback')
def callback():
    session.clear()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session['token_info'] = token_info
    return redirect(url_for('home'))

@app.route('/home')
def home():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect(url_for('login'))

    sp = spotipy.Spotify(auth=token_info['access_token'])
    random_track, lyrics = get_track_with_lyrics(sp)

    track_info = {
        'title': random_track['name'],
        'artist': random_track['artists'][0]['name'],
        'album_cover': random_track['album']['images'][0]['url'],
        'spotify_url': random_track['external_urls']['spotify'],
        'lyrics': lyrics
    }
    return render_template('homepage.html', track=track_info)

@app.route('/next-track')
def next_track():
    token_info = session.get('token_info', None)
    if not token_info:
        return jsonify({'error': 'No token'}), 401

    sp = spotipy.Spotify(auth=token_info['access_token'])
    random_track, lyrics = get_track_with_lyrics(sp)

    track_info = {
        'title': random_track['name'],
        'artist': random_track['artists'][0]['name'],
        'album_cover': random_track['album']['images'][0]['url'],
        'spotify_url': random_track['external_urls']['spotify'],
        'lyrics': lyrics
    }
    return jsonify(track_info)

nlp = spacy.load("en_core_web_sm")  # spaCy 모델 로드 (사전 설치 필요)

# 사전 API
def get_definition(word):
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        try:
            return data[0]['meanings'][0]['definitions'][0]['definition']
        except (KeyError, IndexError):
            return "정의를 찾을 수 없음"
    else:
        return "정의를 찾을 수 없음"

# 명사/동사 추출
def get_nouns_verbs(text):
    doc = nlp(text)
    filtered_words = [token.text for token in doc if token.pos_ in ('NOUN', 'VERB')]
    unique_words = list(dict.fromkeys(filtered_words))
    return unique_words

# 단어 리스트 & 의미 추출
def get_words_meanings(lyrics, count=10):
    words = get_nouns_verbs(lyrics)
    result = []
    for w in words[:count]:
        meaning = get_definition(w.lower())
        result.append({'word': w, 'meaning': meaning})
    return result

# 새 단어 선택 후 flashcard.html로 렌더링
@app.route('/select')
def select_song():
    token_info = session.get('token_info', None)
    if not token_info:
        return redirect(url_for('login'))

    sp = spotipy.Spotify(auth=token_info['access_token'])
    random_track, lyrics = get_track_with_lyrics(sp)

    flashcards = get_words_meanings(lyrics, count=10)

    session['flashcards'] = flashcards
    session['flashcard_index'] = 0

    return render_template('flashcard.html', flashcards=flashcards)

# 하나씩 단어 넘겨주는 API
@app.route('/next-word')
def next_word():
    flashcards = session.get('flashcards', [])
    index = session.get('flashcard_index', 0)

    if index >= len(flashcards):
        return jsonify({'done': True})

    word_data = flashcards[index]
    session['flashcard_index'] = index + 1
    return jsonify({'word': word_data['word'], 'meaning': word_data['meaning']})

# (선택) 10개 전부 한 번에 넘기는 API
@app.route('/next-words')
def next_words():
    flashcards = session.get('flashcards', [])
    if not flashcards:
        return jsonify({'done': True})
    return jsonify({'words': flashcards})

@app.route('/prev-word')
def prev_word():
    flashcards = session.get('flashcards', [])
    index = session.get('flashcard_index', 1)  # 기본 1부터 시작 (next_word 호출 후 상태 가정)
    
    if index <= 1:
        return jsonify({'done': True, 'message': '첫 단어입니다.'})
    
    index -= 2  
    session['flashcard_index'] = index + 1
    
    word_data = flashcards[index]
    return jsonify({'word': word_data['word'], 'meaning': word_data['meaning']})


if __name__ == '__main__':
    app.run(port=8090, debug=True)


