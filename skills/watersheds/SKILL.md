---
name: watersheds
description: Use this skill for the requests related to the watersheds in USA; it provides a way to get watersheds as a GeoDataframe in GeoPandas
---

# Watersheds Skill

## Description

This skill gets the geometries and other attributes of watersheds by accessing the ArcGIS Feature Service at the following URL:      

    https://services.arcgis.com/P3ePLMYs2RVChkJx/ArcGIS/rest/services/Watershed_Boundary_Dataset_HUC_10s/FeatureServer/0

It returns the following columns:


objectid: System-assigned unique identifier for each watershed feature in the service.
areaacres: Total area of the watershed measured in acres.
areasqkm: Total area of the watershed measured in square kilometers.
states: U.S. states that the watershed intersects or lies within. For example, "IN,KY,OH", i.e., a concatenation of state abbreviations
huc10: Ten-digit Hydrologic Unit Code identifying the watershed.
name: Official or commonly used name of the watershed.
globalid: Globally unique identifier used to track the feature across databases and services.
Shape__Area: System-calculated area of the watershed geometry in the feature service’s coordinate system.
Shape__Length: System-calculated perimeter length of the watershed geometry in the feature service’s coordinate system.

## When to Use

- Find a watershe by a name
- Find objects in a watershed  
- Find watersheds with some spatial conditions   

## How to Use

### Step 1: Construct a condition   

Using the condition "LOWER(name) = 'headwaters black fork mohican river'" for finding the watershed Headwaters Black Fork Mohican River 

Use the following way to make a request:                                                                                                                                                                                                                                                         
```                                     
import geopandas as gpd                                                                                                                                 
def get_features(self_url, where, bbox=None):

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
        "resultRecordCount": 1000  # Increase this if needed 
    }                                                                                                                                                   
    response = requests.get(self_url + "/query", params=params)   
    data = response.json()                    
    if data['features']:                      
        return gpd.GeoDataFrame.from_features(data['features'])  
    else:                                               
        return gpd.GeoDataFrame(columns=['geometry'])                                                                                                               
url = "https://services.arcgis.com/P3ePLMYs2RVChkJx/ArcGIS/rest/services/Watershed_Boundary_Dataset_HUC_10s/FeatureServer/0"
where = f"LOWER(name) = 'headwaters black fork mohican river'"    
load_features(self_url, where)                                                                                                                          
                                                                                                                                                        
```                     
