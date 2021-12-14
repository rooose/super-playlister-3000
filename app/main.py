from re import S
from flask import Flask, request, render_template, redirect, session, make_response
from flask.templating import render_template_string
from flask_cors import CORS

from .config import CONFIG
from .spotify_auth import *
from functools import wraps

import time
import ast
import numpy as np
import random

# TODO: Use Flask sessions
app = Flask(__name__)
app.secret_key = "super secret key"
CORS(app)


spotify_helper = SpotifyAuth(CONFIG)
state_key = None


@app.route("/login", methods=['GET'])
def login():
    return render_template('login.html')


@app.route("/auth")
def spotify_auth():
    url = spotify_helper.getAuthUrl()
    response = make_response(redirect(url))
    return response


@app.route('/callback')
def callback():
    # TODO: a state key would be really good
    # if state_key is None or request.args.get('state') != spotify_helper.curr_state_key:
    #    return render_template('index.html', error='State failed.')

    if request.args.get('error'):
        return render_template('index.html', error='Spotify error.')

    else:
        code = request.args.get('code')
        spotify_helper.curr_state_key = None

        success = spotify_helper.getUserToken(request.args['code'])
        if success:
            session['token'] = spotify_helper.token_data[0]
            session['refresh_token'] = spotify_helper.refresh_token
            session['token_expiration'] = spotify_helper.token_data[3]
        else:
            return render_template('index.html', error='Failed to access token.')

    current_user = spotify_helper.getUserInformation(session)
    session['user_id'] = current_user['id']

    return redirect('/')


def authenticated_resource(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if spotify_helper.is_authenticated:
            return f(*args, **kwargs)

        return redirect('/login')

    return decorated


@app.route("/", methods=['GET'])
@authenticated_resource
def home():
    if spotify_helper.needs_refresh:
        spotify_helper.refresh_token()

    return render_template('home.html')


@app.route("/split", methods=['GET'])
@authenticated_resource
def split():
    if spotify_helper.needs_refresh:
        spotify_helper.refresh_token()
    return render_template('split.html', playlists=fetch_playlists())


@app.route("/reorder", methods=['GET'])
@authenticated_resource
def reorder():
    if spotify_helper.needs_refresh:
        spotify_helper.refresh_token()

    return render_template('reorder.html', playlists=fetch_playlists())


@app.route("/merge", methods=['GET', 'POST'])
@authenticated_resource
def merge():
    playlists_to_merge = []
    tracks = []
    tracks_info = []

    if spotify_helper.needs_refresh:
        spotify_helper.refresh_token()

    if request.method == "POST":
        playlists_to_merge = request.form.getlist('playlists_to_merge')
        tracks = fetch_tracks(playlists_to_merge)
        tracks_info = fetch_tracks_info(tracks)
        name = request.form.getstr('out_name')
        make_public = request.form.getstr('out_visibility')
        created_playlist = merge_tracks(tracks_info, name, make_public, session)
        return render_template('done.html', playlists=[created_playlist])

    return render_template('merge.html', playlists=fetch_playlists())


def fetch_playlists():
    playlists = [{
                "id": "saved_tracks",
                "name": "Saved Tracks",
                "tracks_info": {'href':"https://api.spotify.com/v1/me/tracks"}
            }]

    offset = 0
    limit = 50
    url = getAllPlaylistsURL(session['user_id'], limit, offset)

    while True:
        response = spotify_helper.makeGetRequest(session, url)
        items = response['items']
        url = response['next']

        for data in items:
            playlists.append({
                "id": data["id"],
                "name": data["name"],
                "tracks_info": data["tracks"]
            })

        if not url:
            break

    return playlists


def fetch_tracks(playlists_data):
    playlists = {}

    for p in playlists_data:
        data = ast.literal_eval(p)
        playlists[data['id']] = data

    for p_id in playlists:
        url = playlists[p_id]['tracks_info']['href']
        tracks = {}

        while True:
            response = spotify_helper.makeGetRequest(session, url)
            items = response['items']
            url = response['next']

            for data in items:
                track_data = data['track']

                if track_data['type'] != 'track':
                    break

                tracks[track_data["id"]] = {
                    "name": track_data["name"],
                    "url": track_data["href"],
                    "uri": track_data["uri"],
                    "audio_features": None
                }

            if not url:
                break

        playlists[p_id]['tracks'] = tracks

    return playlists


def fetch_tracks_info(playlists) :
    limit = 100
    audio_features_fields = ['danceability', 'energy', 'key', 'loudness', 'mode', 'speechiness', 'acousticness', 'instrumentalness', 'liveness', 'valence', 'tempo']

    for p_id in playlists:
        all_tracks_ids = list(playlists[p_id]['tracks'].keys())
        tracks_chunks = [all_tracks_ids[i:i + limit] for i in range(0, len(all_tracks_ids), limit)] 

        for chunk in tracks_chunks:
            chunk_tracks_ids = ','.join(chunk)
            url = getTracksInfoURL(chunk_tracks_ids)
            response = spotify_helper.makeGetRequest(session, url)
            items = response['audio_features']

            for item in items:
                if item is not None:
                    t_id = item['id']
                    audio_features = np.array([v for k,v in item.items() if k in audio_features_fields])
                    playlists[p_id]['tracks'][t_id]['audio_features'] = audio_features


    return playlists


def merge_tracks(playlists, name, make_public, flask_session):

    tracks_uris = []

    for p_id in playlists:
        for t_id in playlists[p_id]['tracks']:
            tracks_uris.append(playlists[p_id]['tracks'][t_id]['uri'])

    random.shuffle(tracks_uris)
    return create_and_add_playlist(name, make_public, tracks_uris, flask_session)


def create_and_add_playlist(name, make_public, tracks, flask_session):

    url = getCreatePlaylistURL(flask_session['user_id'])
    body = {
        'name': name,
        'description': 'Merge playlist created by SUPER-PLAYLISTER-3000',
        'public': make_public
    }

    created_playlist = spotify_helper.makePostRequest(flask_session, url, body=body)

    limit = 100
    pos = 0
    url = created_playlist['tracks']['href']
    tracks_chunks = [tracks[i:i + limit] for i in range(0, len(tracks), limit)]
    
    for chunk in tracks_chunks:
        body = {
            'position': pos,
            'uris': chunk
        }
        spotify_helper.makePostRequest(flask_session, url, body=body)
        pos += len(chunk)

    return created_playlist


@app.route('/reorder')
@authenticated_resource
def reorder_songs():
    time.sleep(3)
    print("wow reordered so fast")
    return ("nothing")
