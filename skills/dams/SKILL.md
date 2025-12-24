---
name: dams
description: Query dam geometries in the USA from the GeoConnex knowledge graph. Returns dam locations and metadata as a GeoDataFrame.
---

# Dams Skill

## Description

Retrieves dam geometries from the GeoConnex knowledge graph on FRINK using SPARQL queries. Returns results as a GeoPandas GeoDataFrame.

## When to Use

- Find dams by name
- Find dams within counties or states
- Find dams near rivers or other geographic features
- Spatial analysis involving dams

## Important Notes

- **Always use spatial filtering in SPARQL** using `geof:sfContains()` for county/state queries - this is much faster than filtering in Python
- **County names must include state** - use "Ross County, Ohio" not just "Ross County"
- **Dams are point geometries** - they may not intersect river lines exactly due to GIS precision
- **Large queries take time** - state-level queries may take up to 1 minute
- **Data source** - only National Inventory of Dams (NID) data is available

## Examples

### Example 1: Find Dams in a County

**User Request:** "Find all dams in Ross County" or "Find dams in Ross County, Ohio"

**Complete Code:**

```python
import sparql_dataframe
import geopandas as gpd
from shapely import wkt

# SPARQL query with spatial filtering
query = '''
PREFIX schema: <https://schema.org/>
PREFIX geo: <http://www.opengis.net/ont/geosparql#>
PREFIX geof: <http://www.opengis.net/def/function/geosparql/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?damName ?damGeometry ?countyName
WHERE {
    # Specify the county
    VALUES ?inputCounty { "Ross County, Ohio" }
    
    # Get county geometry
    ?county rdf:type <http://stko-kwg.geog.ucsb.edu/lod/ontology/AdministrativeRegion_2>;
            rdfs:label ?countyName;
            geo:hasGeometry/geo:asWKT ?countyGeometry.
    FILTER(STRSTARTS(STR(?county), "http://stko-kwg.geog.ucsb.edu/lod/resource/"))
    FILTER(STRSTARTS(LCASE(STR(?countyName)), LCASE(?inputCounty)))
    
    # Get dams
    ?dam schema:provider "https://nid.usace.army.mil"^^<https://schema.org/url>;
         schema:name ?damName;
         geo:hasGeometry/geo:asWKT ?damGeometry.
    FILTER(STRSTARTS(STR(?dam), "https://geoconnex.us/ref/dams/"))
    
    # Spatial filter - dam must be contained in county
    FILTER(geof:sfContains(?countyGeometry, ?damGeometry))
}
'''

# Execute query
endpoint_url = "https://frink.apps.renci.org/federation/sparql"
df = sparql_dataframe.get(endpoint_url, query)

# Convert to GeoDataFrame
wkt_col = None
for col in df.columns:
    col_lower = col.lower()
    if 'geometry' in col_lower or 'geom' in col_lower or 'wkt' in col_lower:
        sample = df[col].dropna().astype(str)
        if len(sample) > 0:
            valid_wkt = sample.str.match(r'^(POINT|LINESTRING|POLYGON|MULTIPOINT|MULTILINESTRING|MULTIPOLYGON|GEOMETRYCOLLECTION)\s*\(')
            if valid_wkt.sum() / len(sample) > 0.5:
                wkt_col = col
                break

if wkt_col is None:
    raise ValueError("No WKT geometry column found")

df = df.dropna(subset=[wkt_col]).copy()
df['geometry'] = df[wkt_col].apply(wkt.loads)
gdf = gpd.GeoDataFrame(df, geometry='geometry', crs='EPSG:4326')

# Display results
print(f"Found {len(gdf)} dams in Ross County, Ohio")
for _, row in gdf.iterrows():
    print(f"- {row['damName']}")
```

**Key Points:**
- Uses `AdministrativeRegion_2` for counties
- Spatial filtering with `geof:sfContains(?countyGeometry, ?damGeometry)`
- County name must include state: "Ross County, Ohio"

---

### Example 2: Find Dams in a State

**User Request:** "Find all dams in Ohio" or "Find dams in Ohio state"

**Complete Code:**

```python
import sparql_dataframe
import geopandas as gpd
from shapely import wkt

# SPARQL query with spatial filtering
query = '''
PREFIX schema: <https://schema.org/>
PREFIX geo: <http://www.opengis.net/ont/geosparql#>
PREFIX geof: <http://www.opengis.net/def/function/geosparql/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?damName ?damGeometry ?stateName
WHERE {
    # Specify the state
    VALUES ?inputState { "Ohio" }
    
    # Get state geometry
    ?state rdf:type <http://stko-kwg.geog.ucsb.edu/lod/ontology/AdministrativeRegion_1>;
           rdfs:label ?stateName;
           geo:hasGeometry/geo:asWKT ?stateGeometry.
    FILTER(STRSTARTS(STR(?state), "http://stko-kwg.geog.ucsb.edu/lod/resource/"))
    FILTER(STRSTARTS(LCASE(STR(?stateName)), LCASE(?inputState)))
    
    # Get dams
    ?dam schema:provider "https://nid.usace.army.mil"^^<https://schema.org/url>;
         schema:name ?damName;
         geo:hasGeometry/geo:asWKT ?damGeometry.
    FILTER(STRSTARTS(STR(?dam), "https://geoconnex.us/ref/dams/"))
    
    # Spatial filter - dam must be contained in state
    FILTER(geof:sfContains(?stateGeometry, ?damGeometry))
}
'''

# Execute query
endpoint_url = "https://frink.apps.renci.org/federation/sparql"
df = sparql_dataframe.get(endpoint_url, query)

# Convert to GeoDataFrame
wkt_col = None
for col in df.columns:
    col_lower = col.lower()
    if 'geometry' in col_lower or 'geom' in col_lower or 'wkt' in col_lower:
        sample = df[col].dropna().astype(str)
        if len(sample) > 0:
            valid_wkt = sample.str.match(r'^(POINT|LINESTRING|POLYGON|MULTIPOINT|MULTILINESTRING|MULTIPOLYGON|GEOMETRYCOLLECTION)\s*\(')
            if valid_wkt.sum() / len(sample) > 0.5:
                wkt_col = col
                break

if wkt_col is None:
    raise ValueError("No WKT geometry column found")

df = df.dropna(subset=[wkt_col]).copy()
df['geometry'] = df[wkt_col].apply(wkt.loads)
gdf = gpd.GeoDataFrame(df, geometry='geometry', crs='EPSG:4326')

# Display results
print(f"Found {len(gdf)} dams in Ohio")
print(f"First 10 dams:")
for _, row in gdf.head(10).iterrows():
    print(f"- {row['damName']}")
```

**Key Points:**
- Uses `AdministrativeRegion_1` for states
- Spatial filtering with `geof:sfContains(?stateGeometry, ?damGeometry)`
- State name only: "Ohio" (no additional qualifier needed)
- May take up to 1 minute for large states

---

### Example 3: Find Dam by Name

**User Request:** "Find Deer Creek Dam" or "Find dam named Deer Creek"

**Complete Code:**

```python
import sparql_dataframe
import geopandas as gpd
from shapely import wkt

# SPARQL query with name filtering
query = '''
PREFIX schema: <https://schema.org/>
PREFIX geo: <http://www.opengis.net/ont/geosparql#>

SELECT ?damName ?damGeometry ?damDescription
WHERE {  
    ?dam a schema:Place;
         schema:provider "https://nid.usace.army.mil"^^<https://schema.org/url>;
         schema:name ?damName;
         schema:description ?damDescription;
         geo:hasGeometry/geo:asWKT ?damGeometry.
    FILTER(STRSTARTS(STR(?dam), "https://geoconnex.us/ref/dams/"))
    
    # Filter by name (case-insensitive prefix match)
    FILTER(STRSTARTS(LCASE(STR(?damName)), LCASE("Deer Creek")))
}
LIMIT 10
'''

# Execute query
endpoint_url = "https://frink.apps.renci.org/federation/sparql"
df = sparql_dataframe.get(endpoint_url, query)

# Convert to GeoDataFrame
wkt_col = None
for col in df.columns:
    col_lower = col.lower()
    if 'geometry' in col_lower or 'geom' in col_lower or 'wkt' in col_lower:
        sample = df[col].dropna().astype(str)
        if len(sample) > 0:
            valid_wkt = sample.str.match(r'^(POINT|LINESTRING|POLYGON|MULTIPOINT|MULTILINESTRING|MULTIPOLYGON|GEOMETRYCOLLECTION)\s*\(')
            if valid_wkt.sum() / len(sample) > 0.5:
                wkt_col = col
                break

if wkt_col is None:
    raise ValueError("No WKT geometry column found")

df = df.dropna(subset=[wkt_col]).copy()
df['geometry'] = df[wkt_col].apply(wkt.loads)
gdf = gpd.GeoDataFrame(df, geometry='geometry', crs='EPSG:4326')

# Display results
print(f"Found {len(gdf)} dams matching 'Deer Creek'")
for _, row in gdf.iterrows():
    print(f"- {row['damName']}")
    print(f"  Description: {row['damDescription']}")
```

**Key Points:**
- Uses `STRSTARTS` for case-insensitive prefix matching
- No spatial filtering needed for name-based queries
- Returns dam name, geometry, and description
- Use LIMIT to avoid returning too many results

---

## Query Pattern Summary

| Query Type | Administrative Level | Ontology Class | Spatial Filter |
|------------|---------------------|----------------|----------------|
| County | AdministrativeRegion_2 | County name must include state | `geof:sfContains(?countyGeometry, ?damGeometry)` |
| State | AdministrativeRegion_1 | State name only | `geof:sfContains(?stateGeometry, ?damGeometry)` |
| Name | N/A | N/A | `FILTER(STRSTARTS(LCASE(STR(?damName)), LCASE("name")))` |

## Common Patterns for Multiple Regions

To query multiple counties or states, use `VALUES` with multiple entries:

```sparql
# Multiple counties
VALUES ?inputCounty {
    "Ross County, Ohio"
    "Scioto County, Ohio"
}

# Multiple states
VALUES ?inputState {
    "Ohio"
    "Kentucky"
}
```
