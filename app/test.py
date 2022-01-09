from .matrix_helper import *
import json

with open('out.json', 'r') as f:
    data = json.load(f)

tracks = data['saved_tracks']['tracks']
group_songs(tracks)