import geopandas as gpd

# Read your current file
gdf = gpd.read_file("yearly_deforestation.zip")

# Save as Parquet
gdf.to_parquet("yearly_deforestation.parquet")