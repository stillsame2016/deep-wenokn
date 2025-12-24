---
name: census-tracts
description: Use this skill for the requests related to USA census tracts; it provides a way to get tracts as a GeoDataframe in GeoPandas
---

# Census-Tracts Skill

## Description

This skill gets the geometries and other attributes of census tracts in USA by accessing the ArcGIS Feature Service at the following URL: 

    https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Tracts_Blocks/MapServer/0/query

It returns the following columns:

MTFCC: Census feature classification code identifying the type of geographic feature.
OID: Original unique identifier assigned by the source dataset.
GEOID: Unique Census geographic identifier for the tract.
STATE: Two-digit FIPS code identifying the state.
COUNTY: Three-digit FIPS code identifying the county within the state.
TRACT: Six-digit Census tract code within the county.
BASENAME: Base name of the Census tract without descriptive suffixes.
NAME: Full name of the Census tract.
LSADC: Legal/statistical area description code for the tract.
FUNCSTAT: Functional status indicating whether the tract is active or inactive.
AREALAND: Land area of the tract in square meters.
AREAWATER: Water area of the tract in square meters.
STGEOMETRY: Geometry representing the spatial boundaries of the Census tract.
CENTLAT: Latitude of the tract’s centroid.
CENTLON: Longitude of the tract’s centroid.
INTPTLAT: Latitude of the internal point used for label placement.
INTPTLON: Longitude of the internal point used for label placement.
OBJECTID: System-generated unique object identifier for the feature.

## When to Use

- Find a census tract by FIPS
- For a location with the given latitude and longitude, find the census tract contains the location
- For a region, find all the census tracts intersecting with the region

## How to Use

### Example 1:  Find a census tract at a given location

```
def load_census_tract(latitude, longitude):

    url = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Tracts_Blocks/MapServer/0/query"
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
        raise ValueError("No census tract found at the given location.")
    return gdf
```

### Example 2: Find the census tracts that Muskingum river passes

```
import geopandas as gpd
import requests
import json
import time
import numpy as np
from shapely.geometry import Point, LineString, MultiLineString, Polygon, MultiPolygon, mapping
import shapely.geometry

def get_tracts_for_geometry(geometry, retries=3, buffer_distance=0.0001):
    """
    Query Census TIGER/Web API to find tracts intersecting with a geometry.
    
    Args:
        geometry: Shapely geometry object
        retries: Number of retry attempts for failed requests
        buffer_distance: Buffer distance for line geometries (degrees)
    
    Returns:
        GeoDataFrame with tract information
    """
    url = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Tracts_Blocks/MapServer/0/query"
    
    # Handle buffering for lines to address precision/gap issues
    if buffer_distance > 0 and isinstance(geometry, (LineString, MultiLineString)):
        geometry = geometry.buffer(buffer_distance)
    
    # Prepare geometry based on type
    if isinstance(geometry, Point):
        geometry_type = "esriGeometryPoint"
        geometry_param = {"x": geometry.x, "y": geometry.y}
        if not (-125 <= geometry.x <= -66 and 24 <= geometry.y <= 49):
            return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    
    elif isinstance(geometry, (LineString, MultiLineString)):
        geometry_type = "esriGeometryPolyline"
        # Simplify to reduce complexity
        geometry = geometry.simplify(tolerance=0.0001, preserve_topology=True)
        
        if isinstance(geometry, LineString):
            paths = [list(geometry.coords)]
        else:
            paths = [list(line.coords) for line in geometry.geoms]
        
        # Validate coordinates
        all_coords = [coord for path in paths for coord in path]
        if not all(-125 <= lon <= -66 and 24 <= lat <= 49 and 
                   np.isfinite(lon) and np.isfinite(lat) 
                   for lon, lat in all_coords):
            return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
        
        geometry_param = {"paths": paths}
    
    elif isinstance(geometry, (Polygon, MultiPolygon)):
        geometry_type = "esriGeometryPolygon"
        
        def get_rings(geom):
            rings = []
            if isinstance(geom, Polygon):
                # Exterior ring
                rings.append(list(geom.exterior.coords))
                # Interior rings (holes)
                for interior in geom.interiors:
                    rings.append(list(interior.coords))
            else:
                for poly in geom.geoms:
                    rings.append(list(poly.exterior.coords))
                    for interior in poly.interiors:
                        rings.append(list(interior.coords))
            return rings
        
        geometry_param = {"rings": get_rings(geometry)}
    
    else:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    
    # Prepare request parameters
    params = {
        "f": "geojson",
        "geometry": json.dumps(geometry_param),
        "geometryType": geometry_type,
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "GEOID,STATE,COUNTY,TRACT,NAME,BASENAME",
        "returnGeometry": "true"
    }
    
    # Make request with retries
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            
            # Parse GeoJSON response
            data = json.loads(resp.text)
            
            if 'features' not in data or len(data['features']) == 0:
                return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
            
            gdf = gpd.GeoDataFrame.from_features(data['features'], crs="EPSG:4326")
            return gdf
            
        except Exception as e:
            print(f"Attempt {attempt + 1}/{retries} failed: {str(e)}")
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
            else:
                print(f"All retries failed")
    
    return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")

def process_river_by_segments(river_geometry, max_points_per_segment=30):
    """
    Process long rivers by breaking them into segments to avoid API limitations.
    
    Args:
        river_geometry: River geometry (LineString or MultiLineString)
        max_points_per_segment: Maximum points per segment (lower = more reliable)
    
    Returns:
        GeoDataFrame with all unique tracts
    """
    all_tracts = []
    failed_segments = []
    
    if isinstance(river_geometry, LineString):
        lines = [river_geometry]
    elif isinstance(river_geometry, MultiLineString):
        lines = list(river_geometry.geoms)
    else:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    
    for line_idx, line in enumerate(lines):
        coords = list(line.coords)
        num_points = len(coords)
        
        # Calculate number of segments based on max points
        num_segments = int(np.ceil(num_points / max_points_per_segment))
        points_per_segment = int(np.ceil(num_points / num_segments))
        
        print(f"Processing line {line_idx + 1}/{len(lines)} with {num_points} points in {num_segments} segments")
        print(f"  (~{points_per_segment} points per segment)")
        
        for seg_idx in range(0, num_points - 1, points_per_segment):
            end_idx = min(seg_idx + points_per_segment + 1, num_points)
            segment_coords = coords[seg_idx:end_idx]
            
            if len(segment_coords) < 2:
                continue
            
            segment = LineString(segment_coords)
            segment_num = seg_idx // points_per_segment + 1
            print(f"  Segment {segment_num}/{num_segments}: points {seg_idx} to {end_idx-1} ({len(segment_coords)} points)")
            
            # Query tracts for this segment
            tracts = get_tracts_for_geometry(segment, buffer_distance=0.0001, retries=3)
            
            if not tracts.empty:
                all_tracts.append(tracts)
                print(f"    ✓ Found {len(tracts)} tracts")
            else:
                print(f"    ✗ No tracts found (may have failed)")
                failed_segments.append((seg_idx, end_idx, segment))
            
            # Rate limiting - be nice to the API
            time.sleep(1.0)
    
    # Retry failed segments with even smaller chunks
    if failed_segments:
        print(f"\nRetrying {len(failed_segments)} failed segments with smaller chunks...")
        for seg_idx, end_idx, segment in failed_segments:
            coords = list(segment.coords)
            # Break into very small chunks (10 points)
            small_chunk_size = 10
            
            for i in range(0, len(coords) - 1, small_chunk_size):
                chunk_end = min(i + small_chunk_size + 1, len(coords))
                chunk_coords = coords[i:chunk_end]
                
                if len(chunk_coords) < 2:
                    continue
                
                chunk = LineString(chunk_coords)
                print(f"  Retry chunk: points {i} to {chunk_end-1}")
                
                tracts = get_tracts_for_geometry(chunk, buffer_distance=0.0002, retries=2)
                
                if not tracts.empty:
                    all_tracts.append(tracts)
                    print(f"    ✓ Found {len(tracts)} tracts")
                
                time.sleep(0.5)
    
    if not all_tracts:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    
    # Combine and remove duplicates
    combined = gpd.GeoDataFrame(pd.concat(all_tracts, ignore_index=True), crs="EPSG:4326")
    unique_tracts = combined.drop_duplicates(subset=['GEOID']).reset_index(drop=True)
    
    return unique_tracts

def main():
    # Load the river GeoJSON
    print("Loading Muskingum River GeoJSON...")
    river_gdf = gpd.read_file("muskingum_river.geojson")
    
    print(f"Loaded {len(river_gdf)} feature(s)")
    print(f"CRS: {river_gdf.crs}")
    
    # Ensure WGS84 projection
    if river_gdf.crs != "EPSG:4326":
        print("Converting to EPSG:4326...")
        river_gdf = river_gdf.to_crs("EPSG:4326")
    
    # Get the river geometry (combine all features if multiple)
    if len(river_gdf) > 1:
        river_geometry = river_gdf.unary_union
    else:
        river_geometry = river_gdf.geometry.iloc[0]
    
    print(f"River geometry type: {river_geometry.geom_type}")
    
    # Process the river to find all intersecting tracts
    print("\nFinding census tracts...")
    tracts = process_river_by_segments(river_geometry, max_points_per_segment=30)
    
    print(f"\nFound {len(tracts)} unique census tracts")
    
    if not tracts.empty:
        # Display results
        print("\nCensus Tracts:")
        print(tracts[['GEOID', 'NAME', 'STATE', 'COUNTY', 'TRACT']].to_string(index=False))
        
        # Save results
        output_file = "muskingum_tracts.geojson"
        tracts.to_file(output_file, driver="GeoJSON")
        print(f"\nResults saved to {output_file}")
        
        # Save as CSV (without geometry)
        csv_file = "muskingum_tracts.csv"
        tracts.drop(columns=['geometry']).to_csv(csv_file, index=False)
        print(f"Tract list saved to {csv_file}")
    else:
        print("No tracts found!")
    
    return tracts

if __name__ == "__main__":
    import pandas as pd
    tracts = main()

```
