import streamlit as st
import os
import asyncio
import json
from pathlib import Path
from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI
from langchain.agents.middleware import (
    HostExecutionPolicy,
    ShellToolMiddleware,
)
from langchain_core.messages import HumanMessage, ToolMessage, AIMessage
from langgraph.types import Command

from deepagents_cli.skills.middleware import SkillsMiddleware
from deepagents_cli.config import settings

# Import mapping libraries
try:
    import geopandas as gpd
    import pandas as pd
    GEOPANDAS_AVAILABLE = True
except ImportError:
    GEOPANDAS_AVAILABLE = False

# Set the wide layout of the web page
st.set_page_config(layout="wide", page_title="WEN-OKN")

# Set up the title
st.markdown("### 🌍 WEN-OKN: Dive into Data, Never Easier")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "agent" not in st.session_state:
    st.session_state.agent = None
if "skills_loaded" not in st.session_state:
    st.session_state.skills_loaded = False
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []
if "last_geodataframe" not in st.session_state:
    st.session_state.last_geodataframe = None
if "last_geojson_file" not in st.session_state:
    st.session_state.last_geojson_file = None
if "skills_documentation" not in st.session_state:
    st.session_state.skills_documentation = {}

# Helper function to scan and cache skills documentation
def scan_skills_documentation():
    """Scan the skills directory and cache SKILL.md documentation."""
    if st.session_state.skills_documentation:
        return st.session_state.skills_documentation
    
    current_directory = os.getcwd()
    skills_dir = Path(current_directory) / "skills"
    
    if not skills_dir.exists():
        return {}
    
    skills_docs = {}
    
    # Scan for all SKILL.md files
    for skill_dir in skills_dir.iterdir():
        if skill_dir.is_dir():
            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                try:
                    with open(skill_md, 'r', encoding='utf-8') as f:
                        content = f.read()
                        skills_docs[skill_dir.name] = {
                            'path': str(skill_md),
                            'content': content,
                            'short_desc': content.split('\n')[0] if content else "No description"
                        }
                except Exception as e:
                    st.warning(f"Could not read {skill_md}: {e}")
    
    st.session_state.skills_documentation = skills_docs
    return skills_docs

# Configuration section
with st.container():
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("### ⚙️ Configuration")
    with col2:
        temperature = st.slider("Temperature", 0.0, 1.0, 0.3, 0.1, key="temp_slider")

# Initialize LLM
def get_llm():
    return ChatOpenAI(
        model="mimo-v2-flash",
        base_url="https://api.xiaomimimo.com/v1",
        api_key=st.secrets.get("XIAOMI_API_KEY", os.getenv("XIAOMI_API_KEY", "")),
        temperature=st.session_state.get("temp_slider", 0.3),
        top_p=0.95,
        streaming=True,
        stop=None,
        frequency_penalty=0,
        presence_penalty=0,
        extra_body={
            "thinking": {"type": "disabled"}
        }
    )

# Helper function to display GeoDataFrame on map
def display_geodataframe_map(gdf, title="Geographic Data"):
    """Display a GeoDataFrame on an interactive map."""
    if gdf is None or len(gdf) == 0:
        st.warning("No geographic data to display")
        return
    
    try:
        # Ensure we have a geometry column
        if 'geometry' not in gdf.columns:
            st.error("No geometry column found in the data")
            return
        
        # Convert to EPSG:4326 (WGS84) if not already
        if gdf.crs and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)
        
        # Get bounds for the map
        bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
        center_lat = (bounds[1] + bounds[3]) / 2
        center_lon = (bounds[0] + bounds[2]) / 2
        
        # Calculate zoom level based on bounds
        lat_diff = bounds[3] - bounds[1]
        lon_diff = bounds[2] - bounds[0]
        max_diff = max(lat_diff, lon_diff)
        
        if max_diff > 10:
            zoom = 5
        elif max_diff > 5:
            zoom = 6
        elif max_diff > 2:
            zoom = 7
        elif max_diff > 1:
            zoom = 8
        else:
            zoom = 9
        
        # Create a container for the map
        with st.container():
            st.markdown(f"#### 🗺️ {title}")
            
            # Display summary stats
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Features", len(gdf))
            with col2:
                st.metric("Center Lat", f"{center_lat:.4f}")
            with col3:
                st.metric("Center Lon", f"{center_lon:.4f}")
            
            # Try to use pydeck for better visualization
            try:
                import pydeck as pdk
                
                # Convert to GeoJSON
                geojson = json.loads(gdf.to_json())
                
                # Create pydeck layer
                layer = pdk.Layer(
                    "GeoJsonLayer",
                    geojson,
                    opacity=0.6,
                    stroked=True,
                    filled=True,
                    extruded=False,
                    wireframe=True,
                    get_fill_color=[0, 100, 200, 140],
                    get_line_color=[255, 255, 255],
                    line_width_min_pixels=1,
                    pickable=True,
                )
                
                # Set the viewport
                view_state = pdk.ViewState(
                    latitude=center_lat,
                    longitude=center_lon,
                    zoom=zoom,
                    pitch=0,
                )
                
                # Render the map
                r = pdk.Deck(
                    layers=[layer],
                    initial_view_state=view_state,
                    tooltip={"text": "{properties}"},
                    map_style="mapbox://styles/mapbox/light-v10",
                )
                
                st.pydeck_chart(r)
                
            except ImportError:
                # Fallback to simpler map visualization
                # Extract centroids for point-based map
                gdf_centroids = gdf.copy()
                gdf_centroids['geometry'] = gdf_centroids.geometry.centroid
                
                # Create dataframe with lat/lon
                map_df = pd.DataFrame({
                    'lat': gdf_centroids.geometry.y,
                    'lon': gdf_centroids.geometry.x,
                })
                
                # Use Streamlit's built-in map
                st.map(map_df, zoom=zoom)
            
            # Display attribute table
            with st.expander("📊 View Attribute Table"):
                # Drop geometry for display
                display_df = gdf.drop(columns=['geometry'])
                st.dataframe(display_df, use_container_width=True)
            
            # Download options
            col1, col2 = st.columns(2)
            with col1:
                # GeoJSON download
                geojson_str = gdf.to_json()
                st.download_button(
                    label="📥 Download as GeoJSON",
                    data=geojson_str,
                    file_name="geographic_data.geojson",
                    mime="application/json",
                )
            with col2:
                # CSV download (without geometry)
                csv_df = gdf.drop(columns=['geometry'])
                csv_str = csv_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download as CSV",
                    data=csv_str,
                    file_name="geographic_data.csv",
                    mime="text/csv",
                )
    
    except Exception as e:
        st.error(f"Error displaying map: {str(e)}")
        import traceback
        with st.expander("🔍 Error Details"):
            st.code(traceback.format_exc())

# Function to check for and display GeoJSON files
def check_and_display_geojson_files():
    """Check for GeoJSON files created during execution and display them."""
    if not GEOPANDAS_AVAILABLE:
        st.warning("⚠️ GeoPandas not installed. Cannot display maps. Install with: `pip install geopandas`")
        return
    
    tmp_dir = Path("/tmp")
    
    try:
        geojson_files = sorted(tmp_dir.glob("*.geojson"), key=lambda x: x.stat().st_mtime, reverse=True)
        
        if geojson_files:
            # Display the most recent GeoJSON file
            most_recent = geojson_files[0]
            
            try:
                gdf = gpd.read_file(most_recent)
                if gdf is not None and len(gdf) > 0:
                    display_geodataframe_map(gdf, title=f"📍 {most_recent.stem.replace('_', ' ').title()}")
                    st.session_state.last_geodataframe = gdf
                    st.session_state.last_geojson_file = str(most_recent)
                    
                    # Show info about other files if they exist
                    if len(geojson_files) > 1:
                        with st.expander(f"📁 {len(geojson_files)-1} other GeoJSON file(s) available"):
                            for gf in geojson_files[1:]:
                                st.text(f"• {gf.name}")
                else:
                    st.warning(f"⚠️ GeoJSON file {most_recent.name} is empty")
            except Exception as e:
                st.error(f"❌ Could not read {most_recent.name}: {str(e)}")
                import traceback
                with st.expander("🔍 Error Details"):
                    st.code(traceback.format_exc())
        else:
            # No GeoJSON files found - this is OK, just don't show anything
            pass
            
    except Exception as e:
        st.error(f"❌ Error checking for GeoJSON files: {str(e)}")

# Initialize agent
def initialize_agent():
    if st.session_state.agent is None:
        try:
            llm = get_llm()
            
            # Setup directories
            assistant_id = "agent"
            current_directory = os.getcwd()
            local_skills_dir = Path(current_directory) / "skills"
            
            # Scan skills documentation to know what's available
            skills_docs = scan_skills_documentation()
            
            # Just list the skill names, not the full content
            skills_list = list(skills_docs.keys()) if skills_docs else []
            
            # Use local skills directory
            if local_skills_dir.exists():
                skills_dir = str(local_skills_dir)
                project_skills_dir = None
                st.info(f"✅ Loading skills from: {skills_dir}")
            else:
                skills_dir = settings.ensure_user_skills_dir(assistant_id)
                project_skills_dir = settings.get_project_skills_dir()
                st.info(f"ℹ️ Loading skills from: {skills_dir}")
            
            # Initialize skills middleware
            skills_middleware = SkillsMiddleware(
                skills_dir=skills_dir,
                assistant_id=assistant_id,
                project_skills_dir=project_skills_dir,
            )
            
            # Create middleware
            agent_middleware = [
                skills_middleware,
                ShellToolMiddleware(
                    workspace_root=current_directory,
                    execution_policy=HostExecutionPolicy(),
                    env=os.environ,
                ),
            ]
            
            # Enhanced system prompt with map visualization instructions
            system_prompt = f"""You are WEN-OKN, a geographic data assistant specializing in spatial analysis.

## CRITICAL: SKILLS DIRECTORY LOCATION

Your working directory is: /mount/src/deep-wenokn/
Your skills are in the RELATIVE path: skills/

Available skills: {', '.join(skills_list) if skills_list else 'None found'}

**ALWAYS use RELATIVE paths when accessing skills:**

✅ CORRECT: `cat skills/rivers/SKILL.md`
✅ CORRECT: `cat skills/us_counties/SKILL.md`
❌ WRONG: `cat /mount/src/deep-wenokn/skills/rivers/SKILL.md`

## HOW TO USE A SKILL:

**Step 1 - Read the skill documentation:**
```bash
cat skills/rivers/SKILL.md
```

**Step 2 - Use the SPARQL patterns from the documentation**

**Step 3 - Execute inline Python** (never create .py files)

## IMPORTANT: ALWAYS USE INLINE PYTHON EXECUTION

**DO NOT create temporary .py files** - they cause permission issues.

**ALWAYS use inline Python with shell:**

```bash
python3 -c "
import sparql_dataframe
import geopandas as gpd
from shapely import wkt
import sys

query = '''
PREFIX geo: <http://www.opengis.net/ont/geosparql#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT DISTINCT ?name ?geometry
WHERE {{
  # Your WHERE clause here
}}
'''

try:
    endpoint = 'https://frink.apps.renci.org/federation/sparql'
    df = sparql_dataframe.get(endpoint, query)
    
    if len(df) == 0:
        print('No results found')
        sys.exit(1)
    
    df['geometry'] = df['geometry'].apply(wkt.loads)
    gdf = gpd.GeoDataFrame(df, geometry='geometry', crs='EPSG:4326')
    
    gdf.to_file('/tmp/result.geojson', driver='GeoJSON')
    print(f'Success! Found {{len(gdf)}} features. Saved to /tmp/result.geojson')
except Exception as e:
    print(f'Error: {{e}}')
    sys.exit(1)
"
```

## COMMON SPARQL ENTITY TYPES:

**Counties:** `<http://stko-kwg.geog.ucsb.edu/lod/ontology/AdministrativeRegion_2>`
**States:** `<http://stko-kwg.geog.ucsb.edu/lod/ontology/AdministrativeRegion_1>`
**Rivers:** `<http://stko-kwg.geog.ucsb.edu/lod/ontology/River>`
**Power Plants:** `<http://stko-kwg.geog.ucsb.edu/lod/ontology/PowerPlant>`
**Dams:** `<http://stko-kwg.geog.ucsb.edu/lod/ontology/Dam>`
**Watersheds:** `<http://stko-kwg.geog.ucsb.edu/lod/ontology/HUC12>`

## WORKFLOW:

1. **Read skill documentation:** `cat skills/<skill_name>/SKILL.md`
2. **Build SPARQL query** using the patterns from SKILL.md
3. **Execute inline Python** with the query
4. **Save to /tmp/*.geojson** - UI auto-displays the map
5. **Explain results**

## EXAMPLE - Find Ohio River:

```bash
# Step 1: Read the skill
cat skills/rivers/SKILL.md

# Step 2: Execute query based on documentation
python3 -c "
import sparql_dataframe
import geopandas as gpd
from shapely import wkt

query = '''
PREFIX geo: <http://www.opengis.net/ont/geosparql#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT DISTINCT ?riverName ?riverGeometry
WHERE {{
  ?river rdf:type <http://stko-kwg.geog.ucsb.edu/lod/ontology/River> ;
         rdfs:label ?riverName ;
         geo:hasGeometry/geo:asWKT ?riverGeometry .
  FILTER(CONTAINS(LCASE(?riverName), 'ohio'))
}}
'''

endpoint = 'https://frink.apps.renci.org/federation/sparql'
df = sparql_dataframe.get(endpoint, query)
df['geometry'] = df['riverGeometry'].apply(wkt.loads)
gdf = gpd.GeoDataFrame(df, geometry='geometry', crs='EPSG:4326')
gdf.to_file('/tmp/ohio_river.geojson', driver='GeoJSON')
print(f'Found {{len(gdf)}} river segments')
"
```

## CRITICAL RULES:
1. ✅ USE: `cat skills/rivers/SKILL.md` (RELATIVE paths)
2. ✅ USE: `python3 -c "...inline code..."`
3. ❌ DON'T: Use absolute paths like `/mount/src/deep-wenokn/skills/`
4. ❌ DON'T: Create .py files with write_file
5. ✅ ALWAYS: Save results to /tmp/*.geojson
6. ✅ READ: skill documentation FIRST before querying

The UI will automatically detect and display any .geojson files created in /tmp!"""
            
            # Create the agent WITHOUT checkpointer
            st.session_state.agent = create_deep_agent(
                llm,
                system_prompt=system_prompt,
                middleware=agent_middleware,
            )
            
            # Store skills info
            st.session_state.skills_loaded = True
            st.session_state.skills_directory = skills_dir
            
            st.success("✅ Agent initialized successfully!")
            
        except Exception as e:
            st.error(f"❌ Failed to initialize agent: {str(e)}")
            st.exception(e)

# Initialize agent on first run
initialize_agent()

# Skills information section
if st.session_state.skills_loaded and "skills_directory" in st.session_state:
    with st.expander("📋 Available Skills", expanded=False):
        st.success(f"✅ Skills loaded from: {st.session_state.skills_directory}")
        
        skills_docs = scan_skills_documentation()
        
        if skills_docs:
            st.markdown("**Available Skills:**")
            for skill_name in sorted(skills_docs.keys()):
                st.markdown(f"• 🗺️ **{skill_name}** - `skills/{skill_name}/SKILL.md`")
        
        st.markdown("**How to use:**")
        st.markdown("Just ask for what you want, e.g.:")
        st.markdown("- \"Find Ross county in Ohio\"")
        st.markdown("- \"Show the Ohio River\"")
        st.markdown("- \"Display power plants in California\"")
        st.markdown("- \"Find watersheds in Colorado\"")
        
        if not GEOPANDAS_AVAILABLE:
            st.warning("⚠️ GeoPandas not available. Install with: `pip install geopandas`")
        
elif not st.session_state.skills_loaded:
    st.info("🔄 Loading skills...")

# Tool icons for display
TOOL_ICONS = {
    "read_file": "📖",
    "write_file": "✏️",
    "edit_file": "✂️",
    "ls": "📁",
    "glob": "📁",
    "grep": "🔍",
    "shell": "⚡",
    "execute": "🔧",
    "web_search": "🌐",
    "http_request": "🌐",
    "task": "🤖",
    "write_todos": "📋",
    "us_counties": "🗺️",
    "us_states": "🗺️",
    "power_plants": "🏭",
    "dams": "🌊",
    "watersheds": "💧",
    "rivers": "🌊",
    "census_tracts": "📊",
}

def format_tool_display(tool_name: str, args: dict) -> str:
    """Format tool call for display."""
    if tool_name == "read_file":
        file_path = args.get("file_path", "unknown")
        return f"Reading: {file_path}"
    elif tool_name == "write_file":
        file_path = args.get("file_path", "unknown")
        return f"Writing: {file_path}"
    elif tool_name == "shell":
        command = args.get("command", "unknown")
        if len(command) > 60:
            command = command[:57] + "..."
        return f"Executing: {command}"
    elif tool_name == "ls":
        path = args.get("path", ".")
        return f"Listing: {path}"
    elif tool_name in ["us_counties", "us_states", "power_plants", "dams", "watersheds", "rivers", "census_tracts"]:
        return f"Fetching {tool_name.replace('_', ' ').title()} data"
    else:
        args_str = str(args)
        if len(args_str) > 100:
            args_str = args_str[:97] + "..."
        return f"{tool_name}: {args_str}"

# Display chat messages
def display_messages():
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# Handle user input - with automatic map display
async def handle_user_input_async(user_input):
    # Add user message to chat
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # Get assistant response
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        tool_calls_container = st.container()
        
        try:
            config = {
                "metadata": {"assistant_id": "agent"},
            }
            
            # Build messages with history
            messages_with_history = []
            recent_messages = st.session_state.messages[-10:] if len(st.session_state.messages) > 10 else st.session_state.messages
            for msg in recent_messages:
                messages_with_history.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            stream_input = {"messages": messages_with_history}
            
            accumulated_text = ""
            displayed_tool_ids = set()
            tool_call_count = 0
            
            # Stream the response
            try:
                async for event in st.session_state.agent.astream(
                    stream_input,
                    config=config,
                    stream_mode="messages",
                ):
                    if isinstance(event, tuple) and len(event) >= 2:
                        message, metadata = event[0], event[1] if len(event) > 1 else {}
                        
                        if isinstance(message, HumanMessage):
                            continue
                        
                        if isinstance(message, AIMessage):
                            if hasattr(message, 'content') and isinstance(message.content, str):
                                if message.content:
                                    accumulated_text += message.content
                                    response_placeholder.markdown(accumulated_text)
                            
                            if hasattr(message, 'tool_calls') and message.tool_calls:
                                for tool_call in message.tool_calls:
                                    tool_id = tool_call.get('id')
                                    if tool_id and tool_id not in displayed_tool_ids:
                                        displayed_tool_ids.add(tool_id)
                                        tool_call_count += 1
                                        tool_name = tool_call.get('name', 'unknown')
                                        tool_args = tool_call.get('args', {})
                                        icon = TOOL_ICONS.get(tool_name, "🔧")
                                        display_str = format_tool_display(tool_name, tool_args)
                                        
                                        with tool_calls_container:
                                            st.info(f"{icon} {display_str}")
                                        
                                        if tool_call_count % 5 == 0:
                                            await asyncio.sleep(0.1)
                        
                        elif isinstance(message, ToolMessage):
                            tool_name = getattr(message, "name", "")
                            tool_content = getattr(message, "content", "")
                            
                            if isinstance(tool_content, str) and (
                                tool_content.lower().startswith("error") or
                                "failed" in tool_content.lower()
                            ):
                                with tool_calls_container:
                                    st.error(f"❌ {tool_name}: {tool_content}")
            
            except Exception as stream_error:
                st.warning("⚠️ Streaming failed, trying direct invocation...")
                
                result = await st.session_state.agent.ainvoke(
                    stream_input,
                    config=config,
                )
                
                if isinstance(result, dict) and "messages" in result:
                    last_message = result["messages"][-1]
                    if hasattr(last_message, 'content') and isinstance(last_message.content, str):
                        accumulated_text = last_message.content
                        response_placeholder.markdown(accumulated_text)
                else:
                    raise stream_error
            
            # Save final response
            if accumulated_text:
                st.session_state.messages.append({"role": "assistant", "content": accumulated_text})
            else:
                default_msg = "✅ I've processed your request. Please check the outputs above for results."
                response_placeholder.markdown(default_msg)
                st.session_state.messages.append({"role": "assistant", "content": default_msg})
            
            # IMPORTANT: Check for and display any GeoJSON files created
            check_and_display_geojson_files()
            
        except Exception as e:
            error_message = f"❌ An error occurred: {str(e)}"
            st.error(error_message)
            import traceback
            with st.expander("🔍 Error Details"):
                st.code(traceback.format_exc())
            st.session_state.messages.append({"role": "assistant", "content": error_message})

# Synchronous wrapper
def handle_user_input(user_input):
    try:
        asyncio.run(handle_user_input_async(user_input))
    except RuntimeError as e:
        if "cannot be called from a running event loop" in str(e):
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()
                asyncio.run(handle_user_input_async(user_input))
            else:
                raise
        else:
            raise

# Main chat interface
st.markdown("## 💬 Chat Interface")

# Control buttons
col1, col2, col3, col4 = st.columns([4, 1, 1, 1])
with col2:
    if st.button("🗑️ Clear", use_container_width=True):
        st.session_state.messages = []
        st.session_state.conversation_history = []
        st.rerun()
with col3:
    if st.button("🗺️ Show Last Map", use_container_width=True):
        if st.session_state.last_geojson_file and Path(st.session_state.last_geojson_file).exists():
            try:
                gdf = gpd.read_file(st.session_state.last_geojson_file)
                display_geodataframe_map(gdf, f"Map: {Path(st.session_state.last_geojson_file).stem.replace('_', ' ').title()}")
            except Exception as e:
                st.error(f"Error loading map: {e}")
        elif st.session_state.last_geodataframe is not None:
            display_geodataframe_map(st.session_state.last_geodataframe, "Last Query Results")
        else:
            st.warning("No map data available yet. Run a geographic query first!")
with col4:
    if st.button("📂 Browse Maps", use_container_width=True):
        tmp_dir = Path("/tmp")
        geojson_files = sorted(tmp_dir.glob("*.geojson"), key=lambda x: x.stat().st_mtime, reverse=True)
        
        if geojson_files:
            st.markdown("### 📂 Available GeoJSON Files")
            for gf in geojson_files:
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.text(f"📄 {gf.name}")
                with col_b:
                    if st.button("View", key=f"view_{gf.name}"):
                        try:
                            gdf = gpd.read_file(gf)
                            display_geodataframe_map(gdf, f"{gf.stem.replace('_', ' ').title()}")
                        except Exception as e:
                            st.error(f"Error: {e}")
        else:
            st.info("No GeoJSON files found in /tmp")

# Display existing messages
display_messages()

# Chat input
user_input = st.chat_input("Ask about geographic data: counties, states, rivers, power plants, watersheds...")

if user_input:
    handle_user_input(user_input)
