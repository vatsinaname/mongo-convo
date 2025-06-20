import sys
import os
from dotenv import load_dotenv
import streamlit as st
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database.mongodb_client import MongoDBClient
from agents.nl_processor import NLProcessor
from agents.query_generator import QueryGenerator
from agents.context_manager import ContextManager
from utils import call_groq_api, get_groq_chat_chain, product_prompt, product_json_parser

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
    if user_input and client is not None:
        context.add_message("user", user_input)
        parsed = nl_processor.parse(user_input)
        query_info = query_generator.generate(parsed)
        # exec mongodb query if possible
        mongo_result = None
        try:
            if query_info["operation"] == "find":
                mongo_result = client.execute_query(
                    query_info["collection"],
                    query_info["query"],
                    query_info["projection"]
                )
            elif query_info["operation"] == "count_documents":
                mongo_result = client.count_documents(
                    query_info["collection"],
                    query_info["query"]
                )
            elif query_info["operation"] == "aggregate":
                mongo_result = client.aggregate(
                    query_info["collection"],
                    query_info.get("pipeline", [])
                )
        except Exception as e:
            mongo_result = f"MongoDB Error: {e}"
        st.code(str(query_info), language="python")
        st.write("**MongoDB Result:**")
        st.write(mongo_result)
        # ex- sse groq langchain chain for structured output (product extraction)
        if st.checkbox("Extract product details from your question (Groq LLM JSON)"):
            try:
                chain = get_groq_chat_chain(prompt_template=product_prompt, output_parser=product_json_parser)
                product_json = chain.invoke({"input": user_input})
                st.write("**Extracted Product JSON:**")
                st.json(product_json)
                context.add_message("agent", str(product_json))
            except Exception as e:
                st.error(f"Groq LangChain Error: {e}")
                context.add_message("agent", f"Groq LangChain Error: {e}")
        else:
            # call Groq API for conversational LLM response
            llm_prompt = f"User asked: {user_input}\nMongoDB result: {mongo_result}\nRespond conversationally."
            try:
                llm_response = call_groq_api(llm_prompt)
                st.write("**LLM Response:**")
                st.write(llm_response)
                context.add_message("agent", llm_response or "(No response)")
            except Exception as e:
                st.error(f"LLM Error: {e}")
                context.add_message("agent", f"LLM Error: {e}")

    # show conversation history
    st.subheader("Conversation History")
    for msg in context.get_history(10):
        st.markdown(f"**{msg['role'].capitalize()}:** {msg['message']}")
    #import os
    #st.write("GROQ_API_KEY:", os.getenv("GROQ_API_KEY"))

if __name__ == "__main__":
    main()
