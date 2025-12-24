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
import uuid
import tempfile

from deepagents_cli.skills.middleware import SkillsMiddleware
from deepagents_cli.config import settings

# Import mapping libraries
try:
    import geopandas as gpd
    import pandas as pd
    GEOPANDAS_AVAILABLE = True
except ImportError:
    GEOPANDAS_AVAILABLE = False

try:
    import folium
    from folium import plugins
    from streamlit_folium import st_folium
    FOLIUM_AVAILABLE = True
except ImportError:
    FOLIUM_AVAILABLE = False

# Set the wide layout of the web page
st.set_page_config(layout="wide", page_title="WEN-OKN")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "agent" not in st.session_state:
    st.session_state.agent = None
if "skills_loaded" not in st.session_state:
    st.session_state.skills_loaded = False
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []
if "geodataframes" not in st.session_state:
    st.session_state.geodataframes = {}  # Dict: {name: gdf}
if "dataframes" not in st.session_state:
    st.session_state.dataframes = {}  # Dict: {name: df}
if "generated_code" not in st.session_state:
    st.session_state.generated_code = []  # List of code snippets
if "skills_documentation" not in st.session_state:
    st.session_state.skills_documentation = {}
if "user_session_id" not in st.session_state:
    st.session_state.user_session_id = str(uuid.uuid4())[:8]  # Unique per session
if "temp_dir" not in st.session_state:
    # Create user-specific temp directory
    st.session_state.temp_dir = tempfile.mkdtemp(prefix=f"wenokn_{st.session_state.user_session_id}_")
if "current_view" not in st.session_state:
    st.session_state.current_view = "conversation"  # "conversation" or "map"

# current_dir = os.getcwd()
# for root, dirs, files in os.walk(current_dir):
#     for file in files:
#         # Join the root path and filename to get the full path
#         full_path = os.path.join(root, file)
#         st.markdown(full_path)

# current_dir = st.session_state.temp_dir
# st.markdown(f"==================== {current_dir}")
# for root, dirs, files in os.walk(current_dir):
#     for file in files:
#         # Join the root path and filename to get the full path
#         full_path = os.path.join(root, file)
#         st.markdown(full_path)



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

# Initialize LLM
def get_llm():

    return ChatOpenAI(
        model="mimo-v2-flash",
        base_url="https://api.xiaomimimo.com/v1",
        api_key=st.secrets["XIAOMI_API_KEY"],
        temperature=st.session_state.get("temp_slider", 0.3),
        top_p=0.95,
        stream=False,
        stop=None,
        frequency_penalty=0,
        presence_penalty=0,
        extra_body={
            "thinking": {"type": "disabled"}
        }
    )

    # return ChatOpenAI(
    #     model="glm-4.6",
    #     base_url="https://ellm.nrp-nautilus.io/v1",
    #     api_key=os.environ.get("NRP_API_KEY"),
    #     temperature=0,
    # )

# Function to display all GeoDataFrames as layers on a single map
def display_all_layers_map():
    """Display all GeoDataFrames as layers on a single interactive Folium map."""
    if not st.session_state.geodataframes:
        st.info("No geographic data available yet. Start a conversation to generate maps!")
        return
    
    if not FOLIUM_AVAILABLE:
        st.error("⚠️ Folium not available. Install with: `pip install folium streamlit-folium`")
        return
    
    try:
        # Calculate overall bounds from all geodataframes
        all_bounds = []
        for gdf in st.session_state.geodataframes.values():
            if gdf.crs and gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs(epsg=4326)
            all_bounds.append(gdf.total_bounds)
        
        # Calculate center
        if all_bounds:
            min_x = min(b[0] for b in all_bounds)
            min_y = min(b[1] for b in all_bounds)
            max_x = max(b[2] for b in all_bounds)
            max_y = max(b[3] for b in all_bounds)
            
            center_lat = (min_y + max_y) / 2
            center_lon = (min_x + max_x) / 2
        else:
            center_lat, center_lon = 39.8, -98.6  # Center of US
        
        # Create the base map with multiple tile options
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=6,
            tiles=None,  # We'll add tiles manually
            control_scale=True
        )
        
        # Add multiple basemap options
        folium.TileLayer(
            tiles='OpenStreetMap',
            name='Street Map',
            overlay=False,
            control=True
        ).add_to(m)
        
        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri',
            name='Satellite',
            overlay=False,
            control=True
        ).add_to(m)
        
        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',
            attr='Esri',
            name='Topographic',
            overlay=False,
            control=True
        ).add_to(m)
        
        folium.TileLayer(
            tiles='CartoDB positron',
            name='Light',
            overlay=False,
            control=True
        ).add_to(m)
        
        # A professional, muted palette for mapping
        colors = [
            '#4E79A7', '#F28E2B', '#E15759', '#76B7B2', '#59A14F', 
            '#EDC948', '#B07AA1', '#FF9DA7', '#9C755F', '#BAB0AC',
            '#1F77B4', '#FF7F0E', '#2CA02C', '#D62728', '#9467BD', 
            '#8C564B', '#E377C2', '#7F7F7F', '#BCBD22', '#17BECF'
        ]

        colors = [
            "#1F3A5F",  # deep blue
            "#C0392B",  # strong red
            "#2E8B57",  # sea green
            "#F39C12",  # amber
            "#6C3483",  # deep purple
            "#16A085",  # teal
            "#7D6608",  # olive
            "#922B21",  # dark brick
            "#1B4F72",  # steel blue
            "#784212",  # brown
        
            "#2874A6",  # blue
            "#AF601A",  # burnt orange
            "#1E8449",  # green
            "#B03A2E",  # red
            "#5B2C6F",  # purple
            "#117864",  # dark teal
            "#9A7D0A",  # mustard
            "#512E5F",  # plum
            "#4D5656",  # dark gray
            "#0E6251",  # blue-green
        ]
        
        # Add each geodataframe as a layer
        for idx, (name, gdf) in enumerate(st.session_state.geodataframes.items()):
            # Ensure WGS84
            if gdf.crs and gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs(epsg=4326)
            
            color = colors[idx % len(colors)]
            
            # Create a feature group for this layer (allows toggling)
            feature_group = folium.FeatureGroup(name=name.replace('_', ' ').title(), show=True)
            
            # Add GeoJSON to the feature group with proper color handling
            def style_function(feature, color=color):
                return {
                    'fillColor': color,
                    'color': color,  # This is the line color
                    'weight': 1.5,
                    'fillOpacity': 0.4,
                }
            
            def highlight_function(feature):
                return {
                    'fillColor': '#FFFF00',  # Yellow
                    'color': '#000000',  # Black border
                    'weight': 2,
                    'fillOpacity': 0.7,
                }
            
            # Create tooltip with attributes (excluding geometry)
            tooltip_fields = [col for col in gdf.columns if col.lower() not in ['geometry', 'geom', 'the_geom', 'shape', 'countygeometry', 'rivergeometry', 'stategeometry', 'watershedgeometry', 'damgeometry', 'plantgeometry']]
            
            if tooltip_fields:
                tooltip = folium.GeoJsonTooltip(
                    fields=tooltip_fields,
                    aliases=[f"{field}:" for field in tooltip_fields],
                    localize=True,
                    sticky=False,
                    labels=True,
                    style="""
                        background-color: white;
                        border: 1px solid black;
                        border-radius: 3px;
                        box-shadow: 3px;
                        font-size: 11px;
                        max-width: 300px;
                        max-height: 300px;
                        overflow-y: auto;
                        padding: 8px;
                    """,
                )
            else:
                tooltip = None
            
            # Define the marker style for points
            point_marker = folium.CircleMarker(
                radius=2,           # Size in pixels
                weight=1,           # Border thickness
                fill=True,
                fill_opacity=0.7
            )

            gdf_display = gdf.copy()
            for col in gdf_display.columns:
                if pd.api.types.is_datetime64_any_dtype(gdf_display[col]):
                    gdf_display[col] = gdf_display[col].astype(str)
        
            folium.GeoJson(
                gdf_display,
                marker=point_marker,
                style_function=style_function,
                highlight_function=highlight_function,
                tooltip=tooltip,
                name=name.replace('_', ' ').title()
            ).add_to(feature_group)
            
            feature_group.add_to(m)
        
        # Add layer control with custom CSS for smaller font
        layer_control = folium.LayerControl(position='topright', collapsed=False)
        layer_control.add_to(m)
        
        # Add custom CSS to make layer control font smaller
        custom_css = """
        <style>
        .leaflet-control-layers {
            font-size: 11px !important;
        }
        .leaflet-control-layers-base label,
        .leaflet-control-layers-overlays label {
            font-size: 11px !important;
            padding: 2px 5px !important;
        }
        .leaflet-control-layers-base,
        .leaflet-control-layers-overlays {
            line-height: 1.3 !important;
        }
        </style>
        """
        m.get_root().html.add_child(folium.Element(custom_css))
        
        # Add fullscreen button
        plugins.Fullscreen(
            position='topleft',
            title='Fullscreen',
            title_cancel='Exit Fullscreen',
            force_separate_button=True
        ).add_to(m)
        
        # Add measure control
        # plugins.MeasureControl(
        #     position='topleft',
        #     primary_length_unit='kilometers',
        #     secondary_length_unit='miles',
        #     primary_area_unit='sqkilometers',
        #     secondary_area_unit='acres'
        # ).add_to(m)
        
        # Add mouse position
        plugins.MousePosition().add_to(m)
        
        # Don't add minimap - removed per user request
        # minimap = plugins.MiniMap(toggle_display=True)
        # m.add_child(minimap)
        
        # Fit bounds to show all layers
        if all_bounds:
            southwest = [min_y, min_x]
            northeast = [max_y, max_x]
            m.fit_bounds([southwest, northeast], padding=[50, 50])
        
        # Display the map
        st_folium(
            m,
            width=None,  # Use full width
            height=500,
            returned_objects=[],
            use_container_width=True
        )
        
        # Display map legend
        with st.expander("🎨 Map Legend", expanded=False):
            for idx, name in enumerate(st.session_state.geodataframes.keys()):
                color = colors[idx % len(colors)]
                # Create a small colored box for the legend
                st.markdown(f'<span style="color:{color};">⬤</span> **{name.replace("_", " ").title()}**', unsafe_allow_html=True)
    
    except Exception as e:
        st.error(f"Error displaying map: {str(e)}")
        import traceback
        with st.expander("🔍 Error Details"):
            st.code(traceback.format_exc())

# Function to load GeoJSON/CSV files into session state and clean up
def load_and_cleanup_temp_files():
    """Load any generated files into session state and clean up temp directory."""
    if not GEOPANDAS_AVAILABLE:
        return
    
    temp_dir = Path(st.session_state.temp_dir)
    
    try:
        # Check for GeoJSON files
        geojson_files = list(temp_dir.glob("*.geojson"))
        for gf in geojson_files:
            try:
                gdf = gpd.read_file(gf)
                if gdf is not None and len(gdf) > 0:
                    # Store in session state with descriptive name
                    name = gf.stem
                    st.session_state.geodataframes[name] = gdf
                    st.success(f"✅ Loaded {name} into map layers")
                
                # Delete the file after loading
                gf.unlink()
            except Exception as e:
                st.error(f"Error loading {gf.name}: {e}")
        
        # Check for CSV files
        csv_files = list(temp_dir.glob("*.csv"))
        for cf in csv_files:
            try:
                df = pd.read_csv(cf)
                if df is not None and len(df) > 0:
                    # Store in session state
                    name = cf.stem
                    st.session_state.dataframes[name] = df
                    st.success(f"✅ Loaded {name} data")
                
                # Delete the file after loading
                cf.unlink()
            except Exception as e:
                st.error(f"Error loading {cf.name}: {e}")
        
        # Check for Python files (generated code)
        py_files = list(temp_dir.glob("*.py"))
        for pf in py_files:
            try:
                with open(pf, 'r') as f:
                    code = f.read()
                    st.session_state.generated_code.append({
                        'name': pf.stem,
                        'code': code,
                        'timestamp': pf.stat().st_mtime
                    })
                
                # Delete the file after loading
                pf.unlink()
            except Exception as e:
                st.error(f"Error loading {pf.name}: {e}")
                
    except Exception as e:
        st.error(f"Error checking temp files: {str(e)}")

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
            else:
                skills_dir = settings.ensure_user_skills_dir(assistant_id)
                project_skills_dir = settings.get_project_skills_dir()
            
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
            
            # Updated system prompt with user-specific temp directory
            system_prompt = f"""You are WEN-OKN, a data expert.

## CORE DIRECTIVE
You have NO internal knowledge of the file system or specific data. 
You MUST use the `shell` tool to read `SKILL.md` files to know how to perform tasks.
You MUST use Python code execution to generate results.

## YOUR SKILLS
Working directory: /mount/src/deep-wenokn/
Skills directory: skills/
Available skills: {', '.join(skills_list) if skills_list else 'None found'}

## MANDATORY PROTOCOL
1. **Explore**: When asked for a map/data, IMMEDIATELY use `shell` to read the relevant `SKILL.md`.
   - Command: `cat skills/<skill_name>/SKILL.md`
   - CRITICAL: Use the SHELL tool with cat command and RELATIVE paths:                                                                                           
   -- ✅ CORRECT: shell tool → `cat skills/<skill_name>/SKILL.md`                                                                                                           tiles=None,  # We'll add tiles manually                                                                                                         
   -- ❌ WRONG: read_file tool cat sn't work with our paths)                                                                                                            )
   -- ❌ WRONG: absolute paths            
   
2. **Execute**: Generate and run the Python code exactly as the `SKILL.md` instructs. Use inline Python execution when possible: `python3 -c ...". Avoid creating .py files unless necessary.
3. **Save**: You MUST save outputs to the user's temp directory: {st.session_state.temp_dir}/
   - Example: `gdf.to_file('{st.session_state.temp_dir}/output.geojson', driver='GeoJSON')`

## ANTI-HALLUCINATION RULES
- **DO NOT** narrate what you are going to do. Just run the tool.
- **DO NOT** say "I have saved the file" unless you have successfully executed the Python code that saves it.
- **DO NOT** guess file paths. If you haven't run the code to create the file, the file does not exist.
- **NEVER** simulate the output of a tool. If you need to know something, RUN THE TOOL.

**User Temp Directory:** {st.session_state.temp_dir}
"""
            
            # Create the agent WITHOUT checkpointer
            st.session_state.agent = create_deep_agent(
                llm,
                system_prompt=system_prompt,
                middleware=agent_middleware,
            )
            
            # Store skills info
            st.session_state.skills_loaded = True
            st.session_state.skills_directory = skills_dir
            
        except Exception as e:
            st.error(f"❌ Failed to initialize agent: {str(e)}")
            st.exception(e)

# Initialize agent on first run
initialize_agent()

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
}

def format_tool_display(tool_name: str, args: dict) -> str:
    """Format tool call for display."""
    if tool_name == "shell":
        command = args.get("command", "unknown")
        if len(command) > 60:
            command = command[:57] + "..."
        return f"Executing: {command}"
    elif tool_name == "read_file":
        file_path = args.get("file_path", "unknown")
        return f"Reading: {file_path}"
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

# Handle user input
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
            config = {"metadata": {"assistant_id": "agent"}}
            
            # Build messages with history
            messages_with_history = []
            recent_messages = st.session_state.messages[-10:] if len(st.session_state.messages) > 10 else st.session_state.messages
            for msg in recent_messages:
                messages_with_history.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

            # ==================== FIX STARTS HERE ====================
            # Append a hidden system instruction to the last user message.
            # This is sent to the LLM but NOT shown in the UI.
            if messages_with_history and messages_with_history[-1]["role"] == "user":
                messages_with_history[-1]["content"] += """
                
                SYSTEM INSTRUCTION:
                1. IGNORE previous conversation style.
                2. You MUST use the 'shell' tool to read the relevant SKILL.md file first.
                3. You MUST generate Python code and save the output to the temp directory.
                4. DO NOT answer from memory.
                """
            # ==================== FIX ENDS HERE ====================
            
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
                            
                            # if hasattr(message, 'tool_calls') and message.tool_calls:
                            #     for tool_call in message.tool_calls:
                            #         tool_id = tool_call.get('id')
                            #         if tool_id and tool_id not in displayed_tool_ids:
                            #             displayed_tool_ids.add(tool_id)
                            #             tool_call_count += 1
                            #             tool_name = tool_call.get('name', 'unknown')
                            #             tool_args = tool_call.get('args', {})
                            #             icon = TOOL_ICONS.get(tool_name, "🔧")
                            #             display_str = format_tool_display(tool_name, tool_args)
                                        
                            #             with tool_calls_container:
                            #                 st.info(f"{icon} {display_str}")
                                        
                            #             if tool_call_count % 5 == 0:
                            #                 await asyncio.sleep(0.1)

                            # Replace the tool display section (around line 522-535) with this enhanced version:

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
                                            # Show brief summary
                                            st.info(f"{icon} {display_str}")
                                            
                                            # Add expandable section to show FULL arguments
                                            with st.expander(f"🔍 Full {tool_name} details", expanded=False):
                                                if tool_name == "shell":
                                                    command = tool_args.get("command", "")
                                                    st.markdown("**Full Command:**")
                                                    st.code(command, language="bash")
                                                    
                                                    # If it's a Python command, try to pretty-print it
                                                    if command.startswith("python3 -c"):
                                                        st.markdown("**Formatted Python Code:**")
                                                        try:
                                                            # Extract the Python code from the command
                                                            python_code = command.split('python3 -c "', 1)[1].rsplit('"', 1)[0]
                                                            # Unescape and format
                                                            python_code = python_code.replace('\\n', '\n').replace('\\"', '"')
                                                            st.code(python_code, language="python")
                                                        except:
                                                            st.code(command, language="bash")
                                                else:
                                                    if tool_name == 'write_todos':
                                                        todos = tool_args.get("todos", [])
                                                        status_emoji = {
                                                            "pending": "⏳",
                                                            "in_progress": "🔄",
                                                            "completed": "✅"
                                                        }
                                                        for todo in todos:
                                                            status = todo.get("status")
                                                            content = todo.get("content")
                                                            st.markdown(f"{status_emoji[status]} {content}")
                                                    else:
                                                        st.json(tool_args)
                                                
                                                # Add download button for shell commands
                                                if tool_name == "shell" and "command" in tool_args:
                                                    st.download_button(
                                                        label="📥 Download Command",
                                                        data=tool_args["command"],
                                                        file_name=f"command_{tool_call_count}.sh",
                                                        mime="text/plain",
                                                        key=f"download_cmd_{tool_id}"
                                                    )
                                        
                                        if tool_call_count % 5 == 0:
                                            await asyncio.sleep(0.1)
                        
                        # elif isinstance(message, ToolMessage):
                        #     tool_name = getattr(message, "name", "")
                        #     tool_content = getattr(message, "content", "")

                        #     # ADD THIS DEBUG OUTPUT
                        #     with tool_calls_container:
                        #         with st.expander(f"🔍 {tool_name} output", expanded=False):
                        #             st.code(tool_content[:1000])  # Show first 1000 chars
                            
                        #     if isinstance(tool_content, str) and (
                        #         tool_content.lower().startswith("error") or
                        #         "failed" in tool_content.lower()
                        #     ):
                        #         with tool_calls_container:
                        #             st.error(f"❌ {tool_name}: {tool_content}")

                        elif isinstance(message, ToolMessage):
                            tool_name = getattr(message, "name", "")
                            tool_content = getattr(message, "content", "")

                            # Enhanced debug output with full content and better formatting
                            with tool_calls_container:
                                # Show a preview with character count
                                preview_length = 500
                                is_truncated = len(tool_content) > preview_length
                                
                                expander_title = f"🔍 {tool_name} output ({len(tool_content)} chars)"
                                if is_truncated:
                                    expander_title += " - Click to see full output"
                                
                                with st.expander(expander_title, expanded=False):
                                    # Show full content without truncation
                                    st.code(tool_content, language="python" if "import" in tool_content[:100] else "text")
                                    
                                    # Add download button for long outputs
                                    if len(tool_content) > 1000:
                                        st.download_button(
                                            label="📥 Download Full Output",
                                            data=tool_content,
                                            file_name=f"{tool_name}_output.txt",
                                            mime="text/plain",
                                            key=f"download_{tool_name}_{hash(tool_content)}"
                                        )
                            
                            # Keep the error detection
                            if isinstance(tool_content, str) and (
                                tool_content.lower().startswith("error") or
                                "failed" in tool_content.lower()
                            ):
                                with tool_calls_container:
                                    st.error(f"❌ {tool_name}: {tool_content}") 
            
            except Exception as stream_error:
                st.warning("⚠️ Streaming failed, trying direct invocation...")
                
                result = await st.session_state.agent.ainvoke(stream_input, config=config)
                
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
                default_msg = "✅ I've processed your request."
                response_placeholder.markdown(default_msg)
                st.session_state.messages.append({"role": "assistant", "content": default_msg})
            
            # Load files from temp directory and clean up
            load_and_cleanup_temp_files()
            
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
        # st.rerun()
    except RuntimeError as e:
        if "cannot be called from a running event loop" in str(e):
            import nest_asyncio
            nest_asyncio.apply()
            asyncio.run(handle_user_input_async(user_input))
            # st.rerun()
        else:
            raise

# ========== SIDEBAR ==========
with st.sidebar:
    # st.markdown("## 🌍 WEN-OKN")
    
    # Add custom CSS for button styling
    st.markdown("""
        <style>
        /* Style for primary buttons */
        div.stButton > button[kind="primary"] {
            background-color: #1e3a8a !important;
            color: white !important;
            border: none !important;
        }
        div.stButton > button[kind="primary"]:hover {
            background-color: #1e40af !important;
        }
        /* Style for secondary buttons */
        div.stButton > button[kind="secondary"] {
            background-color: #e5e7eb !important;
            color: #374151 !important;
            border: 1px solid #d1d5db !important;
        }
        div.stButton > button[kind="secondary"]:hover {
            background-color: #d1d5db !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # st.markdown("---")
    
    # Navigation buttons
    # col1, col2 = st.columns(2)
    # with col1:
    if st.button("Conversation", use_container_width=True, type="primary" if st.session_state.current_view == "conversation" else "secondary"):
        st.session_state.current_view = "conversation"
        st.rerun()
    # with col2:
    if st.button("Map & Data", use_container_width=True, type="primary" if st.session_state.current_view == "map" else "secondary"):
        st.session_state.current_view = "map"
        st.rerun()
    
    # st.markdown("---")
    
    # Show layer count
    # num_layers = len(st.session_state.geodataframes)
    # st.markdown(f"**Map Layers:** {num_layers}")
    
    if st.button("Clear All Data", use_container_width=True):
        st.session_state.geodataframes = {}
        st.session_state.dataframes = {}
        st.session_state.generated_code = []
        st.session_state.messages = []
        st.rerun()

# ========== MAIN CONTENT AREA ==========

if st.session_state.current_view == "conversation":
    # Conversation View
    st.markdown("### 💬 Chat with WEN-OKN")
    
    # Display existing messages
    display_messages()
    
    # Chat input
    user_input = st.chat_input("Ask about geographic data: counties, states, rivers, power plants, watersheds...")
    
    if user_input:
        handle_user_input(user_input)

elif st.session_state.current_view == "map":
    
    # Check if we have any data at all
    has_geodata = len(st.session_state.geodataframes) > 0
    has_tabledata = len(st.session_state.dataframes) > 0
    
    if not has_geodata and not has_tabledata:
        st.info("No data yet. Start a conversation to generate maps and data tables!")
    else:
        # ========== MAP SECTION ==========
        # Display the combined map
        if has_geodata:
            display_all_layers_map()
        
            st.markdown("---")
            st.markdown("### 📊 Layer Management")
            
            # Layer controls
            for name, gdf in st.session_state.geodataframes.items():
                with st.expander(f"🗺️ {name.replace('_', ' ').title()} ({len(gdf)} features)"):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        # Download GeoJSON
                        # geojson_str = gdf.to_json()
    
                        # Download GeoJSON - convert datetime columns to strings first
                        gdf_copy = gdf.copy()
                        # Convert all datetime/timestamp columns to ISO format strings
                        for col in gdf_copy.columns:
                            if pd.api.types.is_datetime64_any_dtype(gdf_copy[col]):
                                gdf_copy[col] = gdf_copy[col].astype(str)
                        
                        geojson_str = gdf_copy.to_json()
                        
                        st.download_button(
                            label="📥 GeoJSON",
                            data=geojson_str,
                            file_name=f"{name}.geojson",
                            mime="application/json",
                            key=f"download_geojson_{name}",
                            use_container_width=True
                        )
                    
                    with col2:
                        # Download CSV (exclude geometry columns)
                        csv_df = gdf.drop(columns=[col for col in gdf.columns if col.lower() in ['geometry', 'geom', 'the_geom', 'shape']], errors='ignore')
                        csv_str = csv_df.to_csv(index=False)
                        st.download_button(
                            label="📥 CSV",
                            data=csv_str,
                            file_name=f"{name}.csv",
                            mime="text/csv",
                            key=f"download_csv_{name}",
                            use_container_width=True
                        )
                    
                    with col3:
                        # Delete layer
                        if st.button("🗑️ Delete", key=f"delete_{name}", use_container_width=True):
                            del st.session_state.geodataframes[name]
                            st.rerun()
                    
                    # Show attribute table (exclude geometry columns)
                    st.markdown("**Attributes:**")
                    display_df = gdf.drop(columns=[col for col in gdf.columns if col.lower() in ['geometry', 'geom', 'the_geom', 'shape']], errors='ignore')
                    st.dataframe(display_df, use_container_width=True, height=200)
        
        # ========== DATA TABLES SECTION ==========
        if has_tabledata:
            if has_geodata:
                st.markdown("---")  # Separator between map and tables
            
            st.markdown("### 📊 Data Tables")
            
            # Display statistics summary
            # total_rows = sum(len(df) for df in st.session_state.dataframes.values())
            # st.caption(f"{len(st.session_state.dataframes)} tables · {total_rows:,} total rows")
            
            # Display each dataframe
            for name, df in st.session_state.dataframes.items():
                with st.expander(f"📋 {name.replace('_', ' ').title()} ({len(df)} rows × {len(df.columns)} columns)", expanded=False):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        # Download CSV
                        csv_str = df.to_csv(index=False)
                        st.download_button(
                            label="📥 CSV",
                            data=csv_str,
                            file_name=f"{name}.csv",
                            mime="text/csv",
                            key=f"download_table_{name}",
                            use_container_width=True
                        )
                    
                    with col2:
                        # Download Excel
                        try:
                            import io
                            buffer = io.BytesIO()
                            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                                df.to_excel(writer, index=False, sheet_name=name[:31])  # Excel sheet name limit
                            st.download_button(
                                label="📥 Excel",
                                data=buffer.getvalue(),
                                file_name=f"{name}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key=f"download_excel_{name}",
                                use_container_width=True
                            )
                        except ImportError:
                            st.caption("(openpyxl not installed)")
                    
                    with col3:
                        # Delete table
                        if st.button("🗑️ Delete", key=f"delete_table_{name}", use_container_width=True):
                            del st.session_state.dataframes[name]
                            st.rerun()
                    
                    # # Show basic statistics
                    # st.markdown("**Quick Stats:**")
                    # stat_cols = st.columns(4)
                    # with stat_cols[0]:
                    #     st.metric("Rows", f"{len(df):,}")
                    # with stat_cols[1]:
                    #     st.metric("Columns", len(df.columns))
                    # with stat_cols[2]:
                    #     numeric_cols = df.select_dtypes(include=['number']).columns
                    #     st.metric("Numeric", len(numeric_cols))
                    # with stat_cols[3]:
                    #     missing = df.isnull().sum().sum()
                    #     st.metric("Missing", f"{missing:,}")
                    
                    # Display the dataframe with formatting
                    st.markdown("**Data Preview:**")
                    st.dataframe(
                        df,
                        use_container_width=True,
                        height=min(400, len(df) * 35 + 38)  # Dynamic height based on rows
                    )
                    
                    # Optional: Show column types
                    # with st.expander("📋 Column Info"):
                    #     col_info = pd.DataFrame({
                    #         'Column': df.columns,
                    #         'Type': df.dtypes.astype(str),
                    #         'Non-Null': df.notna().sum(),
                    #         'Null': df.isna().sum()
                    #     })
                    #     st.dataframe(col_info, use_container_width=True, hide_index=True)

