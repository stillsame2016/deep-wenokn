---
name: census-blocks
description:  Use this skill for the requests related to USA census blocks; it provides a way to get blocks as a GeoDataframe in GeoPandas
---

# Census-Blocks Skill

## Description

This skill gets the geometries and other attributes of census blocks in USA by accessing the ArcGIS Feature Service at the following URL: 

    https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Tracts_Blocks/MapServer/2/query

It returns the following columns:

OID: Unique string identifier for the census block record.
STATE: Two-digit FIPS code identifying the U.S. state.
COUNTY: Three-digit FIPS code identifying the county within the state.
TRACT: Six-digit census tract code within the county.
BLKGRP: Census block group identifier within the tract.
BLOCK: Census block number identifying the smallest geographic unit.
SUFFIX: Suffix used to distinguish split or modified census blocks.
GEOID: Full geographic identifier combining state, county, tract, and block codes.
LWBLKTYP: Low-water block type indicator for coastal or water-related blocks.
UR: Urban–rural classification code for the census block.
AREAWATER: Total water area of the census block in square meters.
AREALAND: Total land area of the census block in square meters.
MTFCC: Census feature classification code describing the block type.
NAME: Full name of the census block.
BASENAME: Base name of the census block without qualifiers.
LSADC: Legal/statistical area description code.
FUNCSTAT: Functional status of the geographic entity.
CENTLON: Longitude of the geometric center of the census block.
CENTLAT: Latitude of the geometric center of the census block.
INTPTLON: Longitude of the internal point used for labeling and analysis.
INTPTLAT: Latitude of the internal point used for labeling and analysis.
STGEOMETRY: Polygon geometry representing the census block boundary.
HU100: Total number of housing units in the census block from the 2010 Census.
POP100: Total population count in the census block from the 2010 Census.
OBJECTID: System-generated unique identifier used by ArcGIS.

## When to Use

- Find a census block by FIPS
- For a location with the given latitude and longitude, find the census block contains the location
- Find census blocks with spatial relations 

## How to Use

### Example 1: Find a block by a latitude and a longitud

```
def load_census_block(latitude, longitude):

    url = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Tracts_Blocks/MapServer/2/query"
    params = {
        "f": "geojson",
        "geometry": f"{longitude},{latitude}",
        "geometryType": "esriGeometryPoint",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "true"
    }

    resp = requests.get(url, params=params)
    resp.raise_for_status()
    gdf = gpd.read_file(resp.text)
    if gdf.empty:
        raise ValueError("No census block found at the given location.")
    return gdf
```

### Example 2: Find all census blocks within 5 miles of a latitude and longitude

```
def load_nearby_census_blocks(lat, lon, radius_miles=5):

    # Convert miles to meters
    radius_m = radius_miles * 1609.34
    
    # Project WGS84 to an equal-area projection for buffering
    wgs84 = pyproj.CRS("EPSG:4326")
    aeqd = pyproj.CRS(proj="aeqd", lat_0=lat, lon_0=lon, datum="WGS84")
    project_to_aeqd = pyproj.Transformer.from_crs(wgs84, aeqd, always_xy=True).transform
    project_to_wgs84 = pyproj.Transformer.from_crs(aeqd, wgs84, always_xy=True).transform
    
    # Create buffer in meters around point and project back to WGS84
    point = Point(lon, lat)
    buffer = transform(project_to_aeqd, point).buffer(radius_m)
    buffer_wgs84 = transform(project_to_wgs84, buffer)

    # Convert geometry to ESRI JSON
    buffer_geojson = gpd.GeoSeries([buffer_wgs84]).__geo_interface__['features'][0]['geometry']

    esri_geometry = {
        "rings": buffer_geojson['coordinates'],
        "spatialReference": {"wkid": 4326}
    }

    # Query the FeatureServer
    url = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Tracts_Blocks/MapServer/2/query"
    params = {
        "f": "geojson",
        "geometry": json.dumps(esri_geometry),
        "geometryType": "esriGeometryPolygon",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "inSR": "4326",
        "outSR": "4326",
        "returnGeometry": "true"
    }

    resp = requests.get(url, params=params)
    resp.raise_for_status()
    
    return gpd.read_file(io.StringIO(resp.text))
```
