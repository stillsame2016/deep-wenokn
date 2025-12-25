---
name: frs-facilities
description: Retrieves facility geometries from EPA's Facility Registry Service (FRS) for Illinois, Maine, and Ohio as GeoDataFrames
---

# FRS Facilities Skill

## Overview

Query EPA's Facility Registry Service (FRS) data from the SAWGraph knowledge graph to retrieve facility geometries and attributes for Illinois, Maine, and Ohio.

## Prerequisites

The `load_FRS_facilities` function is pre-deployed in `utils.py`. Simply import and use it.

```python
from utils import load_FRS_facilities
```

## Supported States

- Illinois
- Maine
- Ohio

## Supported NAICS Industries

- Waste Treatment and Disposal
- Converted Paper Manufacturing
- Water Supply and Irrigation
- Sewage Treatment
- Plastics Product Manufacturing
- Textile and Fabric Finishing and Coating
- Basic Chemical Manufacturing
- Paint, Coating, and Adhesive Manufacturing
- Aerospace Product and Parts
- Drycleaning and Laundry Services
- Carpet and Upholstery Cleaning Services
- Solid Waste Landfill

## Usage

### Basic Usage

```python
from utils import load_FRS_facilities

# Load sewage treatment facilities in Maine
sewage_facilities = load_FRS_facilities(
    state="Maine",
    naics_name="Sewage Treatment"
)

print(f"Found {len(sewage_facilities)} facilities")
print(sewage_facilities.head())
```

### With Custom Limit

```python
from utils import load_FRS_facilities

# Load up to 500 waste treatment facilities in Illinois
waste_facilities = load_FRS_facilities(
    state="Illinois",
    naics_name="Waste Treatment and Disposal",
    limit=500
)
```

### Function Signature

```python
load_FRS_facilities(
    state: str,           # "Illinois", "Maine", or "Ohio"
    naics_name: str,      # One of the supported NAICS industries
    limit: int = 1000     # Maximum facilities to retrieve
) -> gpd.GeoDataFrame
```

## Returned Data

The function returns a GeoDataFrame with the following columns:

| Column | Description |
|--------|-------------|
| `facilityName` | Name of the facility |
| `industryCodes` | Industry classifications (comma-separated if multiple) |
| `geometry` | Point geometry in EPSG:4326 (WGS84) |
| `countyName` | County where facility is located |
| `stateName` | State where facility is located |
| `frsId` | FRS identifier (may be null) |
| `triId` | Toxics Release Inventory ID (may be null) |
| `rcraId` | Resource Conservation and Recovery Act ID (may be null) |
| `airId` | Air program identifier (may be null) |
| `npdesId` | National Pollutant Discharge Elimination System ID (may be null) |
| `envInterestTypes` | Environmental interest types (may be null) |
| `facility` | Facility URI in the knowledge graph |

## Common Use Cases

### 1. Find facilities in a specific area

```python
from utils import load_FRS_facilities

# Get all sewage treatment facilities in Maine
facilities = load_FRS_facilities("Maine", "Sewage Treatment")

# Filter to a specific county
york_county = facilities[facilities['countyName'] == 'York County']
```

### 2. Spatial analysis with other datasets

```python
from utils import load_FRS_facilities
import geopandas as gpd

# Load facilities
facilities = load_FRS_facilities("Maine", "Sewage Treatment")

# Load another spatial dataset
contamination_sites = gpd.read_file("pfas_sites.geojson")

# Find facilities within 100 meters of contamination sites
nearby = facilities[
    facilities.geometry.distance(contamination_sites.unary_union) < 0.001  # ~100m in degrees
]
```

### 3. Export to different formats

```python
from utils import load_FRS_facilities

facilities = load_FRS_facilities("Ohio", "Basic Chemical Manufacturing")

# Export to GeoJSON
facilities.to_file("ohio_chemical_facilities.geojson", driver="GeoJSON")

# Export to Shapefile
facilities.to_file("ohio_chemical_facilities.shp")

# Export to CSV (without geometry)
facilities.drop(columns=['geometry']).to_csv("ohio_facilities.csv", index=False)
```

### 4. Multiple industries analysis

```python
from utils import load_FRS_facilities
import pandas as pd

# Load multiple industry types
sewage = load_FRS_facilities("Maine", "Sewage Treatment")
waste = load_FRS_facilities("Maine", "Waste Treatment and Disposal")
chemical = load_FRS_facilities("Maine", "Basic Chemical Manufacturing")

# Combine all facilities
all_facilities = pd.concat([sewage, waste, chemical], ignore_index=True)
print(f"Total facilities: {len(all_facilities)}")
```

## Error Handling

```python
from utils import load_FRS_facilities

try:
    facilities = load_FRS_facilities("California", "Sewage Treatment")
except ValueError as e:
    print(f"Error: {e}")
    # Output: Error: Invalid state 'California'. Allowed: ['Illinois', 'Maine', 'Ohio']

try:
    facilities = load_FRS_facilities("Maine", "Invalid Industry")
except ValueError as e:
    print(f"Error: {e}")
    # Output: Error: Invalid NAICS 'Invalid Industry'. Allowed: [...]
```

## Troubleshooting

### No results returned

If the GeoDataFrame is empty:
1. Verify the state name is exactly "Illinois", "Maine", or "Ohio" (case-sensitive)
2. Verify the NAICS name exactly matches one from the supported list (case-sensitive)
3. Check that facilities exist for that combination (some industries may not have facilities in all states)

### ValueError exceptions

- Ensure state parameter is one of: "Illinois", "Maine", "Ohio"
- Ensure naics_name parameter exactly matches one of the 12 supported industries
- Check for typos and correct capitalization

### Import errors

If you get `ImportError: cannot import name 'load_FRS_facilities'`:
- Verify `utils.py` is in the same directory or in your Python path
- Check that `utils.py` contains the `load_FRS_facilities` function

### Slow query performance

- Typical query time: 5-30 seconds depending on the number of facilities
- Reduce the `limit` parameter if you only need a sample
- Consider caching results if you need to run the same query multiple times

## Technical Details

**Data Source**: SAWGraph knowledge graph via Qlever SPARQL endpoint

**Coordinate System**: All geometries are returned in EPSG:4326 (WGS84)

**Data Quality**: Facilities without valid geometries are automatically filtered out

**Dependencies**: 
- `geopandas` - spatial data handling
- `sparql_dataframe` - SPARQL query execution
- `shapely` - geometry parsing

**Performance Notes**:
- The function is optimized for the Qlever SPARQL endpoint
- Results are limited to 1000 facilities by default to ensure reasonable query times
- Increase the `limit` parameter if you need more results

## Important Notes

⚠️ **Do not modify `utils.py`** - The function contains a validated SPARQL query that is optimized for the specific endpoint. Modifications will likely cause the query to fail.

✅ **Do** use the function as-is by importing from `utils.py`

✅ **Do** perform any additional filtering, analysis, or transformations on the returned GeoDataFrame

✅ **Do** report issues if the function doesn't work as expected
