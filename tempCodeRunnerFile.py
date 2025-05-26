from flask import Flask, render_template, redirect, url_for
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import random
import requests

app = Flask(__name__)

# Spotify 인증 정보 (실제 배포시 보안 주의)
CLIENT_ID = '8cee760b960c48e1af9c1f26673889ca'
CLIENT_SECRET = 'e552578ee4bd4427913ae20d7dbe9483'
REDIRECT_URI = 'http://127.0.0.1:8081/callback'
SCOPE = 'user-read-private'

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    scope=SCOPE
))

@app.route('/')
def home():
    # 랜덤 알파벳으로 검색
    query = random.choice('abcdefghijklmnopqrstuvwxyz')

    # 트랙 검색
    results = sp.search(q=query, type='track', limit=10)
    tracks = results['tracks']['items']

    if not tracks:
        return "<h1>트랙이 없습니다.</h1>"

    # 랜덤 트랙 선택
    random_track = random.choice(tracks)

    # 필요한 정보 추출
    track_info = {
        'title': random_track['name'],
        'artist': random_track['artists'][0]['name'],
        'album_cover': random_track['album']['images'][0]['url'],
        'spotify_url': random_track['external_urls']['spotify']
    }

    # 가사 요청
    artist = track_info['artist']
    title = track_info['title']

    response = requests.get(f"https://api.lyrics.ovh/v1/{artist}/{title}")
    lyrics = response.json().get("lyrics", "가사를 찾을 수 없습니다.")
    track_info['lyrics'] = lyrics

    # 결과를 템플릿에 넘겨줌
    return render_template('homepage.html', track=track_info)


@app.route('/test')
def test():
    return render_template('homepage.html', track={
        'title': '테스트 노래',
        'artist': '테스트 아티스트',
        'album_cover': 'https://via.placeholder.com/200',
        'spotify_url': 'https://spotify.com',
        'lyrics': '테스트 가사입니다.'
    })

if __name__ == '__main__':
    app.run(port=8081, debug=True)
