from flask import Flask, request, render_template, redirect, session, make_response
from flask_cors import CORS

from .config import CONFIG
from .spotify_auth import *
from functools import wraps

import time

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

    return render_template('reorder.html')


@app.route("/merge", methods=['GET'])
@authenticated_resource
def merge():
    if spotify_helper.needs_refresh:
        spotify_helper.refresh_token()

    return render_template('merge.html')


@app.route('/fetch')
@authenticated_resource
def fetch_playlists():
    playlists = []
    offset = 0
    limit = 50
    url = getAllPlaylistsURL(session['user_id'], limit, offset)

    while True:
        response = spotify_helper.makeGetRequest(session, url)
        items = response['items']
        url = response['next']

        if not url:
            break

        for data in items:
            playlists.append({
                "id":data["id"],
                "name": data["name"],
                "tracks_info": data["tracks"]
            })

    return playlists


@app.route('/reorder')
@authenticated_resource
def reorder_songs():
    time.sleep(3)
    print("wow reordered so fast")
    return ("nothing")
