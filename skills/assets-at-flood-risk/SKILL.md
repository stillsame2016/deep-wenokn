---
name: assets-at-flood-risk
description: Use this skill for requests related to power plants, buildings, or underground storage tanks at risk of flooding at a specific hour as a GeoDataFrame in GeoPandas.
---

# assets-at-flood-risk Skill

## Description

Gets geometries and attributes of power plants, buildings, or underground storage tanks at risk of flooding from:

    https://staging.api-flooding.data2action.tech/v0/impacts/structures

Returns: fips, feature-type, geometry, date (YYYYMMDDHH)

## When to Use

- Find buildings/power plants/underground storage tanks at risk of flooding in a region at a specific hour

## State FIPS Codes

Ohio: 39, Kentucky: 21, California: 06, New York: 36, Texas: 48, Florida: 12

## Implementation

CRITICAL: Copy this code exactly. Do not modify pagination, headers, or response parsing.

```python
import geopandas as gpd
import requests
import time
from shapely.geometry import Point
from typing import Optional, Union, List

def fetch_flood_impacts(
    date: str,
    fips: str = "county",
    feature_type: str = "power",
    scope: Optional[Union[str, List[str]]] = None,
    base_url: str = "https://staging.api-flooding.data2action.tech/v0/impacts/structures",
    max_retries: int = 3,
    delay_between_requests: float = 0.1
) -> gpd.GeoDataFrame:
    """
    Parameters:
    date: YYYYMMDDHH format (e.g., "2025070114" = July 1, 2025 at 14:00)
    fips: "state", "county", "tract", or "block-group"
    feature_type: "building", "ust", or "power"
    scope: State FIPS code(s), e.g., "39" (Ohio), ["39", "21"] (Ohio and Kentucky)
    """
    
    valid_fips = ["state", "county", "tract", "block-group"]
    valid_feature_types = ["building", "ust", "power"]
    
    if fips not in valid_fips:
        raise ValueError(f"fips must be one of {valid_fips}")
    
    if feature_type not in valid_feature_types:
        raise ValueError(f"feature_type must be one of {valid_feature_types}")
    
    if scope is None:
        scope = ["39", "21"]
    if isinstance(scope, str):
        scope = [scope]
    
    if len(date) != 10 or not date.isdigit():
        raise ValueError("date must be in format YYYYMMDDHH")
    
    all_features = []
    print(f"Fetching {feature_type} data for {fips} level on {date} in scope {scope}...")
    
    for scope_item in scope:
        print(f"Processing scope: {scope_item}")
        page = 0
        
        while True:
            params = {
                "date": date,
                "fips": fips,
                "feature-type": feature_type,
                "scope": scope_item,
                "response-format": "geojson",
                "page": page,
                "size": 1000
            }
            
            headers = {
                "x-api-key": "maj6OM1L77141VXiH7GMy1iLRWmFI88M5JVLMHn7"
            }
            
            response = None
            for attempt in range(max_retries):
                try:
                    response = requests.get(base_url, params=params, headers=headers, timeout=30)
                    
                    if response.status_code == 404:
                        print(f"No data for scope {scope_item} on {date} (404). Skipping.")
                        response = None
                        break
                    
                    response.raise_for_status()
                    break
                
                except requests.RequestException as e:
                    if attempt == max_retries - 1:
                        print(f"Scope {scope_item} failed after {max_retries} attempts: {e}. Skipping.")
                        response = None
                    else:
                        print(f"Attempt {attempt + 1} failed for scope {scope_item}, retrying...")
                        time.sleep(delay_between_requests * (2 ** attempt))
            
            if response is None:
                break
            
            try:
                data = response.json()
            except ValueError as e:
                print(f"Invalid JSON for scope {scope_item}: {e}. Skipping.")
                break
            
            # API returns nested structure: data["structures"]["features"]
            if "structures" not in data:
                print(f"Unexpected response format for scope {scope_item}. Skipping.")
                break
            
            structures = data["structures"]
            features = structures.get("features", [])
            
            if not features:
                break
            
            all_features.extend(features)
            
            # Check pagination
            props = structures.get("properties", {})
            index_info = props.get("index", {})
            total = props.get("total", 0)
            end_index = index_info.get("end", 0)
            
            print(f"Scope {scope_item}, Page {page}: Retrieved {len(features)} features (total: {len(all_features)})")
            
            if end_index >= total or len(features) < 1000:
                break
            
            page += 1
            time.sleep(delay_between_requests)
    
    print(f"Completed: Retrieved {len(all_features)} total features")
    
    if not all_features:
        return gpd.GeoDataFrame(
            columns=["fips", "feature-type", "geometry", "date"],
            geometry="geometry",
            crs="EPSG:4326"
        )
    
    rows = []
    for feature in all_features:
        props = feature["properties"]
        lon, lat = feature["geometry"]["coordinates"]
        
        rows.append({
            "fips": props["fips"],
            "feature-type": props["feature-type"],
            "geometry": Point(lon, lat)
        })
    
    gdf = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    gdf["date"] = date
    
    return gdf
```

## Usage Examples

Example 1: Power plants in Ohio at 2 PM on July 1, 2025 (tract level)
```python
result = fetch_flood_impacts("2025070114", fips="tract", feature_type="power", scope="39")
if len(result) > 0:
    result.to_file("/tmp/output.geojson", driver="GeoJSON")
```

Example 2: Buildings in Ohio at 11 PM on Aug 12, 2025 (block-group level)
```python
result = fetch_flood_impacts("2025081223", fips="block-group", feature_type="building", scope="39")
```

Example 3: Power plants in multiple states (county level)
```python
result = fetch_flood_impacts("2025070114", fips="county", feature_type="power", scope=["39", "21"])
```

## Date Format

YYYYMMDDHH (10 digits, 24-hour time):
- 2025070114 = July 1, 2025 at 14:00 (2 PM)
- 2025081223 = August 12, 2025 at 23:00 (11 PM)
- 2025010100 = January 1, 2025 at 00:00 (midnight)

## Important Notes

- API returns data["structures"]["features"], not data["features"]
- Must include x-api-key header
- Must include page and size parameters for pagination
- Must handle 404 responses (no data available)
- Copy code exactly as shown, only change function call parameters
