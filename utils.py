"""
FRS Facilities Utilities

Pre-validated functions for querying EPA's Facility Registry Service (FRS)
data from the SAWGraph knowledge graph.

DO NOT MODIFY THIS FILE - Functions are validated against specific SPARQL endpoints.
"""

import json
import requests
import geopandas as gpd
import sparql_dataframe
from shapely import wkt
from shapely.ops import linemerge
from shapely.geometry import Point

def load_FRS_facilities(state: str, naics_name: str, limit: int = 1000) -> gpd.GeoDataFrame:
    """
    Load FRS facilities for a specified state and NAICS industry.
    
    This function queries the SAWGraph knowledge graph via Qlever SPARQL endpoint
    to retrieve EPA FRS facility data with geometries.

    Args:
        state: State name - must be one of: "Illinois", "Maine", "Ohio"
        naics_name: NAICS industry name - must be from ALLOWED_NAICS list:
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
        limit: Maximum number of facilities to retrieve (default: 1000)

    Returns:
        GeoDataFrame with facility geometries and attributes including:
        - facilityName: Name of the facility
        - industryCodes: Industry classifications (comma-separated if multiple)
        - geometry: Point geometry in EPSG:4326
        - countyName: County name
        - stateName: State name
        - frsId: FRS identifier (if available)
        - triId: TRI identifier (if available)
        - rcraId: RCRA identifier (if available)
        - airId: Air program identifier (if available)
        - npdesId: NPDES identifier (if available)
        - envInterestTypes: Environmental interest types (if available)
        - facility: Facility URI

    Raises:
        ValueError: If state or NAICS name is not in the allowed lists

    Example:
        >>> sewage = load_FRS_facilities("Maine", "Sewage Treatment")
        >>> print(f"Found {len(sewage)} facilities")
        >>> print(sewage.head())
    """

    # Validate inputs
    ALLOWED_STATES = ["Illinois", "Maine", "Ohio"]
    ALLOWED_NAICS = [
        "Waste Treatment and Disposal",
        "Converted Paper Manufacturing",
        "Water Supply and Irrigation",
        "Sewage Treatment",
        "Plastics Product Manufacturing",
        "Textile and Fabric Finishing and Coating",
        "Basic Chemical Manufacturing",
        "Paint, Coating, and Adhesive Manufacturing",
        "Aerospace Product and Parts",
        "Drycleaning and Laundry Services",
        "Carpet and Upholstery Cleaning Services",
        "Solid Waste Landfill",
    ]

    if state not in ALLOWED_STATES:
        raise ValueError(f"Invalid state '{state}'. Allowed: {ALLOWED_STATES}")
    if naics_name not in ALLOWED_NAICS:
        raise ValueError(f"Invalid NAICS '{naics_name}'. Allowed: {ALLOWED_NAICS}")

    endpoint_url = "https://frink.apps.renci.org/qlever-geo/sparql"

    # SPARQL query validated for Qlever endpoint
    # The double braces {{ }} are f-string escapes that become single braces in SPARQL
    query = f"""
PREFIX kwgr: <http://stko-kwg.geog.ucsb.edu/lod/resource/>
PREFIX kwg-ont: <http://stko-kwg.geog.ucsb.edu/lod/ontology/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX fio: <http://sawgraph.spatialai.org/v1/fio#>
PREFIX frs: <http://sawgraph.spatialai.org/v1/us-frs#>
PREFIX geo: <http://www.opengis.net/ont/geosparql#>

SELECT DISTINCT 
    ?facilityName
    (GROUP_CONCAT(DISTINCT ?industryCode; separator=", ") AS ?industryCodes)
    ?facilityWKT
    ?countyName
    ?stateName
    ?frsId
    ?triId
    ?rcraId
    ?airId
    ?npdesId
    (GROUP_CONCAT(DISTINCT ?envInterestType; separator=", ") AS ?envInterestTypes)
    ?facility
WHERE {{
    ?facility a frs:FRS-Facility ;
              rdfs:label ?facilityName ;
              fio:ofIndustry/rdfs:label ?industryCode ;
              geo:hasGeometry/geo:asWKT ?facilityWKT ;
              kwg-ont:sfWithin ?county .
    ?county rdfs:label ?countyName ;
            kwg-ont:sfWithin ?state .
    ?state rdf:type kwg-ont:AdministrativeRegion_1 ;
           rdfs:label ?stateName .

    FILTER(CONTAINS(LCASE(?stateName), "{state.lower()}"))
    FILTER(CONTAINS(LCASE(?industryCode), "{naics_name.lower()}"))
    FILTER(STRSTARTS(STR(?county), "http://stko-kwg.geog.ucsb.edu/lod/resource/administrativeRegion")) .

    OPTIONAL {{ ?facility frs:hasFRSId ?frsId. }}
    OPTIONAL {{ ?facility frs:hasTRISId ?triId. }}
    OPTIONAL {{ ?facility frs:hasRCRAINFOId ?rcraId. }}
    OPTIONAL {{ ?facility frs:hasAIRId ?airId. }}
    OPTIONAL {{ ?facility frs:hasNPDESId ?npdesId. }}
    OPTIONAL {{ ?facility frs:environmentalInterestType ?envInterestType. }}
}}
GROUP BY ?facility ?facilityName ?facilityWKT ?countyName ?stateName ?industryCode ?frsId ?triId ?rcraId ?airId ?npdesId
LIMIT {limit}
"""    
    # Execute query and process results
    df = sparql_dataframe.get(endpoint_url, query)
    df = df.dropna(subset=["facilityWKT"]).copy()
    df["geometry"] = df["facilityWKT"].apply(wkt.loads)
    df = df.drop(columns=["facilityWKT"])

    # Return as GeoDataFrame with WGS84 coordinate system
    return gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")


def get_upstream_subwatersheds(river_gdf):
    """
    Given a GeoDataFrame containing a river geometry, return a GeoDataFrame
    of all upstream HUC12 sub-watersheds using the USGS WBD HUC12
    ArcGIS Feature Service.
    """
    # 1. Ensure CRS is EPSG:4326
    if river_gdf.crs is None:
        raise ValueError("river_gdf must have a CRS defined")
    if river_gdf.crs.to_epsg() != 4326:
        river_gdf = river_gdf.to_crs(epsg=4326)
    
    # 2. Get downstream outlet point of the river
    merged = linemerge(river_gdf.geometry.values)
    # Handle both LineString and MultiLineString
    if merged.geom_type == 'LineString':
        outlet_point = Point(merged.coords[-1])
    elif merged.geom_type == 'MultiLineString':
        # Use the last point of the last line
        outlet_point = Point(list(merged.geoms)[-1].coords[-1])
    else:
        raise ValueError(f"Unexpected geometry type: {merged.geom_type}")
    
    # 3. Find terminal HUC12 containing the outlet point
    params = {
        "geometry": json.dumps({
            "x": outlet_point.x,
            "y": outlet_point.y,
            "spatialReference": {"wkid": 4326}
        }),
        "geometryType": "esriGeometryPoint",
        "spatialRel": "esriSpatialRelWithin",
        "outFields": "HUC12,TOHUC",
        "f": "json"
    }
    r = requests.get(HUC12_FS_URL, params=params)
    r.raise_for_status()
    features = r.json().get("features", [])
    if not features:
        raise RuntimeError("No HUC12 found for river outlet")
    terminal_huc12 = features[0]["attributes"]["HUC12"]
    
    # 4. Traverse upstream HUC12s using TOHUC
    # Use a queue to track HUCs to process
    upstream = {terminal_huc12}
    to_process = [terminal_huc12]
    
    while to_process:
        current_huc = to_process.pop(0)
        
        # Find all HUC12s that drain TO this one (upstream neighbors)
        params = {
            "where": f"TOHUC = '{current_huc}'",
            "outFields": "HUC12,TOHUC",
            "f": "json"
        }
        r = requests.get(HUC12_FS_URL, params=params)
        r.raise_for_status()
        
        for feat in r.json().get("features", []):
            h = feat["attributes"]["HUC12"]
            if h not in upstream:
                upstream.add(h)
                to_process.append(h)
    
    # 5. Fetch geometries for all upstream HUC12s (batched)
    def chunks(lst, n=50):
        for i in range(0, len(lst), n):
            yield lst[i:i + n]
    
    all_features = []
    for batch in chunks(list(upstream)):
        where = "HUC12 IN ({})".format(",".join(f"'{h}'" for h in batch))
        params = {
            "where": where,
            "outFields": "*",
            "outSR": 4326,
            "f": "geojson"
        }
        r = requests.get(HUC12_FS_URL, params=params)
        r.raise_for_status()
        all_features.extend(r.json()["features"])
    
    # 6. Convert to GeoDataFrame
    huc12_gdf = gpd.GeoDataFrame.from_features(all_features, crs="EPSG:4326")
    return huc12_gdf

