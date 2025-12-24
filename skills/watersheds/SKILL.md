---
name: watersheds
description: Use this skill for requests to retrieve watersheds in the USA as a GeoDataFrame in GeoPandas. This skill can retrieve all watersheds intersecting with specific states directly using the states column.
---

# Watersheds Skill

## Description

This skill retrieves geometries and attributes of watersheds by accessing the ArcGIS Feature Service at the following URL:

```
https://services.arcgis.com/P3ePLMYs2RVChkJx/ArcGIS/rest/services/Watershed_Boundary_Dataset_HUC_10s/FeatureServer/0
```

The service returns the following columns:

- **objectid**: System-assigned unique identifier for each watershed feature in the service
- **areaacres**: Total area of the watershed measured in acres
- **areasqkm**: Total area of the watershed measured in square kilometers
- **states**: U.S. states that the watershed intersects or lies within (e.g., "IN,KY,OH" - a concatenation of state abbreviations)
- **huc10**: Ten-digit Hydrologic Unit Code identifying the watershed
- **name**: Official or commonly used name of the watershed
- **globalid**: Globally unique identifier used to track the feature across databases and services
- **Shape__Area**: System-calculated area of the watershed geometry in the feature service's coordinate system
- **Shape__Length**: System-calculated perimeter length of the watershed geometry in the feature service's coordinate system

## When to Use

Use this skill to:

- Find a watershed by name
- Find objects within a watershed
- Find watersheds that meet specific spatial conditions (e.g., intersecting a state or region)
- Query watersheds by their attributes (HUC10 code, area, states, etc.)

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
    Query the ArcGIS Feature Service for watersheds.
    
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
        GeoDataFrame containing the queried watershed features
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

#### Example 1: Find a Watershed by Name

```python
url = "https://services.arcgis.com/P3ePLMYs2RVChkJx/ArcGIS/rest/services/Watershed_Boundary_Dataset_HUC_10s/FeatureServer/0"

# Query for "Headwaters Black Fork Mohican River" watershed
where = "LOWER(name) = 'headwaters black fork mohican river'"
watersheds_gdf = get_features(url, where)
```

#### Example 2: Find All Watersheds That Intersect Ohio State

This example demonstrates to find watersheds in Ohio. The `states` column contains comma-separated state abbreviations (e.g., "IN,KY,OH"). Use SQL `LIKE` to filter:

```python
# Query for watersheds that include Ohio in their states field
where = "states LIKE '%OH%'"
ohio_watersheds = get_features(url, where)
```

#### Example 3: Find Watersheds by Partial Name Match

```python
# Find all watersheds with "Black Fork" in the name
where = "name LIKE '%Black Fork%'"
watersheds = get_features(url, where)
```

## Notes

Fetching all watersheds in a state may take about one minute.

### Understanding the bbox Parameter

The **bbox (bounding box) parameter** is essential for efficient spatial queries:

- **Format**: `[minx, miny, maxx, maxy]` in WGS84 coordinates (longitude, latitude)
- **Purpose**: Limits the geographic extent of the query, reducing response time and data volume
- **Default**: If not provided, defaults to continental USA bounds
- **Use case**: Always provide a bbox when querying for features in a specific region (like a state, county, or watershed)

**Why bbox matters**: Without a bbox, the service may return all features matching the WHERE clause across the entire USA, which is inefficient. The bbox acts as a spatial pre-filter, dramatically improving query performance.

### Using the states Column

The `states` column is a powerful tool for querying watersheds by location:

- **Format**: Contains comma-separated state abbreviations (e.g., "IN,KY,OH")
- **Query pattern**: Use `states LIKE '%XX%'` where XX is the state abbreviation
  - Example: `"states LIKE '%OH%'"` for Ohio
  - Example: `"states LIKE '%CA%'"` for California
- **Multiple states**: Use AND to find watersheds in multiple states
  - Example: `"states LIKE '%KY%' AND states LIKE '%OH%'"`
- **Advantage**: Direct attribute filtering is faster than complex spatial operations

### WHERE Clause Tips

- Use `LOWER(field)` for case-insensitive string matching on text fields
- **For the states column**: Use `LIKE '%XX%'` where XX is the state abbreviation (e.g., `"states LIKE '%OH%'"` for Ohio)
  - The states column contains comma-separated abbreviations like "IN,KY,OH"
  - `LIKE '%OH%'` will match any watershed where OH appears in the states list
  - For multiple states: `"states LIKE '%KY%' AND states LIKE '%OH%'"` finds watersheds in both states
- Use `LIKE` with `%` wildcards for other partial matches
- Use `1=1` to match all features when relying solely on spatial filtering (bbox)
- Combine multiple conditions with `AND` / `OR`
- Always enclose string values in single quotes
