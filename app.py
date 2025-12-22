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

from keplergl import keplergl

# Import mapping libraries
try:
    import geopandas as gpd
    import pandas as pd
    GEOPANDAS_AVAILABLE = True
except ImportError:
    GEOPANDAS_AVAILABLE = False

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
        model="glm-4.6",
        base_url="https://ellm.nrp-nautilus.io/v1",
        api_key=os.environ.get("NRP_API_KEY"),
        temperature=0,
    )

# Function to display all GeoDataFrames as layers on a single map
def display_all_layers_map():
    """Display all GeoDataFrames as layers on a single interactive map."""
    if not st.session_state.geodataframes:
        st.info("No geographic data available yet. Start a conversation to generate maps!")
        return
    
    try:

        map_config = keplergl(st.session_state.geodataframes, height=400)
        
        import pydeck as pdk
        
        # Calculate overall bounds from all geodataframes
        all_bounds = []
        for gdf in st.session_state.geodataframes.values():
            if gdf.crs and gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs(epsg=4326)
            all_bounds.append(gdf.total_bounds)
        
        # Calculate center and zoom
        if all_bounds:
            min_x = min(b[0] for b in all_bounds)
            min_y = min(b[1] for b in all_bounds)
            max_x = max(b[2] for b in all_bounds)
            max_y = max(b[3] for b in all_bounds)
            
            center_lat = (min_y + max_y) / 2
            center_lon = (min_x + max_x) / 2
            
            lat_diff = max_y - min_y
            lon_diff = max_x - min_x
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
        else:
            center_lat, center_lon, zoom = 39.8, -98.6, 4  # Center of US
        
        # Create layers for each geodataframe
        layers = []
        colors = [
            [0, 100, 200, 140],
            [200, 0, 100, 140],
            [100, 200, 0, 140],
            [200, 100, 0, 140],
            [100, 0, 200, 140],
        ]
        
        for idx, (name, gdf) in enumerate(st.session_state.geodataframes.items()):
            if gdf.crs and gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs(epsg=4326)
            
            geojson = json.loads(gdf.to_json())
            color = colors[idx % len(colors)]
            
            layer = pdk.Layer(
                "GeoJsonLayer",
                geojson,
                opacity=0.6,
                stroked=True,
                filled=True,
                extruded=False,
                wireframe=True,
                get_fill_color=color,
                get_line_color=[255, 255, 255],
                line_width_min_pixels=2,
                pickable=True,
            )
            layers.append(layer)
        
        # Set the viewport
        view_state = pdk.ViewState(
            latitude=center_lat,
            longitude=center_lon,
            zoom=zoom,
            pitch=0,
        )
        
        # Render the map
        r = pdk.Deck(
            layers=layers,
            initial_view_state=view_state,
            tooltip={"text": "{properties}"},
            map_style="mapbox://styles/mapbox/streets-v12",
        )
        
        st.pydeck_chart(r, use_container_width=True, height=700)
        
    except ImportError:
        # Fallback if pydeck not available
        st.warning("⚠️ PyDeck not available. Install with: `pip install pydeck`")
        
        # Simple fallback using streamlit map
        all_points = []
        for gdf in st.session_state.geodataframes.values():
            if gdf.crs and gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs(epsg=4326)
            centroids = gdf.geometry.centroid
            all_points.extend([{"lat": p.y, "lon": p.x} for p in centroids])
        
        if all_points:
            st.map(pd.DataFrame(all_points))
    
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
            system_prompt = f"""You are WEN-OKN, a geographic data assistant specializing in spatial analysis.

## YOUR SKILLS LOCATION

Working directory: /mount/src/deep-wenokn/
Skills directory: skills/

Available skills: {', '.join(skills_list) if skills_list else 'None found'}

## HOW TO USE ANY SKILL

**Step 1: Read the skill's documentation**
Each skill has a SKILL.md file that explains how to use it.

CRITICAL: Use the SHELL tool with cat command and RELATIVE paths:
- ✅ CORRECT: shell tool → `cat skills/<skill_name>/SKILL.md`
- ❌ WRONG: read_file tool (doesn't work with our paths)
- ❌ WRONG: absolute paths

**Step 2: Follow the instructions in SKILL.md**
Each SKILL.md file contains:
- What the skill does
- How to use it
- Example code or commands
- Expected outputs

**Step 3: Execute as instructed**
Follow whatever approach the SKILL.md describes. Different skills work differently.

**Step 4: CRITICAL - Save output to user-specific directory**
Your user-specific temporary directory is: {st.session_state.temp_dir}

When saving files:
- ✅ SAVE TO: {st.session_state.temp_dir}/filename.geojson
- ✅ SAVE TO: {st.session_state.temp_dir}/filename.csv
- ❌ DON'T USE: /tmp/filename.geojson (shared across users - privacy issue!)

Example:
```python
gdf.to_file('{st.session_state.temp_dir}/result.geojson', driver='GeoJSON')
df.to_csv('{st.session_state.temp_dir}/result.csv', index=False)
```

The system will automatically:
1. Load these files into the user's session as map layers
2. Display on interactive map
3. Delete the temporary files (for security)

## GENERAL BEST PRACTICES

1. Always read SKILL.md first using: shell tool → `cat skills/<skill_name>/SKILL.md`
2. Follow the exact instructions in the SKILL.md file
3. Save ALL output files to: {st.session_state.temp_dir}/
4. Use inline Python execution when possible: `python3 -c "..."`
5. Avoid creating .py files unless necessary
6. NEVER save to /tmp/ - always use the user-specific directory above

## EXAMPLE WORKFLOW

User asks: "Find the Muskingum River"

Your approach:
1. Use shell tool: `cat skills/rivers/SKILL.md`
2. Read and understand the instructions
3. Follow the approach described in SKILL.md
4. Save output to {st.session_state.temp_dir}/muskingum_river.geojson
5. The system will automatically load it as a map layer
6. Explain what you found

Remember: Each skill is unique. Always read its SKILL.md file first and follow those specific instructions. Always save to the user-specific directory for privacy and security."""
            
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
    except RuntimeError as e:
        if "cannot be called from a running event loop" in str(e):
            import nest_asyncio
            nest_asyncio.apply()
            asyncio.run(handle_user_input_async(user_input))
        else:
            raise

# ========== SIDEBAR ==========
with st.sidebar:
    st.markdown("## 🌍 WEN-OKN")
    st.markdown("---")
    
    # Navigation buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💬 Conversation", use_container_width=True, type="primary" if st.session_state.current_view == "conversation" else "secondary"):
            st.session_state.current_view = "conversation"
            st.rerun()
    with col2:
        if st.button("🗺️ Map", use_container_width=True, type="primary" if st.session_state.current_view == "map" else "secondary"):
            st.session_state.current_view = "map"
            st.rerun()
    
    st.markdown("---")
    
    # Show layer count
    num_layers = len(st.session_state.geodataframes)
    st.markdown(f"**Map Layers:** {num_layers}")
    
    if st.button("🗑️ Clear All Data", use_container_width=True):
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
    # Map View
    st.markdown("### 🗺️ Geographic Data Layers")
    
    if not st.session_state.geodataframes:
        st.info("No map layers yet. Start a conversation to generate geographic data!")
    else:
        # Display the combined map
        display_all_layers_map()
        
        st.markdown("---")
        st.markdown("### 📊 Layer Management")
        
        # Layer controls
        for name, gdf in st.session_state.geodataframes.items():
            with st.expander(f"🗺️ {name.replace('_', ' ').title()} ({len(gdf)} features)"):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    # Download GeoJSON
                    geojson_str = gdf.to_json()
                    st.download_button(
                        label="📥 GeoJSON",
                        data=geojson_str,
                        file_name=f"{name}.geojson",
                        mime="application/json",
                        key=f"download_geojson_{name}",
                        use_container_width=True
                    )
                
                with col2:
                    # Download CSV
                    csv_df = gdf.drop(columns=['geometry'])
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
                
                # Show attribute table
                st.markdown("**Attributes:**")
                display_df = gdf.drop(columns=['geometry'])
                st.dataframe(display_df, use_container_width=True, height=200)
