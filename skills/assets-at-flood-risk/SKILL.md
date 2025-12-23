---
name: assets-at-flood-risk
description: Retrieves power plants, buildings, or underground storage tanks at flood risk as a GeoDataFrame.
---

# assets-at-flood-risk Skill

## Description
Fetches geometries and attributes of assets at flood risk from:
```
https://staging.api-flooding.data2action.tech/v0/impacts/structures
```

**Returns:** GeoDataFrame with `fips`, `feature-type`, `geometry`, and `date` (YYYYMMDDHH format).

## Critical API Notes
- Response structure: Features are under `data["structures"]["features"]`, NOT `data["features"]`
- Must manually create Point geometries from `feature["geometry"]["coordinates"]`
- Pagination: Use `data["structures"]["properties"]["index"]` for total/end values

## Usage

### Function Setup
```python
def fetch_flood_impacts(
    date: str, 
    fips: str = "county",  # "state" | "county" | "tract" | "block-group"
    feature_type: str = "power",  # "building" | "ust" | "power"
    scope: Optional[Union[str, List[str]]] = None,  # State FIPS codes, default ["39", "21"]
    base_url: str = "https://staging.api-flooding.data2action.tech/v0/impacts/structures",
    max_retries: int = 3,
    delay_between_requests: float = 0.1
) -> gpd.GeoDataFrame:
    """Fetch flood impact data and return as GeoDataFrame."""
    
    # Validate inputs
    valid_fips = ["state", "county", "tract", "block-group"]
    valid_feature_types = ["building", "ust", "power"]
    
    if fips not in valid_fips or feature_type not in valid_feature_types:
        raise ValueError(f"Invalid parameters")
    if len(date) != 10 or not date.isdigit():
        raise ValueError("date format: YYYYMMDDHH")
    
    scope = scope or ["39", "21"]
    if isinstance(scope, str):
        scope = [scope]
    
    all_features = []

    for scope_item in scope:
        page = 0
        while True:
            params = {
                "date": date, "fips": fips, "feature-type": feature_type,
                "scope": scope_item, "response-format": "geojson",
                "page": page, "size": 1000
            }
            headers = {"x-api-key": "maj6OM1L77141VXiH7GMy1iLRWmFI88M5JVLMHn7"}

            # Retry logic
            response = None
            for attempt in range(max_retries):
                try:
                    response = requests.get(base_url, params=params, headers=headers, timeout=30)
                    if response.status_code == 404:
                        response = None
                        break
                    response.raise_for_status()
                    break
                except requests.RequestException:
                    if attempt == max_retries - 1:
                        response = None
                    time.sleep(delay_between_requests * (2 ** attempt))

            if not response:
                break

            try:
                data = response.json()
            except ValueError:
                break

            # CRITICAL: Access structures key
            if "structures" not in data:
                break

            structures = data["structures"]
            features = structures.get("features", [])
            
            if not features:
                break

            all_features.extend(features)

            # Check pagination
            props = structures.get("properties", {})
            total = props.get("total", 0)
            end_index = props.get("index", {}).get("end", 0)

            if end_index >= total or len(features) < 1000:
                break

            page += 1
            time.sleep(delay_between_requests)

    # Build GeoDataFrame
    if not all_features:
        return gpd.GeoDataFrame(
            columns=["fips", "feature-type", "geometry", "date"],
            geometry="geometry", crs="EPSG:4326"
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

### Examples
```python
# Power plants at risk in Ohio on 2025-10-02 10:00, tract level
fetch_flood_impacts("2025100210", fips="tract", feature_type="power", scope="39")

# Buildings at risk in Ohio on 2025-08-12 23:00, block group level
fetch_flood_impacts("2025081223", fips="block-group", feature_type="building", scope="39")
```
