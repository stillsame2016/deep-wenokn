---
name: hydrology-basins
description: Use this skill for the requests related to the hydrology basins in USA; it provides a way to get hydrology basinss as a GeoDataframe in GeoPandas
---

# Hydrology-Basins Skill

## Description

This skill gets the geometries and other attributes of hyfrology basins by accessing the ArcGIS Feature Service at the following URL:      

    https://services.arcgis.com/P3ePLMYs2RVChkJx/ArcGIS/rest/services/Watershed_Boundary_Dataset_HUC_6s/FeatureServer/0

It returns the following columns:

objectid: A system-generated unique identifier for each basin feature.
areaacres: The area of the basin measured in acres.
areasqkm: The area of the basin measured in square kilometers.
states: The U.S. states that the basin overlaps or is located within. For example, "IN,KY,OH", i.e., a concatenation of state abbreviations
huc6: The 6-digit Hydrologic Unit Code identifying the basin at the subregion level.
name: The official or commonly used name of the hydrologic basin.
globalid: A globally unique identifier used to track the feature across systems.
Shape__Area: The area of the basin geometry calculated by the GIS system.
Shape__Length: The perimeter length of the basin geometry calculated by the GIS system.

## When to Use

- Find a basin by a name
- Find objects in a basin  
- Find basins with some spatial conditions   

## How to Use

### Step 1: Construct a condition   

Using the condition "LOWER(name) = 'lower ohio-salt'" for finding the basin Lower Ohio-Salt 

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
url = "https://services.arcgis.com/P3ePLMYs2RVChkJx/ArcGIS/rest/services/Watershed_Boundary_Dataset_HUC_6s/FeatureServer/0"
where = f"LOWER(name) = 'lower ohio-salt'"    
load_features(self_url, where)                                                             
```        
