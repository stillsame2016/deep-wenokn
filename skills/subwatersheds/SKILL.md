---
name: subwatersheds
description: Use this skill for requests to retrieve subwatersheds in the USA as a GeoDataFrame in GeoPandas. This skill can retrieve all subwatersheds intersecting with specific states directly using the states column.
---

# subwatersheds Skill

## Description

This skill retrieves geometries and attributes of subwatersheds by accessing the ArcGIS Feature Service at the following URL:

```
https://services.arcgis.com/P3ePLMYs2RVChkJx/ArcGIS/rest/services/Watershed_Boundary_Dataset_HUC_12s/FeatureServer/0
```

The service returns the following columns:

- **objectid**: Unique system-generated identifier for each subwatershed feature.
- **areaacres**: Total subwatershed area in acres.
- **areasqkm**: Total subwatershed area in square kilometers.
- **states**: U.S. state(s) in which the subwatershed is located.
- **huc12**: 12-digit Hydrologic Unit Code identifying the subwatershed.
- **name**: Official name of the subwatershed.
- **tohuc**: Downstream HUC that this subwatershed drains into.
- **noncontributingareaacres**: Area in acres that does not contribute surface runoff.
- **noncontributingareasqkm**: Area in square kilometers that does not contribute surface runoff.
- **globalid**: Globally unique identifier for the feature.
- **Shape__Area**: Geometry-derived area of the subwatershed.
- **Shape__Length**: Geometry-derived perimeter length of the subwatershed.

## When to Use

Use this skill to:

- Find a subwatershed by name
- Find objects within a subwatershed
- Find subwatersheds that meet specific spatial conditions (e.g., intersecting a county or region)
- Query subwatersheds by their attributes (huc12 code, area, states, etc.)
- Find all subwatersheds upstream of a river (See Example 4)

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
    Query the ArcGIS Feature Service for subwatersheds.
    
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
        GeoDataFrame containing the queried subwatershed features
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

#### Example 1: Find a subwatershed by Name

```python
url = "https://services.arcgis.com/P3ePLMYs2RVChkJx/ArcGIS/rest/services/subwatershed_Boundary_Dataset_HUC_10s/FeatureServer/0"

# Query for "Green Creek-Pocatalico River" subwatershed
where = "LOWER(name) = 'green creek-pocatalico river'"
subwatersheds_gdf = get_features(url, where)
```

#### Example 2: Find All subwatersheds That Intersect Ohio State

This example demonstrates to find subwatersheds in Ohio. The `states` column contains comma-separated state abbreviations (e.g., "IN,KY,OH"). Use SQL `LIKE` to filter:

```python
# Query for subwatersheds that include Ohio in their states field
where = "states LIKE '%OH%'"
ohio_subwatersheds = get_features(url, where)
```

This query needs more than one minute to complete.

#### Example 3: Find subwatersheds by Partial Name Match

```python
# Find all subwatersheds with "Black Fork" in the name
where = "name LIKE '%Black Fork%'"
subwatersheds = get_features(url, where)
```

#### Example 4: Find all subwatersheds upstream of the Muskingum River

Don't make any changes to the following code. Use it as it it.

```python
import utils as get_upstream_subwatersheds
upstream_subwatersheds = get_upstream_subwatersheds(muskingum_river_gdf)
```

## Notes

Fetching all subwatersheds in a state may take about one minute.

### Understanding the bbox Parameter

The **bbox (bounding box) parameter** is essential for efficient spatial queries:

- **Format**: `[minx, miny, maxx, maxy]` in WGS84 coordinates (longitude, latitude)
- **Purpose**: Limits the geographic extent of the query, reducing response time and data volume
- **Default**: If not provided, defaults to continental USA bounds
- **Use case**: Always provide a bbox when querying for features in a specific region (like a state, county, or subwatershed)

**Why bbox matters**: Without a bbox, the service may return all features matching the WHERE clause across the entire USA, which is inefficient. The bbox acts as a spatial pre-filter, dramatically improving query performance.

### Using the states Column

The `states` column is a powerful tool for querying subwatersheds by location:

- **Format**: Contains comma-separated state abbreviations (e.g., "IN,KY,OH")
- **Query pattern**: Use `states LIKE '%XX%'` where XX is the state abbreviation
  - Example: `"states LIKE '%OH%'"` for Ohio
  - Example: `"states LIKE '%CA%'"` for California
- **Multiple states**: Use AND to find subwatersheds in multiple states
  - Example: `"states LIKE '%KY%' AND states LIKE '%OH%'"`
- **Advantage**: Direct attribute filtering is faster than complex spatial operations

### WHERE Clause Tips

- Use `LOWER(field)` for case-insensitive string matching on text fields
- **For the states column**: Use `LIKE '%XX%'` where XX is the state abbreviation (e.g., `"states LIKE '%OH%'"` for Ohio)
  - The states column contains comma-separated abbreviations like "IN,KY,OH"
  - `LIKE '%OH%'` will match any subwatershed where OH appears in the states list
  - For multiple states: `"states LIKE '%KY%' AND states LIKE '%OH%'"` finds subwatersheds in both states
- Use `LIKE` with `%` wildcards for other partial matches
- Use `1=1` to match all features when relying solely on spatial filtering (bbox)
- Combine multiple conditions with `AND` / `OR`
- Always enclose string values in single quotes
