import pandas as pd
import plotly.express as px


costar_export = pd.read_csv('data/costar_export.csv')
costar_export['PropertyManagerName'] = costar_export['PropertyManagerName'].str.split('-').str[0].str.strip()

managers = ['Greystar', 'MAA', 'Cortland']

city_map = {
    'Atlanta': {'lat': 33.7778, 'lon': -84.3909},
    'Dallas': {'lat': 32.7767, 'lon': -96.7970}
}


def create_map(manager, city=None):
    df = costar_export[costar_export["PropertyManagerName"] == manager]

    if df.empty:
        raise ValueError(f"No rows match management company: {manager}")

    # Set zoom and center
    if city and city in city_map:
        center_lat = city_map[city]['lat']
        center_lon = city_map[city]['lon']
        zoom = 15
    else:
        center_lat = 39.8
        center_lon = -98.6
        zoom = 3

    # Create density map
    fig = px.density_map(
        df,
        lat="Latitude",
        lon="Longitude",
        hover_name="PropertyName",
        radius=15,  # smoother heatmap
        zoom=zoom,
        center=dict(lat=center_lat, lon=center_lon),
        map_style="carto-positron",
        color_continuous_scale="Turbo",
        opacity=0.7
    )

    fig.update_layout(
        title=f"{city or 'U.S.'} Heat Map of {manager} Properties",
        margin=dict(l=0, r=0, t=40, b=0)
    )

    fig.write_image(f"figures/{manager}_{city or 'National'}_heatmap.png", width=1400, height=900, scale=2)
    print(f"Saved: {manager}_{city or 'National'}_heatmap.png")


for manager in managers:
    create_map(manager)
    # create_map(manager, city="Atlanta")
    # create_map(manager, city="Dallas")