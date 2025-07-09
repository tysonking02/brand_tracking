import streamlit as st
import pandas as pd
import leafmap.foliumap as leafmap
from folium.plugins import HeatMap
import re
from shapely.geometry import Polygon
import geopandas as gpd
import unicodedata

def clean_text(val):
    if isinstance(val, str):
        return unicodedata.normalize("NFKD", val).encode("ascii", "ignore").decode("ascii")
    return val

@st.cache_data
def load_data(path):
    df = pd.read_csv(path)
    df['manager'] = df['manager'].fillna('').astype(str).str.strip()
    return df

df = load_data('data/branded_sites.csv')

df['property'] = df['property'].apply(clean_text)
df['manager'] = df['manager'].apply(clean_text)
df['owner'] = df['owner'].apply(clean_text)

df['lat_bin'] = df['Latitude'].round(2)
df['lon_bin'] = df['Longitude'].round(2)

tile_density = (
    df.groupby(['MarketName', 'lat_bin', 'lon_bin'])
    .agg(
        total_units=('UnitCount', 'sum'),
        total_assets=('PropertyID', 'count')
    )
    .reset_index()
)

top_tiles = (
    tile_density.sort_values(['MarketName', 'total_units'], ascending=[True, False])
    .groupby('MarketName')
    .head(3)
    .copy()
)

# Read in Survey Data

market_map = {
    'Atlanta': 'Atlanta, GA',
    'Austin': 'Austin, TX',
    'Charlotte': 'Charlotte, NC',
    'Columbus': 'Columbus, OH',
    'DC': 'Washington, DC',
    'Dallas': 'Dallas-Fort Worth, TX',
    'Denver': 'Denver, CO',
    'Houston': 'Houston, TX',
    'Nashville': 'Nashville, TN',
    'Orlando': 'Orlando, FL',
    'Phoenix': 'Phoenix, AZ',
    'Raleigh': 'Raleigh, NC',
    'South Florida': 'Miami, FL',
    'Tampa': 'Tampa, FL',
    'Tucson': 'Tucson, AZ'
}

manager_map = {
    'amli': 'AMLI',
    'arium': 'ARIUM',
    'avalon': 'AvalonBay',
    'bell': 'Bell',
    'bozzuto': 'Bozzuto',
    'broadstone': 'Broadstone',  
    'camden': 'Camden',
    'cortland': 'Cortland',
    'cushman_&_wakefield': 'Pinnacle', 
    'encantada': 'HSL', 
    'gables': 'Gables', 
    # 'greenwater': 'Greenwater',
    'greystar': 'Greystar',
    'hsl': 'HSL', 
    'lincoln': 'Willow Bridge', 
    'maa': 'MAA',
    'mark_taylor': 'Mark Taylor',
    'northstar': 'Northstar', 
    'northwood': 'Northwood Ravin', 
    'pb_bell': 'Bell',
    'pinnacle': 'Pinnacle',
    'post': 'Post Road',
    'rpm_living': 'RPM',
    'walton': 'Walton Communities', 
    'weidner': 'Weidner',
    'windsor': 'Windsor'
}

raw_survey_data = pd.read_csv('data/raw_survey_data.csv',encoding='latin1')\
    .rename(columns={'Market': 'market',
                     'Which of the following best describes your current living situation?':'living',
                     'What is your combined, annual household income?':'income',
                     'What is theÂ\xa0total monthly rent payment (for all bedrooms)Â\xa0where you live? The total rent forÂ\xa0all bedrooms, not just your portion of the rent.Â\xa0':'total_rent',
                     'What is your age?':'age',
                     'Cortland Unaided': 'cortland_unaided',
                     'Camden Unaided': 'camden_unaided',
                     'Greystar Unaided': 'greystar_unaided',
                     'MAA Unaided': 'maa_unaided'})

raw_survey_data['cortland_unaided'] = raw_survey_data['cortland_unaided'].notna().astype(int)
raw_survey_data['camden_unaided']   = raw_survey_data['camden_unaided'].notna().astype(int)
raw_survey_data['greystar_unaided'] = raw_survey_data['greystar_unaided'].notna().astype(int)
raw_survey_data['maa_unaided']      = raw_survey_data['maa_unaided'].notna().astype(int)

aided_cols = [col for col in raw_survey_data.columns if col.startswith('<strong>')]

for col in aided_cols:
    match = re.search(r'<strong>(.*?)</strong>', col)
    if match:
        brand = match.group(1).strip().lower().replace(' ', '_')
        new_col = f"{brand}_aided"
        raw_survey_data[new_col] = raw_survey_data[col].notna().astype(int)

survey_df = raw_survey_data[[
    col for col in raw_survey_data.columns
    if col in ['market', 'living', 'income', 'total_rent', 'age']
    or col.endswith('_aided') or col.endswith('_unaided')
]]

aided_cols = [col for col in raw_survey_data.columns if col.endswith('_aided')]

aided_cols = [col for col in raw_survey_data.columns if col.endswith('_aided')]

melted_aided = survey_df[['market'] + aided_cols].melt(
    id_vars='market',
    value_vars=aided_cols,
    var_name='manager',
    value_name='recognized'
)
melted_aided['manager'] = melted_aided['manager'].str.replace('_aided', '', regex=False)

aided_grouped = (
    melted_aided.groupby(['market', 'manager'])
    .agg(
        aided_recognition=('recognized', 'mean'),
        count=('recognized', 'count')
    )
    .reset_index()
)

unaided_cols = [col for col in raw_survey_data.columns if col.endswith('_unaided')]

melted_unaided = survey_df[['market'] + unaided_cols].melt(
    id_vars='market',
    value_vars=unaided_cols,
    var_name='manager',
    value_name='recognized'
)
melted_unaided['manager'] = melted_unaided['manager'].str.replace('_unaided', '', regex=False)

unaided_recognition = (
    melted_unaided.groupby(['market', 'manager'], as_index=False)['recognized']
    .mean()
    .rename(columns={'recognized': 'unaided_recognition'})
)

# Final merge
recognition_df = pd.merge(
    aided_grouped,
    unaided_recognition,
    on=['market', 'manager'],
    how='outer'
)

recognition_df['market'] = recognition_df['market'].map(market_map)
recognition_df['manager'] = recognition_df['manager'].map(manager_map)

# only markets with 50+ properties
counts   = df['MarketName'].value_counts()
eligible_markets = counts[counts >= 50].index.tolist()
markets = ['All'] + sorted(eligible_markets)

# Sidebar controls
st.sidebar.title("Controls")

# default index for Atlanta, GA (fall back to 0 if not present)
try:
    atl_i = markets.index("Atlanta, GA")
except ValueError:
    atl_i = 0

market = st.sidebar.selectbox("Market", markets, index=atl_i)

# Market filter and map center/zoom
if market == "All":
    center_lat, center_lon, zoom = 39.8, -98.6, 4
else:
    df = df[df['MarketName'] == market]
    center_lat = df['Latitude'].mean()
    center_lon = df['Longitude'].mean()
    zoom = 10

    rank_to_radius = {1: 30, 2: 20, 3: 15}

    hotspots = top_tiles[top_tiles['MarketName'] == market]

    # Rename columns
    hotspots = hotspots.rename(columns={
        'lat_bin': 'Latitude',
        'lon_bin': 'Longitude',
        'total_units': '# Units',
        'total_assets': '# Assets'
    })

    hotspots['Center Rank'] = (
        hotspots.groupby('MarketName')['# Units']
        .rank(method='first', ascending=False)
        .astype(int)
    )


    # Create popup text
    hotspots[''] = (
        'City Center #' + hotspots['Center Rank'].astype(str) + '<br>' +
        'Lat: ' + hotspots['Latitude'].astype(str) + '<br>' +
        'Lon: ' + hotspots['Longitude'].astype(str) + '<br>' +
        '# Units: ' + hotspots['# Units'].astype(str) + '<br>' +
        '# Assets: ' + hotspots['# Assets'].astype(str)
    )

submarkets = df['SubMarketName'].dropna().unique()
submarkets = ['All'] + sorted(submarkets)

submarket_selection = st.sidebar.multiselect("Submarket", submarkets, default=['All'])

# If "All" is selected or nothing is selected, show all
if 'All' not in submarket_selection:
    df = df[df['SubMarketName'].isin(submarket_selection)]

# Only managers with 5+ props in that (filtered) market
counts   = df['manager'].value_counts()
eligible = counts[counts >= 5].index.tolist()
managers = ['All'] + sorted(eligible)

# default index for Cortland (fall back to 0)
try:
    cort_i = managers.index("Cortland")
except ValueError:
    cort_i = 0

manager = st.sidebar.selectbox("Management", managers, index=cort_i)

if manager != "All":
    df = df[df['manager'] == manager]

    total_assets = len(df)
    branded_assets = len(df[df['branded'] == True])

    total_units = df['UnitCount'].sum()
    branded_units = df.loc[df['branded'] == True, 'UnitCount'].sum()

    if market != 'All':
        match = recognition_df[
            (recognition_df['manager'] == manager) & 
            (recognition_df['market'] == market)
        ]

        if not match.empty:
            recognition_row = match.iloc[0]
            st.markdown(f"""
                ### Brand Recognition — {recognition_row['manager']} - {recognition_row['market']}

                - **Aided Recognition**: {recognition_row['aided_recognition']:.2%}  
                - **Unaided Recognition**: {recognition_row['unaided_recognition']:.2%}  
                - **Total Assets**: {total_assets} ({branded_assets} branded)
                - **Total Units**: {round(total_units)} ({round(branded_units)} branded)
            """)
        else:
            st.markdown(f"""
                ### Brand Recognition — {manager} - {market}

                - No survey recognition data available  
                - **Total Assets**: {total_assets} ({branded_assets} branded)
            """)

    else:
        manager_rows = recognition_df[recognition_df['manager'] == manager]

        if not manager_rows.empty:
            total_count = manager_rows['count'].sum()
            weighted_aided = (manager_rows['aided_recognition'] * manager_rows['count']).sum() / total_count
            weighted_unaided = (manager_rows['unaided_recognition'] * manager_rows['count']).sum() / total_count

            st.markdown(f"""
                ### Brand Recognition — {manager} (National)

                - **Aided Recognition**: {weighted_aided:.2%}  
                - **Unaided Recognition**: {weighted_unaided:.2%}  
                - **Total Assets**: {total_assets} ({branded_assets} branded)
            """)
        else:
            st.markdown(f"""
                ### Brand Recognition — {manager} (National)

                - No survey recognition data available  
                - **Total Assets**: {total_assets} ({branded_assets} branded)
            """)

st.sidebar.markdown("---")
st.sidebar.subheader("Heatmap Settings")

heatmap_radius = st.sidebar.slider("Radius", min_value=5, max_value=50, value=15, step=1)
heatmap_blur = st.sidebar.slider("Blur", min_value=1, max_value=30, value=15, step=1)

df['value'] = 1
branded_df = df[df['branded'] == True]
unbranded_df = df[df['branded'] != True]

# Create map
m = leafmap.Map(center=[center_lat, center_lon], zoom=zoom)

if not branded_df.empty:
    m.add_heatmap(
        data=branded_df,
        latitude="Latitude",
        longitude="Longitude",
        value="value",
        name="Branded Heatmap",
        radius=heatmap_radius,
        blur=heatmap_blur,
        gradient={0.2: 'cyan', 0.4: 'blue', 0.6: 'navy', 1: 'black'},
    )

if not unbranded_df.empty:
    m.add_heatmap(
        data=unbranded_df,
        latitude="Latitude",
        longitude="Longitude",
        value="value",
        name="Unbranded Heatmap",
        radius=heatmap_radius,
        blur=heatmap_blur,
        gradient={0.2: 'hotpink', 0.5: 'pink', 0.7: 'deeppink', 1.0: 'darkred'},
    )

m.add_points_from_xy(
    data=df,
    x='Longitude',
    y='Latitude',
    popup=['property', 'manager', 'owner'],
    layer_name='Properties',
    show=False
)

if market != 'All':

    # Create square polygons
    half_bin_size = 0.005
    geometries = []
    popups = []

    for _, row in hotspots.iterrows():
        lat, lon = row['Latitude'], row['Longitude']
        rank = row['Center Rank']

        square = Polygon([
            (lon - half_bin_size, lat - half_bin_size),
            (lon + half_bin_size, lat - half_bin_size),
            (lon + half_bin_size, lat + half_bin_size),
            (lon - half_bin_size, lat + half_bin_size),
            (lon - half_bin_size, lat - half_bin_size)
        ])
        geometries.append(square)

        popups.append(
            f"City Center #{rank}<br>"
            f"Market: {row['MarketName']}<br>"
            f"Lat: {lat}<br>"
            f"Lon: {lon}<br>"
            f"# Units: {row['# Units']}<br>"
            f"# Assets: {row['# Assets']}"
        )

    gdf = gpd.GeoDataFrame({
        '': popups,
        'geometry': geometries
    })

    m.add_gdf(gdf, layer_name='City Centers', info_mode='on_click', fill_color='black', fill_opacity=0.5, show=False)

m.to_streamlit(height=700)

st.markdown("""
**Heatmap Legend:**
- 🔵 **Blue** = Branded properties
- 🔴 **Red** = Unbranded properties
""")