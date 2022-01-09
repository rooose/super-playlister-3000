from re import S
from flask import Flask, request, render_template, redirect, session, make_response
from flask.templating import render_template_string
from flask_cors import CORS

from .config import CONFIG, APP_SECRET
from .spotify_auth import *
from .matrix_helper import *
from functools import wraps

import time
import ast
import numpy as np
import random
import csv

# TODO: Use Flask sessions
app = Flask(__name__)
app.secret_key = APP_SECRET
CORS(app)


spotify_helper = SpotifyAuth(CONFIG)
state_key = None


@app.route("/login", methods=['GET'])
def login():
    session.clear()
    spotify_helper.clear()
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

        success = spotify_helper.getUserToken(code)
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


@app.route("/split", methods=['GET', 'POST'])
@authenticated_resource
def split():
    if spotify_helper.needs_refresh:
        spotify_helper.refresh_token()

    if request.method == "POST":
        playlists_to_reorder = request.form.getlist('playlists_to_split')
        tracks = fetch_tracks(playlists_to_reorder)
        tracks_info = fetch_tracks_info(tracks)

        split_in = int(request.form.get('split_in'))
        split_in = max(split_in, 1)
        split_by_style = request.form.get('split_order_mode_style')
        visibility =  request.form.get('split_visibility')

        created_playlists = split_playlists(tracks_info, split_in, split_by_style, visibility, session)

        return render_template('done.html', playlists=created_playlists)

    return render_template('split.html', playlists=fetch_playlists())


@app.route("/reorder", methods=['GET', 'POST'])
@authenticated_resource
def reorder():
    if spotify_helper.needs_refresh:
        spotify_helper.refresh_token()

    if request.method == "POST":
        playlists_to_reorder = request.form.getlist('playlists_to_reorder')
        tracks = fetch_tracks(playlists_to_reorder)
        tracks_info = fetch_tracks_info(tracks)

        make_public =  request.form.get('reorder_visibility')
        reorder_by_style = request.form.get('reorder_order_mode_style')

        created_playlist = reorder_playlists(tracks_info, make_public, reorder_by_style, session)
        return render_template('done.html', playlists=created_playlist)

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
        name = request.form.get('merged_playlist_name')
        if name is None:
            name = 'Merged Playlist'

        make_public =  request.form.get('merge_is_public') is not None
        merge_by_style = request.form.get('merge_order_mode_style')
        created_playlist = merge_tracks(tracks_info, name, make_public, merge_by_style, session)
        return render_template('done.html', playlists=[created_playlist])

    return render_template('merge.html', playlists=fetch_playlists())


def fetch_playlists():
    playlists = [{
                "id": "saved_tracks",
                "name": "Saved Tracks",
                "public": False,
                "tracks_info": {'href':"https://api.spotify.com/v1/me/tracks"}
            }]

    offset = 0
    limit = 50
    url = getAllPlaylistsURL(session['user_id'], limit, offset)

    while True:
        response = spotify_helper.makeGetRequest(session, url)
        items = response['items']
        url = response['next']

        for item in items:
            playlists.append({
                "id": item["id"],
                "name": item["name"],
                "tracks_info": item["tracks"],
                "public": item['public']
            })

        if not url:
            break

    playlists = sorted(playlists, key=lambda d: d['name']) 
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
    audio_features_fields = ['danceability', 'energy', 'loudness', 'speechiness', 'acousticness', 'instrumentalness', 'liveness', 'valence', 'tempo'] #minus key and mode

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
                    audio_features = [v for k,v in item.items() if k in audio_features_fields]
                    playlists[p_id]['tracks'][t_id]['audio_features'] = audio_features

        # t_id_to_rmv = []

        # for t_id in playlists[p_id]['tracks']:
        #     if playlists[p_id]['tracks'][t_id]['audio_features'] is None:
        #         t_id_to_rmv.append(t_id)

        # for t_id in t_id_to_rmv:
        #     del playlists[p_id]['tracks'][t_id]

    # with open('out.json', 'w') as f:
    #     json.dump(playlists, f)

    return playlists


def merge_tracks(playlists, name, make_public, merge_by_style, flask_session):
    tracks_uris = []

    for p_id in playlists:
        for t_id in playlists[p_id]['tracks']:
            tracks_uris.append(playlists[p_id]['tracks'][t_id]['uri'])

    if merge_by_style:
        # change it to do smth cool
        random.shuffle(tracks_uris)
    else:
        random.shuffle(tracks_uris)

    merged_playlists = [playlists[p_id]['name'] for p_id in playlists]
    description = f"Merge playlist created by SUPER-PLAYLISTER-3000. Created from : {', '.join(merged_playlists)}"
    return create_and_add_playlist(name, description, make_public, tracks_uris, flask_session)


def reorder_playlists(playlists, visibility, reorder_by_style, flask_session):
    created_playlists = []

    for p_id in playlists:
        tracks_uris = []

        for t_id in playlists[p_id]['tracks']:
            tracks_uris.append(playlists[p_id]['tracks'][t_id]['uri'])

        if reorder_by_style:
            # change it to do smth cool
            random.shuffle(tracks_uris)
        else:
            random.shuffle(tracks_uris)

        name = f"Reordered {playlists[p_id]['name']}"
        description = f"Reordered playlist created by SUPER-PLAYLISTER-3000. Created from : {playlists[p_id]['name']}"

        if visibility == 'ALL_PUBLIC':
            make_public = True
        elif visibility == 'KEEP_VISIBILITY':
            make_public = playlists[p_id]['public']
        else:
            make_public = False

        created_playlists.append(create_and_add_playlist(name, description, make_public, tracks_uris, flask_session))

    return created_playlists


# https://stackoverflow.com/a/11574640
def split_in_n(arr, count):
     return [arr[i::count] for i in range(count)]


def split_playlists(playlists, split_in, split_by_style, visibility, flask_session):
    created_playlists = []

    for p_id in playlists:
        tracks_uris = []
        for t_id in playlists[p_id]['tracks']:
            tracks_uris.append(playlists[p_id]['tracks'][t_id]['uri'])

        if split_by_style:
            split_playlists_content = group_songs(playlists[p_id]['tracks'], 9)

        else:
            random.shuffle(tracks_uris)
            split_playlists_content = split_in_n(tracks_uris, split_in)

        if visibility == 'ALL_PUBLIC':
            make_public = True
        elif visibility == 'KEEP_VISIBILITY':
            make_public = playlists[p_id]['public']
        else:
            make_public = False

        for n, content in enumerate(split_playlists_content):
            name = f"{playlists[p_id]['name']} [SPLIT #{n + 1}]"
            description = f"Split playlist created by SUPER-PLAYLISTER-3000. Created from : {playlists[p_id]['name']}"
            created_playlists.append(create_and_add_playlist(name, description, make_public, content, flask_session))

    return created_playlists


def create_and_add_playlist(name, descr, make_public, tracks, flask_session):
    url = getCreatePlaylistURL(flask_session['user_id'])
    body = {
        'name': name,
        'description': descr,
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
