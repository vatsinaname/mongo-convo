import streamlit as st
import os
from dotenv import load_dotenv
from src.database.mongodb_client import MongoDBClient
from src.agents.nl_processor import NLProcessor
from src.agents.query_generator import QueryGenerator
from src.agents.context_manager import ContextManager
from src.utils import call_groq_api

# load environment variables
load_dotenv()

def main():
    st.title("MongoDB Conversation Agent")
    st.write("Chat with your MongoDB using natural language!")

    # sidebar for settings
    st.sidebar.header("Settings")
    connection_string = st.sidebar.text_input(
        "MongoDB Connection String",
        value=os.getenv("MONGO_URI", ""),
        type="password"
    )
    db_name = st.sidebar.text_input("Database Name", value="test")

    # initialise session state for context
    if "context" not in st.session_state:
        st.session_state.context = ContextManager()
    if "client" not in st.session_state and connection_string:
        st.session_state.client = MongoDBClient(connection_string)
        st.session_state.client.connect_to_database(db_name)

    nl_processor = NLProcessor()
    query_generator = QueryGenerator()
    context = st.session_state.context
    client = st.session_state.get("client", None)

    # chat interface
    st.subheader("Chat")
    user_input = st.text_input("Ask about your database:")
    if user_input and client:
        context.add_message("user", user_input)
        parsed = nl_processor.parse(user_input)
        query_info = query_generator.generate(parsed)
        # just show the generated query
        st.code(str(query_info), language="python")
        # call Groq API for LLM response
        # llm_response = call_groq_api(user_input)
        # st.write(llm_response)
        # add agent response to context
        context.add_message("agent", f"Query: {query_info}")

    # show conversation history
    st.subheader("Conversation History")
    for msg in context.get_history(10):
        st.markdown(f"**{msg['role'].capitalize()}:** {msg['message']}")

if __name__ == "__main__":
    main()
