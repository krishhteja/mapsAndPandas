import os
import numpy as np
import pandas as pd
from geopy.geocoders import Nominatim
import requests
import matplotlib.cm as cm
import matplotlib.colors as colors
from sklearn.cluster import KMeans
import folium

print('Libraries imported.')

pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)


clientId = 'UPDATE_FOURSQUARE_CLIENT_ID'
clientSecret = 'UPDATE_FOURSQUARE_CLIENT_SECRET'
version = '20180606'
limit = 500
radius = 500

address = 'Chicago'
geolocator = Nominatim(user_agent="chicago_explorer")
latitude = 41.8114215
longitude = -87.7261651
try:
    location = geolocator.geocode(address)
    latitude = location.latitude
    longitude = location.longitude
    print('The geograpical coordinate of {} City are {}, {}.'.format(address, latitude, longitude))
except Exception as e:
    print(e)

def getData():
    #get data from wikipedia
    url = 'https://en.wikipedia.org/wiki/List_of_neighborhoods_in_Chicago'
    data = requests.get(url, verify=False)
    tables = pd.read_html(data.text)
    PostalCode_df = pd.DataFrame(tables[0])
    print(PostalCode_df['Neighborhood'])

    #match coordinates using nominatim
    nom = Nominatim()
    PostalCode_df["Coordinates"] = PostalCode_df["Neighborhood"].apply(nom.geocode)
    PostalCode_df["Latitude"] = PostalCode_df["Coordinates"].apply(lambda x: x.latitude if x != None else None)
    PostalCode_df["Longitude"] = PostalCode_df["Coordinates"].apply(lambda x: x.longitude if x != None else None)
    PostalCode_df.rename(columns={'Neighborhood': 'Borough', 'Community area': 'Neighborhood'}, inplace=True)
    print(PostalCode_df)
    try:
        PostalCode_df.to_csv ("demo.csv", index = None, header=True)
    except:
        print("failed to export to csv")

def getNearbyVenues(names, latitudes, longitudes, radius=500):
    venues_list = []
    print("working on your stuff")
    for name, lat, lng in zip(names, latitudes, longitudes):
        #get venue and interesting places nearby using foursquare api
        try:
            url = 'https://api.foursquare.com/v2/venues/explore?&client_id={}&client_secret={}&v={}&ll={},{}&radius={}&limit={}'.format(clientId, clientSecret, version, lat, lng, radius, limit)
            result = requests.get(url)
            #In case of 400 or error, ignore the reponse and continue to next
            if 'warning' in result.json()['response']:
                print("warning")
            elif result.status_code == 400:
                print("warning")
            else:
                results = result.json()["response"]['groups'][0]['items']
                print(results)
                venues_list.append([(name, lat, lng, v['venue']['name'], v['venue']['location']['lat'], v['venue']['location']['lng'], v['venue']['categories'][0]['name']) for v in results])
        except Exception as e:
            print(e)
    nearby_venues = pd.DataFrame([item for venue_list in venues_list for item in venue_list])
    nearby_venues.columns = ['Neighborhood', 'Neighborhood Latitude', 'Neighborhood Longitude', 'Venue', 'Venue Latitude', 'Venue Longitude', 'Venue Category']

    return (nearby_venues)

def returnMostCommonVenues(row, num_top_venues):
    #find most common venue and return
    row_categories = row.iloc[1:]
    row_categories_sorted = row_categories.sort_values(ascending=False)

    return row_categories_sorted.index.values[0:num_top_venues]


def magic():
    df = pd.read_csv("demo.csv")
    venues = getNearbyVenues(names=df['Neighborhood'], latitudes=df['Latitude'], longitudes=df['Longitude'])
    print(venues.shape)
    venues.groupby('Neighborhood').count()

    # one hot encoding
    oneHotEncoding = pd.get_dummies(venues[['Venue Category']], prefix="", prefix_sep="")

    # add neighborhood column back to dataframe
    oneHotEncoding['Neighborhood'] = venues['Neighborhood']

    # move neighborhood column to the first column
    fixedColumns = [oneHotEncoding.columns[-1]] + list(oneHotEncoding.columns[:-1])
    oneHotEncoding = oneHotEncoding[fixedColumns]

    grouped = oneHotEncoding.groupby('Neighborhood').mean().reset_index()

    countOfTopVenues = 5

    for hood in grouped['Neighborhood']:
        print("----" + hood + "----")
        temp = grouped[grouped['Neighborhood'] == hood].T.reset_index()
        temp.columns = ['venue', 'freq']
        temp = temp.iloc[1:]
        temp['freq'] = temp['freq'].astype(float)
        temp = temp.round({'freq': 2})
        print(temp.sort_values('freq', ascending=False).reset_index(drop=True).head(countOfTopVenues))
        print('\n')

    countOfTopVenues = 10

    indicators = ['st', 'nd', 'rd']

    # create columns according to number of top venues
    columns = ['Neighborhood']
    for ind in np.arange(countOfTopVenues):
        try:
            columns.append('{}{} Most Common Venue'.format(ind + 1, indicators[ind]))
        except:
            columns.append('{}th Most Common Venue'.format(ind + 1))

    # create a new dataframe
    sortedNeighborhoodVenues = pd.DataFrame(columns=columns)
    sortedNeighborhoodVenues['Neighborhood'] = grouped['Neighborhood']

    print("here")
    for ind in np.arange(grouped.shape[0]):
        sortedNeighborhoodVenues.iloc[ind, 1:] = returnMostCommonVenues(grouped.iloc[ind, :], countOfTopVenues)

    # set number of clusters
    kClusters = 3

    groupedCluster = grouped.drop('Neighborhood', 1)

    # run k-means clustering
    kmeans = KMeans(n_clusters=kClusters, random_state=0).fit(groupedCluster)

    # check cluster labels generated for each row in the dataframe
    kmeans.labels_[0:10]
    print("again here")
    # add clustering labels
    sortedNeighborhoodVenues.insert(0, 'ClusterLabels', kmeans.labels_)

    merged = df
    merged = merged.join(sortedNeighborhoodVenues.set_index('Neighborhood'), on='Neighborhood')

    merged = merged.dropna()
    merged["ClusterLabels"] = merged.ClusterLabels.astype(int)

    # create map
    mapClusters = folium.Map(location=[latitude, longitude], zoom_start=11)

    # set color scheme for the clusters
    x = np.arange(kClusters)
    ys = [i + x + (i * x) ** 2 for i in range(kClusters)]
    colors_array = cm.rainbow(np.linspace(0, 1, len(ys)))
    rainbow = [colors.rgb2hex(i) for i in colors_array]
    print("almost done dana done")

    # add markers to the map
    markers_colors = []
    for lat, lon, poi, cluster in zip(merged['Latitude'], merged['Longitude'], merged['Neighborhood'], merged['ClusterLabels']):
        label = folium.Popup(str(poi) + ' Cluster ' + str(cluster), parse_html=True)
        folium.CircleMarker([lat, lon], radius=5, popup=label, color=rainbow[cluster - 1], fill=True, fill_color=rainbow[cluster - 1], fill_opacity=0.7).add_to(mapClusters)

    mapClusters.save("demo.html")
    print("Your html is saved as demo.html in " + os.path.dirname(os.path.realpath(__file__)))

try:
    with open("demo.csv", "r"):
        magic()
except:
    getData()
    magic()
