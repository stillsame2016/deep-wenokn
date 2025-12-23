---
name: assets-at-flood-risk
description: Use this skill for the requests related to the power plants or buildings or underground storage tanks at risk of flooding at a hour as an GeoDataframe in GeoPandas.
---

# assets-at-flood-risk Skill

## Description

This skill gets the geometries and other attributes of the power plants or buildings or underground storage tanks at risk of flooding at an hour from the following API endpoint:

    https://staging.api-flooding.data2action.tech/v0/impacts/structures

It returns the following attributes:

- fips: a FIPS code for each asset based on the requested level "state", "county", "tract", or "block-group".
- feature-type: "building", or "ust" for underground storage tank, or "power" for power plant
- date: in format YYYYMMDDHH 

## When to Use

- Find the buildings at risk of flooding in a region at a hour
- Find the power plants at risk of flooding in a region at a hour
- Find underground storage tanks at risk of flooding in a region at a hour

## State FIPS Codes (Reference)

Common state FIPS codes:
- Ohio: `39`
- Kentucky: `21`
- California: `06`
- New York: `36`
- Texas: `48`
- Florida: `12`

## How to Use

### Step 1: Set up the following function

**IMPORTANT**: You must include these imports:
```python
import geopandas as gpd
import requests
import time
from shapely.geometry import Point
from typing import Optional, Union, List
```

**CRITICAL NOTE**: The API returns data in a nested structure: `data["structures"]["features"]`.
You MUST access features via `data["structures"]["features"]`, NOT `data["features"]`.

```python
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
    Fetch flood impact data from the API and return as a GeoDataFrame.
    
    Parameters:
    -----------
    date : str
        Date in format YYYYMMDDHH (e.g., "2025071414" = July 14, 2025 at 2 PM / 14:00)
    fips : str
        Geographic level: "state", "county", "tract", or "block-group"
    feature_type : str
        Type of feature: "building", "ust", or "power"
    scope : str or List[str]
        State FIPS code(s). Examples: "39" (Ohio), "21" (Kentucky), ["39", "21"] (both)
        Default is ["39", "21"] (Ohio and Kentucky)
    """

    # Validate parameters
    valid_fips = ["state", "county", "tract", "block-group"]
    valid_feature_types = ["building", "ust", "power"]
    
    if fips not in valid_fips:
        raise ValueError(f"fips must be one of {valid_fips}")
    
    if feature_type not in valid_feature_types:
        raise ValueError(f"feature_type must be one of {valid_feature_types}")
    
    # Default to Ohio and Kentucky
    if scope is None:
        scope = ["39", "21"]
    if isinstance(scope, str):
        scope = [scope]
    
    if len(date) != 10 or not date.isdigit():
        raise ValueError("date must be in format YYYYMMDDHH (e.g., '2025071414')")
    
    all_features = []

    print(f"Fetching {feature_type} data for {fips} level on {date} in scope {scope}...")

    # Process each scope
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

            # Retry request block
            response = None
            for attempt in range(max_retries):
                try:
                    response = requests.get(base_url, params=params, headers=headers, timeout=30)

                    # If API says "no data" → skip but do not fail
                    if response.status_code == 404:
                        print(f"No data for scope {scope_item} on {date} (404). Skipping.")
                        response = None
                        break

                    response.raise_for_status()
                    break  # success

                except requests.RequestException as e:
                    if attempt == max_retries - 1:
                        print(f"Scope {scope_item} failed after {max_retries} attempts: {e}. Skipping this scope.")
                        response = None
                    else:
                        print(f"Attempt {attempt + 1} failed for scope {scope_item}, retrying...")
                        time.sleep(delay_between_requests * (2 ** attempt))

            # If request failed after all retries → skip this scope
            if response is None:
                break

            # Parse JSON
            try:
                data = response.json()
            except ValueError as e:
                print(f"Invalid JSON for scope {scope_item}: {e}. Skipping.")
                break

            # CRITICAL: API returns nested structure data["structures"]["features"]
            if "structures" not in data:
                print(f"Unexpected response format for scope {scope_item}. Skipping.")
                break

            structures = data["structures"]
            features = structures.get("features", [])

            # No more data for this scope
            if not features:
                break

            all_features.extend(features)

            # Pagination
            props = structures.get("properties", {})
            index_info = props.get("index", {})
            total = props.get("total", 0)
            end_index = index_info.get("end", 0)

            print(f"Scope {scope_item}, Page {page}: Retrieved {len(features)} features (total so far: {len(all_features)})")

            if end_index >= total or len(features) < 1000:
                break

            page += 1
            time.sleep(delay_between_requests)

    print(f"Completed: Retrieved {len(all_features)} total features")

    # Build GeoDataFrame
    if not all_features:
        return gpd.GeoDataFrame(
            columns=["fips", "feature-type", "geometry", "date"],  # Note: lowercase "date"
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

### Step 2: Call the function fetch_flood_impacts with proper parameters

**Example 1**: Find all power plants at risk of flooding in Ohio at 2025-10-02 10:00:00 with FIPS codes at the tract level

```python
result = fetch_flood_impacts("2025100210", fips="tract", feature_type="power", scope="39")
print(f"Found {len(result)} power plants at risk")
```

**Example 2**: Find all buildings at risk of flooding in Ohio at 2025-08-12 23:00:00 with FIPS codes at the block group level

```python
result = fetch_flood_impacts("2025081223", fips="block-group", feature_type="building", scope="39")
print(f"Found {len(result)} buildings at risk")
```

**Example 3**: Find power plants at risk in multiple states (Ohio and Kentucky) at the county level

```python
result = fetch_flood_impacts("2025070114", fips="county", feature_type="power", scope=["39", "21"])
print(f"Found {len(result)} power plants at risk")
```

## Date Format Reference

Date format is YYYYMMDDHH (10 digits):
- `2025070114` = July 1, 2025 at 1:00 AM (01:00)
- `2025070214` = July 2, 2025 at 2:00 PM (14:00)
- `2025081223` = August 12, 2025 at 11:00 PM (23:00)
- `2025123100` = December 31, 2025 at midnight (00:00)

## Troubleshooting

**Getting 0 results?**
1. Verify you're using `data["structures"]["features"]` not `data["features"]`
2. Check the date format is exactly 10 digits (YYYYMMDDHH)
3. Verify the state FIPS code is correct (e.g., Ohio = "39")
4. Check if flood data exists for that specific date/time

**Common mistakes to avoid:**
- ❌ Don't use `data["features"]` - the API returns `data["structures"]["features"]`
- ❌ Don't forget to import `time` and `Point`
- ❌ Don't use incorrect date formats (must be exactly 10 digits)
