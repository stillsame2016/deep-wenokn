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
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.types import Command, Interrupt
from langgraph.checkpoint.memory import InMemorySaver

from deepagents_cli.skills.middleware import SkillsMiddleware
from deepagents_cli.config import settings

# Set the wide layout of the web page
st.set_page_config(layout="wide", page_title="WEN-OKN")

# Set up the title
st.markdown("### &nbsp; WEN-OKN: Dive into Data, Never Easier")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "agent" not in st.session_state:
    st.session_state.agent = None
if "skills_loaded" not in st.session_state:
    st.session_state.skills_loaded = False

# Configuration section (moved to main area)
with st.container():
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("### Configuration")
    with col2:
        temperature = st.slider("Temperature", 0.0, 1.0, 0.3, 0.1, key="temp_slider")

# Initialize LLM
@st.cache_resource
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

# Initialize agent with skills
def initialize_agent():
    if st.session_state.agent is None:
        llm = get_llm()
        
        # Setup directories like the CLI does
        assistant_id = "agent"
        current_directory = os.getcwd()
        
        # For Streamlit Cloud, use local skills folder
        local_skills_dir = Path(current_directory) / "skills"
        
        # Try to use local skills folder first, fallback to CLI settings
        if local_skills_dir.exists():
            skills_dir = str(local_skills_dir)
            project_skills_dir = None
            st.success(f"✅ Using local skills folder: {skills_dir}")
        else:
            # Fallback to CLI settings
            skills_dir = settings.ensure_user_skills_dir(assistant_id)
            project_skills_dir = settings.get_project_skills_dir()
            st.info(f"📁 Using CLI skills directory: {skills_dir}")
        
        # Initialize skills middleware
        skills_middleware = SkillsMiddleware(
            skills_dir=skills_dir,
            assistant_id=assistant_id,
            project_skills_dir=project_skills_dir,
        )
        
        # Create middleware like the CLI
        agent_middleware = [
            skills_middleware,
            ShellToolMiddleware(
                workspace_root=current_directory,
                execution_policy=HostExecutionPolicy(),
                env=os.environ,
            ),
        ]
        
        # Enhanced system prompt
        system_prompt = """
        You are WEN-OKN, a helpful AI assistant with access to specialized skills for data analysis and research.
        
        ## Your Capabilities
        You have access to various skills for:
        - Geographic data analysis (counties, states, census tracts, watersheds)
        - Environmental data (PFAS contamination, water systems, facilities)
        - Infrastructure data (power plants, dams, coal mines)
        - Statistical data from Google Data Commons
        - File operations and web research
        
        ## How to Help Users
        1. **Understand their needs** - Ask clarifying questions if needed
        2. **Use appropriate skills** - When a user's request matches a skill's domain, use that skill
        3. **Provide clear explanations** - Explain what data you're accessing and why
        4. **Be helpful and accurate** - Always provide useful, actionable information
        
        ## File Operations
        - All file paths must be absolute paths (e.g., `/tmp/test/file.txt`)
        - Use the working directory to construct absolute paths
        - Never use relative paths
        
        ## Skills Usage
        - Skills are automatically loaded and available as tools
        - Use skills when the user's request matches their domain
        - The SkillsMiddleware handles skill discovery and execution
        
        Always be helpful, accurate, and explain your reasoning when using specialized skills.
        """
        
        # Create the agent with custom tools and skills middleware
        st.session_state.agent = create_deep_agent(
            llm,
            system_prompt=system_prompt,
            middleware=agent_middleware,
        )
        
        # Add checkpointer like the CLI
        st.session_state.agent.checkpointer = InMemorySaver()
        
        # Store skills info for reference
        st.session_state.skills_loaded = True
        st.session_state.skills_directory = skills_dir

# Initialize agent
initialize_agent()

# Skills information section
if st.session_state.skills_loaded and "skills_directory" in st.session_state:
    with st.expander("📋 Available Skills", expanded=False):
        skills_dir = st.session_state.skills_directory
        st.success(f"✅ Skills loaded from: {skills_dir}")
        
        # Show available skills from directory
        try:
            skills_path = Path(skills_dir)
            if skills_path.exists():
                skill_folders = [f for f in skills_path.iterdir() if f.is_dir() and (f / "SKILL.md").exists()]
                
                if skill_folders:
                    cols = st.columns(min(3, len(skill_folders)))
                    for i, skill_folder in enumerate(skill_folders):
                        with cols[i % 3]:
                            skill_name = skill_folder.name
                            skill_file = skill_folder / "SKILL.md"
                            
                            st.markdown(f"**{skill_name}**")
                            
                            # Read first few lines of skill description
                            try:
                                with open(skill_file, 'r', encoding='utf-8') as f:
                                    lines = f.readlines()[:2]
                                    for line in lines:
                                        if line.strip() and not line.startswith('#'):
                                            st.markdown(f"  {line.strip()}")
                            except:
                                st.markdown("  *Skill description unavailable*")
                else:
                    st.info("No skills found in the skills directory")
            else:
                st.warning("Skills directory not found")
        except Exception as e:
            st.error(f"Error reading skills: {str(e)}")
elif not st.session_state.skills_loaded:
    st.info("🔄 Loading skills...")

# Display chat messages
def display_messages():
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant":
                st.markdown(message["content"])
            else:
                st.markdown(message["content"])

# Handle user input
def handle_user_input(user_input):
    # Add user message to chat
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # Get assistant response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                # Create human message
                human_msg = HumanMessage(content=user_input)
                
                # Get response from agent
                response = st.session_state.agent.invoke({"messages": [human_msg]})
                
                # Extract assistant response
                if response and "messages" in response:
                    assistant_response = response["messages"][-1].content
                else:
                    assistant_response = "I apologize, but I couldn't generate a response. Please try again."
                
                # Display assistant response
                st.markdown(assistant_response)
                
                # Add to message history
                st.session_state.messages.append({"role": "assistant", "content": assistant_response})
                
            except Exception as e:
                error_message = f"An error occurred: {str(e)}"
                st.error(error_message)
                st.session_state.messages.append({"role": "assistant", "content": error_message})

# Main chat interface
st.markdown("## Chat Interface")

# Display existing messages
display_messages()

# Chat input
user_input = st.chat_input("Ask me anything about data analysis, geographic information, or research...")

if user_input:
    handle_user_input(user_input)

# Clear chat button
if st.button("Clear Chat"):
    st.session_state.messages = []
    st.rerun()

