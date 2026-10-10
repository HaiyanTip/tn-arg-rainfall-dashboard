import pandas as pd
import re

def get_base_name(name):
    n = str(name).lower()
    remove_words = [
        ' arg', ' aws', ' tndrra', ' rtff', ' gcc', ' vao office', ' taluk office',
        ' district collectorate office', ' district collector office', ' pups', ' lake',
        ' check dam', ' govt high school', ' govt.high school', ' govt higher secondary school',
        ' government higher secondary school', ' government girls higher secondary school',
        ' primary health centre', ' panchayat union middle school', ' wrd section office',
        ' wrd', ' sub registrar office', ' town panchayat office', ' (south)', ' (north)',
        ' (east)', ' (west)', ' part 1', ' part 2', ' 1', ' 2', ' i', ' ii',
        ' (a)', ' (b)', ' (c)', ' (pal)', ' (w 02)', ' (w 03)', ' (w 11)', ' (w 05)',
        ' veterinary hospital'
    ]
    n = re.sub(r'\(.*?\)', '', n)
    for w in remove_words:
        n = n.replace(w, '')
    n = re.sub(r'[^a-z0-9]', '', n)
    return n.strip()

raw_file = 'tndrra_2026_summary.csv'
df = pd.read_csv(raw_file)

df['base_name'] = df['station_name'].apply(get_base_name)

canonical_mapping = {}
canonical_coords = {}

districts = df['district_name'].unique()

for dist in districts:
    dist_df = df[df['district_name'] == dist]
    unique_stations = dist_df['station_name'].unique()
    
    station_info = []
    for st in unique_stations:
        st_data = dist_df[dist_df['station_name'] == st]
        dates = set(st_data['date'].unique())
        count = len(st_data)
        lat = st_data['latitude'].median()
        lon = st_data['longitude'].median()
        bname = st_data['base_name'].iloc[0]
        station_info.append({
            'name': st,
            'bname': bname,
            'dates': dates,
            'count': count,
            'lat': lat,
            'lon': lon
        })
        
    station_info.sort(key=lambda x: x['count'], reverse=True)
    
    clusters = [] 
    
    for info in station_info:
        placed = False
        for cluster in clusters:
            if len(cluster['dates'].intersection(info['dates'])) == 0:
                same_name = (cluster['bname'] == info['bname'])
                substring_match = (cluster['bname'] in info['bname'] or info['bname'] in cluster['bname'])
                dist_sq = (cluster['lat'] - info['lat'])**2 + (cluster['lon'] - info['lon'])**2
                close_coords = dist_sq < 0.0025 # ~5km radius roughly
                
                if same_name or (substring_match and close_coords):
                    cluster['names'].append(info['name'])
                    cluster['dates'].update(info['dates'])
                    placed = True
                    break
        
        if not placed:
            clusters.append({
                'names': [info['name']],
                'dates': set(info['dates']),
                'master_name': info['name'],
                'bname': info['bname'],
                'lat': info['lat'],
                'lon': info['lon']
            })
    
    for cluster in clusters:
        best_name = cluster['names'][0]
        for n in cluster['names']:
            if len(n) < len(best_name):
                best_name = n
        cluster['master_name'] = best_name
        
        m_name = cluster['master_name']
        m_lat = cluster['lat']
        m_lon = cluster['lon']
        for name in cluster['names']:
            canonical_mapping[(dist, name)] = m_name
            canonical_coords[(dist, name)] = (m_lat, m_lon)

def map_name(row):
    return canonical_mapping.get((row['district_name'], row['station_name']), row['station_name'])
    
def map_lat(row):
    return canonical_coords.get((row['district_name'], row['station_name']), (row['latitude'], row['longitude']))[0]
    
def map_lon(row):
    return canonical_coords.get((row['district_name'], row['station_name']), (row['latitude'], row['longitude']))[1]

df['clean_station_name'] = df.apply(map_name, axis=1)
df['clean_lat'] = df.apply(map_lat, axis=1)
df['clean_lon'] = df.apply(map_lon, axis=1)

clean_df = df[['date', 'district_name', 'clean_station_name', 'total', 'clean_lat', 'clean_lon']].copy()
clean_df.columns = ['date', 'district_name', 'station_name', 'total', 'latitude', 'longitude']

final_df = clean_df.groupby(['date', 'district_name', 'station_name', 'latitude', 'longitude'], as_index=False).max()
try:
    final_df.to_csv('tndrra_2026_cleaned_summary_v2.csv', index=False)
except PermissionError:
    print("Could not overwrite tndrra_2026_cleaned_summary_v2.csv. Using v2 instead.")
    final_df.to_csv('tndrra_2026_cleaned_summary.csv', index=False)
    # also update engine.js/rainfall24h.html to v2 just in case
