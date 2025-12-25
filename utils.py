"""
FRS Facilities Utilities

Pre-validated functions for querying EPA's Facility Registry Service (FRS)
data from the SAWGraph knowledge graph.

DO NOT MODIFY THIS FILE - Functions are validated against specific SPARQL endpoints.
"""

import geopandas as gpd
import sparql_dataframe
from shapely import wkt


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
