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

# Skills will be loaded from local "skills" folder

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

# Sidebar for configuration
with st.sidebar:
    st.markdown("## Configuration")
    
    # Model settings
    st.markdown("### Model Settings")
    temperature = st.slider("Temperature", 0.0, 1.0, 0.3, 0.1)
    
    # Skills information
    st.markdown("### Available Skills")
    if st.session_state.skills_loaded and "available_skills" in st.session_state:
        skills_count = len(st.session_state.available_skills)
        st.success(f"✅ {skills_count} skills loaded from local folder")
        
        # Show skill list
        if st.session_state.available_skills:
            with st.expander("View Available Skills"):
                for skill in st.session_state.available_skills:
                    st.markdown(f"**{skill['name']}**")
                    # Show first few lines of description
                    lines = skill["description"].split('\n')[:3]
                    for line in lines:
                        if line.strip():
                            st.markdown(f"  {line}")
                    st.markdown("")
    else:
        st.info("🔄 Loading skills...")

# Initialize LLM
@st.cache_resource
def get_llm(temperature_value=0.3):
    return ChatOpenAI(
        model="mimo-v2-flash",
        base_url="https://api.xiaomimimo.com/v1",
        api_key=st.secrets["XIAOMI_API_KEY"],
        temperature=temperature_value,
        top_p=0.95,
        stream=False,
        stop=None,
        frequency_penalty=0,
        presence_penalty=0,
        extra_body={
            "thinking": {"type": "disabled"}
        }
    )

# Load skills from local folder
def load_local_skills():
    """Load skills from the local 'skills' folder"""
    skills_dir = Path("skills")
    
    if not skills_dir.exists():
        st.warning("⚠️ Skills folder not found. Some features may be limited.")
        return []
    
    skills = []
    try:
        for skill_folder in skills_dir.iterdir():
            if skill_folder.is_dir():
                skill_file = skill_folder / "SKILL.md"
                if skill_file.exists():
                    # Read skill description
                    with open(skill_file, 'r', encoding='utf-8') as f:
                        skill_content = f.read()
                    
                    skills.append({
                        "name": skill_folder.name,
                        "path": str(skill_folder),
                        "description": skill_content
                    })
        
        st.success(f"✅ Loaded {len(skills)} skills from local folder")
        return skills
        
    except Exception as e:
        st.error(f"❌ Error loading skills: {str(e)}")
        return []

# Initialize agent with skills
def initialize_agent():
    if st.session_state.agent is None:
        llm = get_llm(temperature)
        
        # Load skills from local folder
        skills = load_local_skills()
        
        # Build skills-aware system prompt
        skills_info = ""
        if skills:
            skills_info = "\n## Available Skills:\n"
            for skill in skills:
                # Extract first line of skill description as summary
                lines = skill["description"].split('\n')
                summary = lines[0] if lines else skill["name"]
                skills_info += f"- **{skill['name']}**: {summary}\n"
        
        system_prompt = f"""
        You are WEN-OKN, a helpful AI assistant with access to specialized skills for data analysis and research.
        
        ## Your Capabilities
        You have access to various skills for geographic data analysis, environmental information, infrastructure queries, and statistical research.{skills_info}
        
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
        - Skills are located in the local 'skills' folder
        - Each skill has its own directory with a SKILL.md file
        - Use skills when the user's request matches their domain
        - Always read the skill's SKILL.md file before using it
        
        Always be helpful, accurate, and explain your reasoning when using specialized skills.
        """
        
        # Create agent with basic middleware (skills will be accessed via file system)
        st.session_state.agent = create_deep_agent(
            llm,
            system_prompt=system_prompt,
            middleware=[
                ShellToolMiddleware(
                    execution_policy=HostExecutionPolicy.ALLOW_ALL
                )
            ]
        )
        
        # Store skills info for reference
        st.session_state.available_skills = skills
        st.session_state.skills_loaded = True

# Initialize agent
initialize_agent()

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

# Footer with helpful tips
st.markdown("---")
st.markdown("### 💡 Tips for using WEN-OKN:")
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("**🗺️ Geographic Data**")
    st.markdown("Ask about counties, states, watersheds, or environmental data by location")

with col2:
    st.markdown("**🏭 Infrastructure**")
    st.markdown("Query power plants, dams, coal mines, and other facilities")

with col3:
    st.markdown("**📊 Statistics**")
    st.markdown("Get demographic, economic, and environmental statistics")

st.markdown("**Example queries:**")
st.markdown("- \"Show me power plants in California\"")
st.markdown("- \"What are the PFAS contamination sites in Maine?\"")
st.markdown("- \"Get demographic data for New York County\"")
st.markdown("- \"Find dams in the Colorado River watershed\"")
