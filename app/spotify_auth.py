# inspired from https://github.com/vanortg/Flask-Spotify-Auth and https://github.com/lucaoh21/Spotify-Discover-2.0
import base64, json, requests
from enum import Enum
import time
import random as rand
import string as string

def createStateKey(size):
    #https://stackoverflow.com/questions/2257441/random-string-generation-with-upper-case-letters-and-digits
    return ''.join(rand.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(size))

class Token_Data(Enum):
    ACCESS_TOKEN = 0
    AUTHENTICATION_HEADER = 1
    AUTHORIZED_SCOPES = 2
    EXPIRATION = 3


class SpotifyAuth():
    SPOTIFY_URL_AUTH = 'https://accounts.spotify.com/authorize?'
    SPOTIFY_URL_TOKEN = 'https://accounts.spotify.com/api/token/'
    RESPONSE_TYPE = 'code'
    HEADER = 'application/x-www-form-urlencoded'

    def __init__(self, config):
        self.refresh_token = ''
        self.token_data = []
        self.config = config
        self.curr_state_key = None

    def clear(self):
        self.refresh_token = ''
        self.token_data = []
        self.curr_state_key = None

    @property
    def is_authenticated(self):
        return len(self.token_data) != 0 and time.time() < self.token_data[Token_Data.EXPIRATION.value]

    @property
    def needs_refresh(self):
        return len(self.token_data) != 0 and time.time() >= self.token_data[Token_Data.EXPIRATION.value]

    @property
    def redirect_uri(self):
        return f"{self.config['callback_url']}:{self.config['port']}/callback"

    def getAuthUrl(self):
        # self.curr_state_key = createStateKey(15)
        return f"{SpotifyAuth.SPOTIFY_URL_AUTH}client_id={self.config['client_id']}&response_type=code&redirect_uri={self.redirect_uri}&scope={self.config['scope']}" #&state={self.curr_state_key}"

    def handleToken(self, response):
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
        return True


    def refreshAuth(self):
        body = {
            "grant_type" : "refresh_token",
            "refresh_token" : self.refresh_token
        }

        post_refresh = requests.post(SpotifyAuth.SPOTIFY_URL_TOKEN, data=body, headers=SpotifyAuth.HEADER)
        payback = json.dumps(post_refresh.text)
        
        return self.handleToken(payback)


    def refreshToken(self):
        self.token_data = self.refreshAuth()


    def checkTokenStatus(self, session):
        if time.time() > session['token_expiration']:
            payload = self.refreshToken(session['refresh_token'])
        if payload != None:
            session['token'] = payload[0]
            session['token_expiration'] = time.time() + payload[1]
        else:
            return None
        return "Success"


    def makeGetRequest(self, session, url, params={}):
        headers = {"Authorization": "Bearer {}".format(session['token'])}
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401 and self.checkTokenStatus(session) != None:
            return self.makeGetRequest(session, url, params)
        else:
            print('makeGetRequest:' + str(response.status_code))
            return None


    def makePostRequest(self, session, url, params={}, body={}):
        headers = {
            "Authorization": "Bearer {}".format(session['token'])
            }

        response = requests.post(url, headers=headers,  params=params, json=body)

        if response.status_code == 201:
            return response.json()
        elif response.status_code == 401 and self.checkTokenStatus(session) != None:
            return self.makePostRequest(session, url, body)
        else:
            print('makePostRequest:' + str(response.status_code))
            return None


    def getUserInformation(self, session):
        url = 'https://api.spotify.com/v1/me'
        payload = self.makeGetRequest(session, url)

        if payload == None:
            return None

        return payload


def getAllPlaylistsURL(user_id, limit, offset=0):
    return f'https://api.spotify.com/v1/users/{user_id}/playlists?limit={limit}&offset={offset}'

def getTracksInfoURL(tracks):
    return f'https://api.spotify.com/v1/audio-features?ids={tracks}'

def getCreatePlaylistURL(user_id):
    return f'https://api.spotify.com/v1/users/{user_id}/playlists'