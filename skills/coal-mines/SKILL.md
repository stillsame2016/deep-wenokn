---
name: coal-mines
description: Use this skill for the requests related to load coal mines in USA as GeoDataframe in GeoPandas
---

# coal-mines Skill

## Description

This skill gets the geometries and other attributes of coal mines in USA by accessing the ArcGIS Feature Service at the following URL:
    	   
https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/Surface_and_Underground_Coal_Mines_in_the_US/FeatureServer/0

It returns the following columns:

FID – Internal feature ID used by ArcGIS.
MSHA_ID – Mine’s official ID assigned by the Mine Safety and Health Administration.
MINE_NAME – Name of the coal mine.
MINE_TYPE – Type of mine (e.g., surface, underground).
MINE_STATE – State FIPS code for the mine’s location.
state – State name where the mine is located.
FIPS_COUNT – County FIPS code.
MINE_COUNT – County name.
PRODUCTION – Reported coal output for the mine.
PHYSICAL_U – Unit used for the production value (e.g., tons).
REFUSE – Indicates whether the site is a coal refuse or waste site.
Source – Data source or provider for this record.
PERIOD – Reporting period (usually the year).
Longitude – Mine longitude coordinate.
Latitude – Mine latitude coordinate.


## When to Use

- Find a coal mine by a name
- Find coal mines in a region
- Find coal mines with some spatial conditions

## How to Use

### Step 1: Construct a condition

### Step 2: Figure out the bounding box of the querying region

To find all coal mines in a county, you can find the bounding box of the county first.
To find all coal mines within 1000 meters from a river, you can find rge bounding box of the river first.

### Step 3: Use the following way to make a request:

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
    # st.code(response.url)
    # st.code(data)
    if data['features']:
        return gpd.GeoDataFrame.from_features(data['features'])
    else:
        return gpd.GeoDataFrame(columns=['geometry'])

url = "https://services2.arcgis.com/FiaPA4ga0iQKduv3/ArcGIS/rest/services/Power_Plants_in_the_US/FeatureServer/0"
where = f"PrimSource='Coal'"      # with other condition
load_features(self_url, where)

```

## Examples

### Example 1: Find a coal mine by a name
**User Request:** "Find the coal mine 'River View Mine' "
**Approach:**
Use the following condition:
   where = f"PrimSource='Coal' AND MINE_NAME='River View Mine'"

### Example 2: Find all coal mines in a state
**User Request:** "Find all coal mines in Ohio"
**Approach:**
Use the following condition: 
   where = f"PrimSource='Coal' AND state='Ohio'"   
   
