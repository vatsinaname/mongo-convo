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
    # try to auto detect the correct database if not set
    default_db = os.getenv("MONGO_DEFAULT_DB") or "sample_analytics"
    connection_string = st.sidebar.text_input(
        "MongoDB Connection String",
        value=os.getenv("MONGO_URI", ""),
        type="password"
    )
    db_name = st.sidebar.text_input("Database Name", value=default_db)

    # option to use LLM for query translation
    use_llm_query = st.sidebar.checkbox("Use LLM for advanced query translation", value=False)
    st.sidebar.markdown("""
    <small>If enabled, the LLM will attempt to translate your natural language question into a MongoDB query. If disabled, a rule-based approach is used.</small>
    """, unsafe_allow_html=True)

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
        # LLM query translation
        if use_llm_query:
            # compose a prompt with context and user input
            chat_history = "\n".join([
                f"{msg['role'].capitalize()}: {msg['message']}" for msg in context.get_history(5)
            ])
            llm_query_prompt = (
                f"You are a MongoDB expert assistant.\n"
                f"Conversation so far:\n{chat_history}\n"
                f"User question: {user_input}\n"
                f"Translate the user's question into a MongoDB query. "
                f"If the collection or intent is unclear, ask a clarifying question. "
                f"Return a JSON object with keys: collection, operation, query, projection, and pipeline (if aggregation)."
            )
            try:
                llm_query_response = call_groq_api(llm_query_prompt)
                st.write("**LLM Query Translation Output:**")
                st.code(llm_query_response, language="json")
                # try to parse the LLM output as query_info
                import json
                if llm_query_response:
                    try:
                        query_info = json.loads(llm_query_response)
                    except Exception:
                        st.warning("Could not parse LLM output as JSON. Falling back to rule-based translation.")
                        parsed = nl_processor.parse(user_input)
                        st.write("Parsed:", parsed)  # debug output
                        query_info = query_generator.generate(parsed)
                else:
                    st.warning("LLM did not return a response. Falling back to rule-based translation.")
                    parsed = nl_processor.parse(user_input)
                    st.write("Parsed:", parsed)  # debug output
                    query_info = query_generator.generate(parsed)
            except Exception as e:
                st.error(f"LLM Query Translation Error: {e}")
                parsed = nl_processor.parse(user_input)
                st.write("Parsed:", parsed)  # debug output
                query_info = query_generator.generate(parsed)
        else:
            parsed = nl_processor.parse(user_input)
            st.write("Parsed:", parsed)  # debug output
            query_info = query_generator.generate(parsed)
        st.write("Query Info:", query_info)  # debug output
        if not query_info.get("collection"):
            st.warning("Could not determine the collection name from your query. Please specify the collection explicitly (e.g., 'List all users from customers').")
        # exec mongodb query if possible
        mongo_result = None
        try:
            st.write(f"Connecting to DB: {db_name}")  # debug output
            st.write(f"Collection: {query_info.get('collection')}")  # debug output
            if query_info.get("operation") == "find":
                mongo_result = client.execute_query(
                    query_info["collection"],
                    query_info["query"],
                    query_info["projection"]
                )
            elif query_info.get("operation") == "count_documents":
                mongo_result = client.count_documents(
                    query_info["collection"],
                    query_info["query"]
                )
            elif query_info.get("operation") == "aggregate":
                mongo_result = client.aggregate(
                    query_info["collection"],
                    query_info.get("pipeline", [])
                )
        except Exception as e:
            st.error(f"MongoDB Error: {e}")
            st.write(f"Exception details: {e}")  # debug output
            mongo_result = f"MongoDB Error: {e}"
        st.code(str(query_info), language="python")
        st.write("**MongoDB Result:**")
        st.write(mongo_result)
        # generalised display for known collections and fields
        #if mongo_result and isinstance(mongo_result, list) and isinstance(mongo_result[0], dict):
            #st.write("**Results:**")
            #for doc in mongo_result:
                # show all projected fields for each document
                #display_fields = [k for k in doc.keys() if k != "_id"]
                #st.write(", ".join(f"{field}: {doc[field]}" for field in display_fields))
        #elif not mongo_result:
            #st.info(f"No results found in collection '{query_info['collection']}' of database '{db_name}'.")
            # extra debug- list collections and sample doc
        try:
            client_db = getattr(st.session_state.client, 'current_db', None)
            if client_db:
                collections = client_db.list_collection_names()
                st.write(f"Collections in DB: {collections}")
                if query_info["collection"] in collections:
                    collection_obj = client_db.get_collection(query_info["collection"])
                    if collection_obj:
                        sample_doc = collection_obj.find_one()
                        st.write(f"Sample doc in '{query_info['collection']}': {sample_doc}")
            else:
                st.write("No database connection available for listing collections or sample doc.")
        except Exception as e:
            st.write(f"Error listing collections or sample doc: {e}")
        # product extraction feature explanation n ui
        with st.expander("What does 'Extract product from your question (Groq LLM JSON)' do?", expanded=False):
            st.markdown("""
            This feature uses the Groq LLM to extract structured product details (like product name, category, price, etc.) from your question and returns them as a JSON object.\n
            **Use case:** If you ask about a product (e.g., "Show me details for the iPhone 15 Pro in electronics"), this tool will extract the product name, category, and other details from your question, making it easier to use this information in downstream applications or queries.
            """)
        #groq langchain chain for structured output product extraction
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
            chat_history = "\n".join([
                f"{msg['role'].capitalize()}: {msg['message']}" for msg in context.get_history(5)
            ])
            llm_prompt = f"Conversation so far:\n{chat_history}\nUser asked: {user_input}\nMongoDB result: {mongo_result}\nRespond conversationally, ask clarifying questions if needed."
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
