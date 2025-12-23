---
name: hydrology-basins
description: Use this skill for requests related to hydrology basins in the USA; it provides a way to get hydrology basins as a GeoDataframe in GeoPandas.
---

# Hydrology-Basins Skill

## Description

This skill retrieves the geometries and attributes of hydrology basins by accessing the ArcGIS Feature Service. It queries the Watershed Boundary Dataset (HUC 6) to return data as a GeoPandas GeoDataFrame.

**Data Source:**
https://services.arcgis.com/P3ePLMYs2RVChkJx/ArcGIS/rest/services/Watershed_Boundary_Dataset_HUC_6s/FeatureServer/0

### Output Columns
The skill returns the following columns:

| Column | Description |
| :--- | :--- |
| **objectid** | System-generated unique identifier for the basin. |
| **areaacres** | Area of the basin in acres. |
| **areasqkm** | Area of the basin in square kilometers. |
| **states** | Comma-separated list of U.S. states the basin overlaps (e.g., "IN,KY,OH"). |
| **huc6** | The 6-digit Hydrologic Unit Code identifying the basin. |
| **name** | The official name of the hydrologic basin. |
| **globalid** | Globally unique identifier. |
| **Shape__Area** | Area calculated by the GIS system. |
| **Shape__Length** | Perimeter length calculated by the GIS system. |

## When to Use

- Finding a specific basin by its name.
- Retrieving all basins that intersect a specific geographic area (Bounding Box).
- Finding basins based on spatial conditions relative to other objects.

## Parameters

1.  **`where`**: (String) A SQL-style where clause to filter by attributes (e.g., `name`, `states`). Default should be `"1=1"` if no attribute filter is needed.
2.  **`bbox`**: (List/Tuple) **Crucial for performance.** A spatial filter defined as `[minx, miny, maxx, maxy]`.
    -   If provided, the query only returns basins intersecting this box.
    -   If omitted, the script defaults to the entire United States, which may be slow.

## How to Use

### Code Example

```python
import requests
import geopandas as gpd

def get_features(url, where="1=1", bbox=None):
    """
    Query the Feature Service.
    
    Args:
        url (str): The ArcGIS FeatureServer URL.
        where (str): SQL filtering clause.
        bbox (list): [min_lon, min_lat, max_lon, max_lat]. 
                     Defaults to full US extent if None.
    """
    
    # 1. Define the Bounding Box
    # If bbox is explicitly provided, use it. 
    # Otherwise, default to the approximate extent of the US.
    if bbox is None:                        
        bbox = [-125.0, 24.396308, -66.93457, 49.384358]   
    
    minx, miny, maxx, maxy = bbox
           
    # 2. Construct Query Parameters
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
        "resultRecordCount": 1000 
    }                                         
    
    # 3. Fetch Data
    response = requests.get(url + "/query", params=params)
    
    # 4. Parse to GeoDataFrame
    try:
        data = response.json()          
        if data.get('features'):                      
            return gpd.GeoDataFrame.from_features(data['features'])  
        else:                                               
            return gpd.GeoDataFrame(columns=['geometry', 'name', 'huc6'])
    except Exception as e:
        print(f"Error fetching data: {e}")
        return gpd.GeoDataFrame()

# --- USAGE EXAMPLES ---

url = "[https://services.arcgis.com/P3ePLMYs2RVChkJx/ArcGIS/rest/services/Watershed_Boundary_Dataset_HUC_6s/FeatureServer/0](https://services.arcgis.com/P3ePLMYs2RVChkJx/ArcGIS/rest/services/Watershed_Boundary_Dataset_HUC_6s/FeatureServer/0)"

# Example 1: Query by Name (Attribute Filter)
where_clause = "LOWER(name) = 'lower ohio-salt'"    
gdf_by_name = get_features(url, where=where_clause)

# Example 2: Find all basins that intersect with Ohio state
# (Assuming 'gdf_ohio' is a GeoDataFrame containing the Ohio state boundary)

# Get the bounding box of Ohio (minx, miny, maxx, maxy)
# .total_bounds returns an array that fits the expected format
bbox_ohio = gdf_ohio.total_bounds

# Query the service using Ohio's bounding box
gdf_basins_ohio = get_features(url, where="1=1", bbox=bbox_ohio)
