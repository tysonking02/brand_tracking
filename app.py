import streamlit as st
import pandas as pd
import leafmap.foliumap as leafmap
from folium.plugins import HeatMap
import re
from shapely.geometry import Polygon
import geopandas as gpd
import unicodedata
import matplotlib.colors as mcolors


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

manager_logo_map = {
    'AMLI': 'https://media.licdn.com/dms/image/v2/C560BAQGnxhMQWfLpjA/company-logo_200_200/company-logo_200_200/0/1630613538782/amli_residential_logo?e=2147483647&v=beta&t=V-mBBUgDZ6KajQ6XKjkbSpIqh382Wb2hN6_8BkMnUM0',
    'AvalonBay': 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTSjZB_WdcnA6UHxoTZh9e7ewgMARfPHRdsGg&s',
    'Bell': 'https://media.glassdoor.com/sqll/2590407/bell-management-squarelogo-1644392295469.png',
    'Camden': 'https://www.camdenliving.com/images/camden-logo-black.png',
    'Cortland': 'https://www.multifamilyexecutive.com/wp-content/uploads/sites/3/2018/cortland-logo-stacked-rgb.png?w=1024',
    'FPA': 'https://images1.apartments.com/i2/6yzvf1jIv9iWltohdLCwGaBOliNpGgXLLH7jE3BUH5Y/110/image.png',
    'Fairfield': 'https://images1.apartments.com/i2/AejWy_Wu0361EimbUJCaiGPRRQ5TwLcgkECUYjSupZo/110/image.jpg',
    'GID': 'https://media.licdn.com/dms/image/v2/D560BAQFec0alUyaRAQ/company-logo_200_200/B56ZZfFBgeGcAM-/0/1745351876017/windsorm_logo?e=2147483647&v=beta&t=Pv905gG85FrKuZrGBKgY4P135mWvkgnXiUQYgZ6w7fs',
    'Greystar': 'https://mma.prnewswire.com/media/1761396/greystar_Logo.jpg?p=facebook',
    'MAA': 'https://cdn.cookielaw.org/logos/7d7d223a-000d-4093-b8e4-356348d54408/018fdf5b-7162-738e-a17d-542945beefb7/9f203eab-91c5-4baf-8b5b-c4592cd027e3/MAA_logo_with_R.png',
    'Mill Creek': 'https://mma.prnewswire.com/media/224987/mill_creek_logo.jpg?p=facebook'
}

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

df = df[df['manager'].isin([
    'Fairfield', 'Bell', 'Mill Creek', 'GID', 'FPA', 'AMLI', 
    'Greystar', 'Camden', 'Cortland', 'AvalonBay', 'MAA'
])]

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
    'avalon': 'AvalonBay',
    'camden': 'Camden',
    'cortland': 'Cortland',
    'greystar': 'Greystar',
    'maa': 'MAA',
    'pb_bell': 'Bell',
    'windsor': 'GID'
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

# Only managers with 5+ props in that (filtered) market
counts   = df['manager'].value_counts()
eligible = counts[counts >= 5].index.tolist()
managers = sorted(eligible)

manager_select = st.sidebar.multiselect("Management", managers, default=['Cortland'])

import pandas as pd

data = []

for mgr in manager_select:
    filtered_df = df[df['manager'] == mgr]
    total_assets = len(filtered_df)
    branded_assets = len(filtered_df[filtered_df['branded'] == True])
    total_units = filtered_df['UnitCount'].sum()
    branded_units = filtered_df.loc[filtered_df['branded'] == True, 'UnitCount'].sum()

    if market != 'All':
        match = recognition_df[
            (recognition_df['manager'] == mgr) & (recognition_df['market'] == market)
        ]

        if not match.empty:
            recognition_row = match.iloc[0]
            aided = f"{recognition_row['aided_recognition']:.2%}"
            unaided = f"{recognition_row['unaided_recognition']:.2%}"
        else:
            aided = 'N/A'
            unaided = 'N/A'

        market_label = market
    else:
        manager_rows = recognition_df[recognition_df['manager'] == mgr]

        if not manager_rows.empty:
            total_count = manager_rows['count'].sum()
            aided_val = (manager_rows['aided_recognition'] * manager_rows['count']).sum() / total_count
            unaided_val = (manager_rows['unaided_recognition'] * manager_rows['count']).sum() / total_count
            aided = f"{aided_val:.2%}"
            unaided = f"{unaided_val:.2%}"
        else:
            aided = 'N/A'
            unaided = 'N/A'

        market_label = 'National'

    logo_url = manager_logo_map.get(mgr, "")
    logo_html = f'<div style="text-align:center;"><img src="{logo_url}" width="100"/></div>' if logo_url else ''

    data.append({
        'Logo': logo_html,
        'Manager': mgr,
        'Market': market_label,
        'Aided Recognition': aided,
        'Unaided Recognition': unaided,
        'Total Assets': f"{total_assets:,}",
        'Branded Assets': f"{branded_assets:,}",
        'Total Units': f"{round(total_units):,}",
        'Branded Units': f"{round(branded_units):,}"
    })

df_display = pd.DataFrame(data)
st.subheader('Brand Recognition')

html_table = df_display.to_html(escape=False, index=False)

html_table = html_table.replace(
    "<thead>",
    "<thead><style>th { text-align: center !important; }</style>",
)

st.markdown(html_table, unsafe_allow_html=True)


st.sidebar.markdown("---")
st.sidebar.subheader("Heatmap Settings")

heatmap_radius = st.sidebar.slider("Radius", min_value=5, max_value=50, value=15, step=1)
heatmap_blur = st.sidebar.slider("Blur", min_value=1, max_value=30, value=15, step=1)

df['value'] = 1
branded_df = df[df['branded'] == True]
unbranded_df = df[df['branded'] != True]

manager_color_map = {
    'AMLI': '#80a1d4',
    'AvalonBay': '#4a2e89',
    'Bell': '#31999b',
    'Camden': '#84be30',
    'Cortland': '#284692',
    'FPA': '#f59128',
    'Fairfield': '#a7632d',
    'GID': '#222707',
    'Greystar': '#102045',
    'MAA': '#e6752e',
    'Mill Creek': '#7aaeb6'
}

def create_gradient(base_hex):
    base_rgb = mcolors.to_rgb(base_hex)
    gradient = {
        0.2: mcolors.to_hex([min(1, c + 0.4) for c in base_rgb]),
        0.5: mcolors.to_hex([min(1, c + 0.2) for c in base_rgb]),
        0.8: base_hex,
        1.0: mcolors.to_hex([max(0, c - 0.2) for c in base_rgb])
    }
    return gradient

# Create map
m = leafmap.Map(center=[center_lat, center_lon], zoom=zoom)

for manager in manager_select:
    manager_df = df[df['manager'] == manager]
    base_color = manager_color_map.get(manager, '#888888')
    gradient = create_gradient(base_color)

    m.add_heatmap(
        data=manager_df,
        latitude="Latitude",
        longitude="Longitude",
        value="value",
        name=f"{manager} Heatmap",
        radius=heatmap_radius,
        blur=heatmap_blur,
        gradient=gradient
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

st.subheader("Heatmap Legend")

for manager in manager_select:
    if manager in manager_color_map:
        color = manager_color_map[manager]
        st.markdown(
            f'<div style="display:flex;align-items:center;margin-bottom:4px;">'
            f'<div style="width:16px;height:16px;background-color:{color};border-radius:3px;margin-right:8px;"></div>'
            f'<span style="font-weight:500;">{manager}</span>'
            f'</div>',
            unsafe_allow_html=True
        )
