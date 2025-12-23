---
name: power-plants
description: Use this skill for the requests related to the power plants in USA; it provides a way to get power plants as a GeoDataframe in GeoPandas
---

# power-plants Skill

## Description

This skill gets the geometries and other attributes of power plants in USA by accessing the ArcGIS Feature Service at the following URL:

    https://services2.arcgis.com/FiaPA4ga0iQKduv3/ArcGIS/rest/services/Power_Plants_in_the_US/FeatureServer/0

It returns the following columns:     

    FID — Feature ID (OID, primary key)
    OBJECTID — Object ID
    Plant_Code — EIA plant identification number
    Plant_Name — Power plant name
    Utility_ID — EIA utility identifier
    Utility_Na — Utility name (operations)
    sector_nam — Plant-level sector
    Street_Add — Street address
    City — City
    County — County
    State — State. State names must be FULL NAMES, not abbreviations! CORRECT: State='Ohio'. WRONG: State='OH'.
    Zip — Zip code
    PrimSource — Primary energy source
    source_des — Energy sources and summer capacities
    tech_desc — Generator technology / prime mover description
    Install_MW — Installed nameplate capacity (MW)
    Total_MW — Maximum output (MW)
    Bat_MW — Battery capacity (MW)
    Bio_MW — Biomass capacity (MW)
    Coal_MW — Coal capacity (MW)
    Geo_MW — Geothermal capacity (MW)
    Hydro_MW — Hydroelectric capacity (MW)
    HydroPS_MW — Pumped-storage hydro capacity (MW)
    NG_MW — Natural gas capacity (MW)
    Nuclear_MW — Nuclear capacity (MW)
    Crude_MW — Petroleum capacity (MW)
    Solar_MW — Solar capacity (MW)
    Wind_MW — Wind capacity (MW)
    Other_MW — Other/unspecified energy capacity (MW)
    Source — EIA data source reference
    Period — Reporting period (yyyymm)
    Longitude / Latitude — Plant location coordinates

## When to Use

- Find a power plant by a name 
- Find power plants in a region
- Find power plants with some spatial conditions
- Find a specific type of power plants in a region

### Step 1: Construct a condition

Using the condition "PrimSource='Solar'" for solar power plants.
Using the condition "PrimSource='Wind'" for wind power plants.
Using the condition "PrimSource='Biomass'" for renewable diesel fuel and other biofuel power plants.
Using the condition "PrimSource='Battery'" for battery storage power plants.
Using the condition "PrimSource='Geothermal'" for geothermal power plants.
Using the condition "PrimSource='Pumped storage'" for hydro pumped storage power plants.
Using the condition "PrimSource='Natural gas'" for natural gas power plants.
Using the condition "PrimSource='Nuclear'" for nuclear power plants.
Using the condition "PrimSource='Petroleum'" for petroleum power plants.
Using the condition "PrimSource='Solar'" for solar power plants.
Using the condition "PrimSource='Hydroelectric'" for hydroelectric power plants.

### Step 2: Figure out the bounding box of the querying region if possible

For example, to find all power plants within 1000 meters from a river, you can use the bounding box of the river.

### Step 3: Call the following function to get the GeoDataframe:

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

```

## Examples

### Example 1: Find nuclear power plants in California

Use the following code:

```
import geopandas as gpd
import requests

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
        "outSR": "4326",
        "resultOffset": 0,
        "resultRecordCount": 1000
    }

    response = requests.get(self_url + "/query", params=params)
    data = response.json()
    
    if data['features']:
        return gpd.GeoDataFrame.from_features(data['features'])
    else:
        return gpd.GeoDataFrame(columns=['geometry'])

# Get all nuclear power plants in California
url = "https://services2.arcgis.com/FiaPA4ga0iQKduv3/ArcGIS/rest/services/Power_Plants_in_the_US/FeatureServer/0"
where = f"PrimSource='Nuclear' AND State='California'"
california_nuclear_plants = get_features(url, where)
```

### Example 2: Find coal power plants in Ohio

```
import geopandas as gpd
import requests

def get_features(service_url, where_clause, bbox=None):
    """Query ArcGIS Feature Service and return GeoDataFrame"""
    if bbox is None:
        bbox = [-125.0, 24.396308, -66.93457, 49.384358]  # Continental US bounds
    
    minx, miny, maxx, maxy = bbox
    params = {
        "where": where_clause,
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
    
    response = requests.get(service_url + "/query", params=params)
    data = response.json()
    
    if data['features']:
        return gpd.GeoDataFrame.from_features(data['features'])
    else:
        return gpd.GeoDataFrame(columns=['geometry'])

# Find all coal power plants in Ohio
url = "https://services2.arcgis.com/FiaPA4ga0iQKduv3/ArcGIS/rest/services/Power_Plants_in_the_US/FeatureServer/0"
where = "PrimSource='Coal' AND State='Ohio'"
coal_plants_ohio = get_features(url, where)
```

## Notes:

For the power plants at risk of flooding, use the skill assets_at_flood_risk
Use the skill assets_at_flood_risk to find power plants at risk of flooding.
