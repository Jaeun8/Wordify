from flask import Flask, render_template, redirect, url_for, request, session
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import random
import requests


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

    # 랜덤 알파벳으로 검색
    import random
    query = random.choice('abcdefghijklmnopqrstuvwxyz')

    results = sp.search(q=query, type='track', limit=10)
    tracks = results['tracks']['items']

    if not tracks:
        return "<h1>트랙이 없습니다.</h1>"

    random_track = random.choice(tracks)

    track_info = {
        'title': random_track['name'],
        'artist': random_track['artists'][0]['name'],
        'album_cover': random_track['album']['images'][0]['url'],
        'spotify_url': random_track['external_urls']['spotify']
    }

    # ... (가사 API 호출 및 렌더링 코드 동일)

    return render_template('homepage.html', track=track_info)

if __name__ == '__main__':
    app.run(port=8090, debug=True)
