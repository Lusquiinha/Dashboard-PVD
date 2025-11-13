import geopandas as gpd

# 1. Load your current parquet file
print("Loading file...")
gdf = gpd.read_parquet("yearly_deforestation.parquet")

# 2. Simplify geometries
# 'tolerance' is in the units of your CRS.
# If using degrees (EPSG:4326), try 0.0001 or 0.001.
# If using meters (UTM), try 10 or 50.
print("Simplifying geometries...")
gdf['geometry'] = gdf.geometry.simplify(tolerance=0.001, preserve_topology=True)

# 3. Keep only necessary columns
# Drop columns you don't use in the dashboard to save RAM
cols_to_keep = ['year', 'area_km', 'state', 'satellite', 'path_row', 'geometry'] # <--- CHANGE THESE to what you actually use
gdf = gdf[cols_to_keep]

# 4. Save as a new optimized file
print("Saving optimized file...")
gdf.to_parquet("yearly_deforestation_light.parquet")
print("Done!")