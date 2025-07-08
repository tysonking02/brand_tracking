import geopandas as gpd
import pandas as pd
from shapely.ops import unary_union

# 1. Load your Georgia tract shapefile
tracts = gpd.read_file("data/shapefiles/georgia_tract/tl_2024_13_tract.shp")\
           .to_crs("EPSG:4326")  # make sure it's WGS84

# 2. Load your property CSV as a GeoDataFrame
df = pd.read_csv("data/branded_sites.csv")
props = gpd.GeoDataFrame(
    df,
    geometry=gpd.points_from_xy(df.Longitude, df.Latitude),
    crs="EPSG:4326"
)

# 3. Spatial‐join: tag each property with the GEOID of its containing tract
props = props.sjoin(
    tracts[["GEOID","geometry"]],
    how="left",
    predicate="within"
).drop(columns=["index_right"])

# 4. Get the tract geometries for each property
tract_props = props.merge(
    tracts[["GEOID","geometry"]],
    on="GEOID",
    how="left",
    suffixes=("_point","_tract")
)

# Set the geometry to the tract geometry for dissolving
tract_props = tract_props.set_geometry("geometry_tract")

# 5. Dissolve by your marketing SubMarketName
submarkets = tract_props.dissolve(
    by="SubMarketName",
    aggfunc="first"   # keep one representative record's attributes
).reset_index()

# 6. Clean up and export to GeoJSON
submarkets = submarkets[["SubMarketName", "geometry_tract"]]
# Rename the geometry column to the standard name
submarkets = submarkets.rename(columns={"geometry_tract": "geometry"})
submarkets = submarkets.set_geometry("geometry")
submarkets.to_file("data/submarkets.geojson", driver="GeoJSON")