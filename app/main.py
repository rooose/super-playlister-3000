from flask import Flask, request, render_template, redirect, g
from flask_cors import CORS

from .config import CONFIG
from .spotify_auth import *
from functools import wraps

# TODO: Use Flask sessions
app = Flask(__name__)
CORS(app)

spotify_helper = SpotifyAuth(CONFIG)

@app.route("/login", methods=['GET'])
def login():
   return render_template('login.html')


@app.route("/auth")
def spotify_auth():
   return redirect(spotify_helper.auth_str)


@app.route('/callback/')
def callback():
   spotify_helper.getUserToken(request.args['code'])
   return redirect('/')


def authenticated_resource(f):
   @wraps(f)
   def decorated(*args, **kwargs):
      print(g)
      if g.user is not None or spotify_helper.is_authenticated:
         return f(*args, **kwargs)

      return redirect('/login')

   return decorated


@app.route("/", methods=['GET'])
@authenticated_resource
def home():
   if spotify_helper.needs_refresh:
      spotify_helper.refresh_token()

   return render_template('home.html')

