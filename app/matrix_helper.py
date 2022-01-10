from scipy.spatial.kdtree import distance_matrix
from sklearn.cluster import AgglomerativeClustering
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial import distance
from k_means_constrained import KMeansConstrained
import random

def build_feature_matrix(tracks, tracks_ids, n_audio_features):
    vector_dict = {}
    feature_matrix = np.zeros((n_audio_features, len(tracks_ids)))

    for i, t_id in enumerate(tracks_ids):
        vector_dict[i] = tracks[t_id]['audio_features']

    for i, feature_vec in enumerate(vector_dict.values()):
        feature_matrix[:,i] = np.transpose(np.array(feature_vec))

    feature_matrix_norm = (feature_matrix - feature_matrix.min(axis=0)) / feature_matrix.ptp(axis=0)

    return feature_matrix_norm


def calculate_dist_matrix(feature_matrix):
    n_songs = feature_matrix.shape[1]
    dist_matrix = np.zeros((n_songs, n_songs))

    for i in range(n_songs):
        for j in range(n_songs):
            if j > i:
                dist_matrix[i][j] = distance.cosine(feature_matrix[:,i], feature_matrix[:,j])
                dist_matrix[j][i] = dist_matrix[i][j]

    return dist_matrix


def plot_scatter(X,  color, alpha=0.7):
    return plt.scatter(X[:, 0],
                       X[:, 1],
                       c=color,
                       alpha=alpha,
                       edgecolor='k')


def group_songs(tracks, n_audio_features):
    playlist_no_info = []
    tracks_ids = []

    for t_id in tracks:
        if tracks[t_id]['audio_features'] is None:
            playlist_no_info.append(tracks[t_id]['uri'])
        else:
            tracks_ids.append(t_id)

    feature_matrix = build_feature_matrix(tracks, tracks_ids, n_audio_features)
    distance_matrix = calculate_dist_matrix(feature_matrix)

    # cluster = AgglomerativeClustering(affinity='precomputed', linkage='complete',compute_full_tree=True, n_clusters=15)
    cluster = KMeansConstrained(size_min=3, random_state=0)
    cluster_labels = cluster.fit_predict(distance_matrix)

    # show_clusters(distance_matrix, cluster_labels)


    playlists = { 'playlist_no_info': playlist_no_info }

    for i, label in enumerate(cluster_labels):
        content = playlists.get(label, [])
        content.append(tracks[tracks_ids[i]]['uri'])
        playlists[label] = content

    playlists = list(playlists.values())
    playlists = [ p for p in playlists if len(p) > 0]

    return playlists


def order_songs(tracks, n_audio_features):
    no_info = []
    tracks_ids = []

    for t_id in tracks:
        if tracks[t_id]['audio_features'] is None:
            no_info.append(tracks[t_id]['uri'])
        else:
            tracks_ids.append(t_id)

    feature_matrix = build_feature_matrix(tracks, tracks_ids, n_audio_features)
    distance_matrix = calculate_dist_matrix(feature_matrix)

    n_songs = len(tracks_ids)
    curr_song = random.randint(0, n_songs - 1)

    visited = [curr_song]

    for _ in range(1, n_songs):

        for s in range(n_songs):
            distance_matrix[s][curr_song] = float('inf')

        curr_song = np.argmin(distance_matrix[curr_song, :])
        visited.append(curr_song)

    reordered = [tracks[tracks_ids[v]]['uri'] for v in visited] + no_info

    # TODO: Add randomness

    return reordered
