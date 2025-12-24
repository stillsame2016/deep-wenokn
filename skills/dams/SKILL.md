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

## Implementation Steps

### 1. Build SPARQL Query

All dam queries follow this basic pattern:

```sparql
PREFIX schema: <https://schema.org/>
PREFIX geo: <http://www.opengis.net/ont/geosparql#>
PREFIX geof: <http://www.opengis.net/def/function/geosparql/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?damName ?damGeometry ?damDescription
WHERE {  
    ?dam a schema:Place;
         schema:provider "https://nid.usace.army.mil"^^<https://schema.org/url>;
         schema:name ?damName ;
         schema:description ?damDescription;
         geo:hasGeometry/geo:asWKT ?damGeometry.
    FILTER(STRSTARTS(STR(?dam), "https://geoconnex.us/ref/dams/")) 
}
```

### 2. Execute Query

```python
import sparql_dataframe

endpoint_url = "https://frink.apps.renci.org/federation/sparql"
df = sparql_dataframe.get(endpoint_url, query)
```

### 3. Convert to GeoDataFrame

```python
import geopandas as gpd
from shapely import wkt

# Auto-detect WKT column
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

# Create GeoDataFrame
df = df.dropna(subset=[wkt_col]).copy()
df['geometry'] = df[wkt_col].apply(wkt.loads)
gdf = gpd.GeoDataFrame(df, geometry='geometry', crs='EPSG:4326')
```

## Query Patterns

### Find Dams by Name

Add a name filter:

```sparql
FILTER(STRSTARTS(LCASE(STR(?damName)), LCASE("deer creek")))
```

### Find Dams in Counties

**Always use this pattern for county queries** - spatial filtering on the server is much faster:

```sparql
SELECT ?damName ?damGeometry ?countyName
WHERE {
    # Specify counties
    VALUES ?inputCounty {
        "Ross County, Ohio"
        "Scioto County, Ohio"
    }
    
    # Get county geometries (filter early)
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
    
    # Spatial filter (on server)
    FILTER(geof:sfContains(?countyGeometry, ?damGeometry))
}
```

### Find Dams in States

```sparql
SELECT ?damName ?damGeometry ?stateName
WHERE {
    # Specify states
    VALUES ?inputState {
        "Ohio"
        "Kentucky"
    }
    
    # Get state geometries
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
    
    # Spatial filter
    FILTER(geof:sfContains(?stateGeometry, ?damGeometry))
}
```

## Important Notes

- **Spatial filtering**: Always do spatial filtering in SPARQL using `geof:sfContains()` rather than post-processing in Python. This is dramatically faster.
- **Dams on rivers**: Due to GIS precision limits, dams (stored as points) may not intersect river geometries exactly. Use a 30-meter buffer around rivers, but note that FRINK's QLever doesn't support `geof:buffer()` - you must buffer in GeoPandas after querying.
- **Performance**: Queries for large regions (entire states) may take up to 1 minute.
- **Data scope**: Only dam data from the National Inventory of Dams (NID) is available. Don't assume other infrastructure types are in FRINK.

## Complete Example

**Query**: "Find all dams in Ross County, Ohio"

```python
import sparql_dataframe
import geopandas as gpd
from shapely import wkt

query = '''
PREFIX schema: <https://schema.org/>
PREFIX geo: <http://www.opengis.net/ont/geosparql#>
PREFIX geof: <http://www.opengis.net/def/function/geosparql/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?damName ?damGeometry ?countyName
WHERE {
    VALUES ?inputCounty { "Ross County, Ohio" }
    
    ?county rdf:type <http://stko-kwg.geog.ucsb.edu/lod/ontology/AdministrativeRegion_2>;
            rdfs:label ?countyName;
            geo:hasGeometry/geo:asWKT ?countyGeometry.
    FILTER(STRSTARTS(STR(?county), "http://stko-kwg.geog.ucsb.edu/lod/resource/"))
    FILTER(STRSTARTS(LCASE(STR(?countyName)), LCASE(?inputCounty)))
    
    ?dam schema:provider "https://nid.usace.army.mil"^^<https://schema.org/url>;
         schema:name ?damName;
         geo:hasGeometry/geo:asWKT ?damGeometry.
    FILTER(STRSTARTS(STR(?dam), "https://geoconnex.us/ref/dams/"))
    
    FILTER(geof:sfContains(?countyGeometry, ?damGeometry))
}
'''

endpoint_url = "https://frink.apps.renci.org/federation/sparql"
df = sparql_dataframe.get(endpoint_url, query)

# Convert to GeoDataFrame
wkt_col = [c for c in df.columns if 'geometry' in c.lower() or 'geom' in c.lower()][0]
df['geometry'] = df[wkt_col].apply(wkt.loads)
gdf = gpd.GeoDataFrame(df, geometry='geometry', crs='EPSG:4326')

print(f"Found {len(gdf)} dams in Ross County, Ohio")
for _, row in gdf.iterrows():
    print(f"- {row['damName']}")
```
