---
name: hydrology-basins
description: Use this skill for requests to retrieve hydrology basins in the USA as a GeoDataFrame in GeoPandas. Note that this skill is able to fetch all basins intersecting some states directly.
---

# Hydrology-Basins Skill

## Description

This skill retrieves geometries and attributes of hydrology basins by accessing the ArcGIS Feature Service at the following URL:

https://services.arcgis.com/P3ePLMYs2RVChkJx/ArcGIS/rest/services/Watershed_Boundary_Dataset_HUC_6s/FeatureServer/0

The service returns the following columns:
- **objectid**: A system-generated unique identifier for each basin feature
- **areaacres**: The area of the basin measured in acres
- **areasqkm**: The area of the basin measured in square kilometers
- **states**: The U.S. states that the basin overlaps or is located within (e.g., "IN,KY,OH" - a concatenation of state abbreviations)
- **huc6**: The 6-digit Hydrologic Unit Code identifying the basin at the subregion level
- **name**: The official or commonly used name of the hydrologic basin
- **globalid**: A globally unique identifier used to track the feature across systems
- **Shape__Area**: The area of the basin geometry calculated by the GIS system
- **Shape__Length**: The perimeter length of the basin geometry calculated by the GIS system

## When to Use

Use this skill to:
- Find a basin by name
- Find objects within a basin
- Find basins that meet specific spatial conditions (e.g., intersecting a state or region)
- Query basins by their attributes (HUC6 code, area, states, etc.)

## How to Use

### Step 1: Import Required Libraries

```python
import geopandas as gpd
import requests
```

### Step 2: Define the Query Function

Use the `get_features` function to query the feature service. The **bbox parameter** is crucial for spatial filtering - it defines a bounding box to limit results to a specific geographic area.

```python
def get_features(service_url, where, bbox=None):
    """
    Query the ArcGIS Feature Service for hydrology basins.
    
    Parameters:
    -----------
    service_url : str
        The URL of the ArcGIS Feature Service
    where : str
        SQL-like WHERE clause to filter features
    bbox : list or tuple, optional
        Bounding box as [minx, miny, maxx, maxy] in WGS84 (EPSG:4326)
        Default is the continental USA bounds
    
    Returns:
    --------
    geopandas.GeoDataFrame
        GeoDataFrame containing the queried basin features
    """
    
    # Default to continental USA bounds if no bbox provided
    if bbox is None:
        bbox = [-125.0, 24.396308, -66.93457, 49.384358]
    
    minx, miny, maxx, maxy = bbox
    
    params = {
        "where": where,
        "geometry": f"{minx},{miny},{maxx},{maxy}",
        "geometryType": "esriGeometryEnvelope",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "true",
        "f": "geojson",
        "outSR": "4326",  # Ensure output is in WGS84
        "resultOffset": 0,
        "resultRecordCount": 1000  # Increase if expecting more results
    }
    
    response = requests.get(service_url + "/query", params=params)
    data = response.json()
    
    if data.get('features'):
        return gpd.GeoDataFrame.from_features(data['features'], crs="EPSG:4326")
    else:
        return gpd.GeoDataFrame(columns=['geometry'], crs="EPSG:4326")
```

### Step 3: Query Examples

#### Example 1: Find a Basin by Name

```python
url = "https://services.arcgis.com/P3ePLMYs2RVChkJx/ArcGIS/rest/services/Watershed_Boundary_Dataset_HUC_6s/FeatureServer/0"

# Query for "Lower Ohio-Salt" basin
where = "LOWER(name) = 'lower ohio-salt'"
basins_gdf = get_features(url, where)

print(f"Found {len(basins_gdf)} basin(s)")
print(basins_gdf[['name', 'huc6', 'states', 'areasqkm']])
```

#### Example 2: Find All Basins That Intersect Ohio State

This example demonstrates to find basins in Ohio.

The `states` column contains comma-separated state abbreviations (e.g., "IN,KY,OH"). Use SQL `LIKE` to filter:

```python
# Query for basins that include Ohio in their states field
where = "states LIKE '%OH%'"
ohio_basins = get_features(url, where)

print(f"Found {len(ohio_basins)} basin(s) that intersect Ohio")
print(ohio_basins[['name', 'huc6', 'states', 'areasqkm']])
```

## Notes

### Understanding the bbox Parameter

The **bbox (bounding box) parameter** is essential for efficient spatial queries:

- **Format**: `[minx, miny, maxx, maxy]` in WGS84 coordinates (longitude, latitude)
- **Purpose**: Limits the geographic extent of the query, reducing response time and data volume
- **Default**: If not provided, defaults to continental USA bounds
- **Use case**: Always provide a bbox when querying for features in a specific region (like a state, county, or watershed)

**Why bbox matters**: Without a bbox, the service may return all features matching the WHERE clause across the entire USA, which is inefficient. The bbox acts as a spatial pre-filter, dramatically improving query performance.

