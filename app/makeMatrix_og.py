# %%
from sklearn_extra.cluster import KMedoids
from sklearn.cluster import AgglomerativeClustering
from sklearn.datasets import make_blobs
from sklearn.preprocessing import StandardScaler
from pyclustering.cluster.kmedoids import kmedoids
from pyclustering.cluster import cluster_visualizer
from pyclustering.utils import read_sample
from pyclustering.samples.definitions import FCPS_SAMPLES
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier
from sklearn.base import BaseEstimator, clone
from sklearn.utils.metaestimators import if_delegate_has_method
from sklearn.manifold import MDS
import numpy as np
import json
from numpy.core.fromnumeric import shape
import pandas as pd
from scipy.spatial import distance

data = open('out.json')
data = json.load(data)

tracks = data[list(data.keys())[0]]['tracks']

# int -> ID
# n_songs = 100
ids = np.array(list(tracks.keys()))

# %%
vector_dict = {}
feature_matrix = np.zeros((9,len(tracks)))
for i, id in enumerate(tracks):
    vector_dict[id] = tracks[id]['audio_features']

#%%
for feature_set in vector_dict.values():
    del feature_set[2]
    del feature_set[3]
#%%
for i, f in enumerate(vector_dict.values()):
    array = np.array(f)
    feature_matrix[:,i] = np.transpose(array)
    

# %%traitement
# for each matrix row
for i in range (feature_matrix.shape[0]): 
    max = np.amax(feature_matrix[i])
    feature_matrix[i] = np.divide(feature_matrix[i], max)

print(feature_matrix)
 # %%
matrix = np.zeros((len(tracks), len(tracks)))
# 
for i, row_id in enumerate(ids):
    for j, col_id in enumerate(ids):
        if j>i:
            matrix[i][j] = distance.cosine(feature_matrix[:,i], feature_matrix[:,j])


# Rendre symmetrique
for i, row_id in enumerate(ids):
    for j, col_id in enumerate(ids):
        if j<i:
            matrix[i][j] = matrix[j][i]

# %%
X = matrix
#%%


#%%
cluster = AgglomerativeClustering(affinity='precomputed', linkage='complete',compute_full_tree=True, n_clusters=15)
cluster_labels = cluster.fit_predict(X)


plt.figure(figsize=(30, 10))

plt.subplot(131)
plot_scatter(X, cluster_labels)
plt.title("Clustering")

plt.show()

# %%
cluster_data = {}
for i , x in enumerate(cluster_labels):
    cluster_data[ids[i]]  = x
# %%
clustr_ids = set(cluster_data.values())
cluster_array = {}
for cid in clustr_ids:
    temp_tracks = [k for k, v in cluster_data.items() if v == cid]
    cluster_array[str(cid)] = temp_tracks

#%% Rename songs
cluster_array_names = cluster_array
for cluster_id in cluster_array:
    for i, song_id in enumerate(cluster_array[cluster_id]):
        cluster_array_names[cluster_id][i] = tracks[song_id]['name']
# %%
with open("clusters.json", "w", encoding='utf8') as outfile:  
    json.dump(cluster_array, outfile, ensure_ascii=False) 

# %%
