# inspired from https://github.com/vanortg/Flask-Spotify-Auth
import base64, json, requests
from enum import Enum
import time

class Token_Data(Enum):
    ACCESS_TOKEN = 0
    AUTHENTICATION_HEADER = 1
    AUTHORIZED_SCOPES = 2
    EXPIRATION = 3


class SpotifyAuth():
    SPOTIFY_URL_AUTH = 'https://accounts.spotify.com/authorize/?'
    SPOTIFY_URL_TOKEN = 'https://accounts.spotify.com/api/token/'
    RESPONSE_TYPE = 'code'
    HEADER = 'application/x-www-form-urlencoded'

    def __init__(self, config):
        self.refresh_token = ''
        self.token_data = []

        self.config = config

    @property
    def is_authenticated(self):
        return len(self.token_data) != 0 and time.time() < self.token_data[Token_Data.EXPIRATION.value]

    @property
    def needs_refresh(self):
        return len(self.token_data) != 0 and time.time() >= self.token_data[Token_Data.EXPIRATION.value]

    @property
    def redirect_uri(self):
        return f"{self.config['callback_url']}:{self.config['port']}/callback/"

    @property
    def auth_str(self): # vas getUser
        return f"{SpotifyAuth.SPOTIFY_URL_AUTH}client_id={self.config['client_id']}&response_type=code&redirect_uri={self.redirect_uri}&scope={self.config['scope']}"

    def handleToken(self, response):
        print("RESPONSE: ", response)
        auth_head = {"Authorization": f"Bearer {response['access_token']}"}
        self.refresh_token = response["refresh_token"]
        return [response["access_token"], auth_head, response["scope"], time.time() + response["expires_in"]]


    def getToken(self, code):
        body = {
            "grant_type": 'authorization_code',
            "code" : code,
            "redirect_uri": self.redirect_uri,
            "client_id":  self.config['client_id'],
            "client_secret": self.config['client_secret']
        }

        to_encode = "{}:{}".format(self.config['client_id'], self.config['client_secret'])
        encoded = base64.urlsafe_b64encode(to_encode.encode()).decode()
        headers = {"Content-Type" : SpotifyAuth.HEADER, "Authorization" : f"Basic {encoded}"} 

        post = requests.post(SpotifyAuth.SPOTIFY_URL_TOKEN, params=body, headers=headers)
        return self.handleToken(json.loads(post.text))


    def getUserToken(self, code):
        self.token_data = self.getToken(code)


    def refreshAuth(self):
        body = {
            "grant_type" : "refresh_token",
            "refresh_token" : self.refresh_token
        }

        post_refresh = requests.post(SpotifyAuth.SPOTIFY_URL_TOKEN, data=body, headers=SpotifyAuth.HEADER)
        payback = json.dumps(post_refresh.text)
        
        return self.handleToken(payback)


    def refreshToken(self, time):
        time.sleep(time)
        self.token_data = self.refreshAuth()


