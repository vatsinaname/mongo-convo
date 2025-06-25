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
from ui.clarification_ui import clarification_form, clarification_window

# load environment variables
load_dotenv()

# Default projections for sample_analytics collections
DEFAULT_PROJECTIONS = {
    "customers": {"_id": 0, "username": 1, "name": 1, "email": 1, "accounts": 1, "tier_and_details": 1},
    "accounts": {"_id": 0, "account_id": 1, "limit": 1, "products": 1},
    "transactions": {"_id": 0, "account_id": 1, "transaction_count": 1, "transactions": 1},
}

# System message for LLM prompt
SAMPLE_ANALYTICS_SYSTEM_MSG = """
You are an expert MongoDB assistant. The database is 'sample_analytics' and contains these collections: 
'customers' (fields: username, name, address, birthdate, email, accounts, tier_and_details), 
'accounts' (fields: account_id, limit, products), 
'transactions' (fields: account_id, transaction_count, bucket_start_date, bucket_end_date, transactions).
Always use the correct collection and field names. If the user does not specify a projection, use the most relevant fields for the collection.
For substring or partial name matching in the 'name' field, always use the following regex format:
regex_query = {"name": {'$regex': "Input", "$options": "i"}}; projection = {"_id": 0, "name": 1}.
Replace 'Input' with the actual name or substring to match. Adhere to this format strictly in your MongoDB queries.

---
# Instructions for Output:
- Always respond with a single valid JSON object, never with single quotes, trailing commas, or markdown/code block markers.
- Do NOT include explanations, comments, or any text outside the JSON.
- Do NOT use single quotes in the JSON.
- Do NOT use curly quotes (“ ” or ‘ ’) in the JSON. Only use straight double quotes (").
- Do NOT add trailing commas.
- Do NOT wrap the JSON in markdown (no triple backticks).
- Only output the JSON object in proper indented formatting.

# Output JSON keys:
- collection: the collection name (e.g., 'customers')
- query: the MongoDB filter object
- projection: the projection object (fields to return)
- operation: one of 'find', 'count_documents', or 'aggregate'

# Example 1:
User: List all users named John
Output:
{
  "collection": "customers",
  "query": {
    "name": {
      "$regex": "John",
      "$options": "i"
    }
  },
  "projection": {
    "name": 1,
    "_id": 0
  },
  "operation": "find"
}

# Example 2:
User: How many accounts have a limit over 5000?
Output:
{
  "collection": "accounts",
  "query": {
    "limit": { "$gt": 5000 }
  },
  "projection": {
    "account_id": 1,
    "limit": 1,
    "_id": 0
  },
  "operation": "count_documents"
}

# Example 3:
User: Show all transactions for account_id 12345
Output:
{
  "collection": "transactions",
  "query": {
    "account_id": 12345
  },
  "projection": {
    "account_id": 1,
    "transactions": 1,
    "_id": 0
  },
  "operation": "find"
}

---
Translate the user's question into a MongoDB query. If the collection or intent is unclear, make your best guess. Return only a single valid JSON object as shown above.
"""

def extract_json_from_text(text: str, debug=False, st_warn=None):
    """
    Extract the first complete valid JSON object from a string, even if surrounded by text or markdown.
    Uses a stack-based approach to find the first top-level {...} block with balanced braces.
    Tries to parse as soon as a balanced block is found. If parsing fails, continues searching.
    If st_warn is provided, shows a Streamlit warning if auto-fix is used.
    Returns the parsed dict, or None if not found.
    Use the following regex format for substring matching regex_query = {"name": {"$regex": "Input", "$options": "i"}}
    projection = {"_id": 0, "name": 1}
    """
    import re
    import json
    if not text:
        return None
    # removing markdown code block markers
    text = re.sub(r'```[a-zA-Z]*', '', text)
    # converting single to double quotes for JSON keys/values not perfect for nested quotes
    text = re.sub(r"'([a-zA-Z0-9_]+)'", r'"\\1"', text)
    # replacing curly quotes with straight
    text = text.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
    # removing newlines and excessive whitespace inside JSON blocks to help parser
    text = re.sub(r'([\{\}\[\],:])\s*\n+\s*', r'\1', text)
    text = re.sub(r'\n+', ' ', text)
    # find the first top level block using a stack
    start = None
    stack = []
    for i, c in enumerate(text):
        if c == '{':
            if not stack:
                start = i
            stack.append('{')
        elif c == '}':
            if stack:
                stack.pop()
                if not stack and start is not None:
                    json_str = text[start:i+1]
                    try:
                        return json.loads(json_str)
                    except Exception as e:
                        if debug:
                            print(f"Failed to parse JSON: {json_str}\nError: {e}")
                        # try to auto fix by adding a closing brace if missing
                        if json_str.count('{') > json_str.count('}'):
                            fixed_json_str = json_str + '}'
                            try:
                                result = json.loads(fixed_json_str)
                                if st_warn:
                                    st_warn("Auto-fixed LLM JSON by adding a closing brace. Please check LLM output quality.")
                                return result
                            except Exception as e2:
                                if debug:
                                    print(f"Failed to auto-fix JSON: {fixed_json_str}\nError: {e2}")
                    # continue searching for next
    return None

def main():
    st.title("MongoDB Conversation Agent")
    st.write("Chat with your MongoDB using natural language.")

    # sidebar for settings
    st.sidebar.header("MongoDB Conversational Agent")
    st.sidebar.markdown("""
    **Project Workflow:**
    - Enter a natural language query (e.g., "List all users named Rishabh").
    - The agent translates your question into a MongoDB query using either a rule-based or LLM-driven approach.
    - If the LLM needs clarification, you'll see a follow-up question and a special input box for your answer.
    - Results are fetched live from your MongoDB Atlas database and shown below.
    - You can also extract product details or ask for conversational explanations.
    
    **Key Features:**
    - Hybrid rule-based + LLM query translation
    - Context-aware conversation and follow-ups
    - Live MongoDB query execution and debugging
    - Product extraction and diagnostics
    
    **Challenges:**
    - Robustly parsing natural language to MongoDB queries
    - Handling ambiguous or incomplete user input
    - Ensuring LLM output is always valid
    - Maintaining context for multi-turn conversations
    """)
    
    default_db = os.getenv("MONGO_DEFAULT_DB") or "sample_analytics"
    db_name = default_db

    # LLM checkbox and warning moved to main page
    use_llm_query = st.checkbox("Use LLM for advanced query translation", value=False)
    st.markdown("<small>If enabled, the LLM will attempt to translate your natural language question into a MongoDB query. If disabled, a rule-based approach is used.</small>", unsafe_allow_html=True)

    # initialise session state for context
    if "context" not in st.session_state:
        st.session_state.context = ContextManager()
    if "client" not in st.session_state and os.getenv("MONGO_URI"):
        mongo_uri = os.getenv("MONGO_URI") or ""
        st.session_state.client = MongoDBClient(mongo_uri)
        st.session_state.client.connect_to_database(db_name)

    nl_processor = NLProcessor()
    query_generator = QueryGenerator()
    context = st.session_state.context
    client = st.session_state.get("client", None)

    # main query input with button
    with st.form(key="main_query_form", clear_on_submit=False):
        user_input = st.text_input("Ask about your database:", key="main_query_input", disabled=not bool(client))
        run_query = st.form_submit_button("Run Query", disabled=not bool(client))

    clarification_needed = st.session_state.get("clarification_needed", False)
    clarification_question = st.session_state.get("clarification_question", "")
    clarification_prev_query = st.session_state.get("clarification_prev_query", "")
    clarification_response = ""
    clarification_submitted = False
    if clarification_needed and clarification_question:
        clarification_response, clarification_submitted = clarification_window(clarification_question, clarification_prev_query)

    clarification_sentence = None
    # main query logic only run if button pressed and not in clarification mode
    if run_query and user_input and client is not None and not clarification_needed:
        context.add_message("user", user_input)
        # LLM query translation
        if use_llm_query:
            # compose a prompt with context, system message, and user input
            chat_history = "\n".join([
                f"{msg['role'].capitalize()}: {msg['message']}" for msg in context.get_history(5)
            ])
            llm_query_prompt = (
                f"{SAMPLE_ANALYTICS_SYSTEM_MSG}\n"
                f"Conversation so far:\n{chat_history}\n"
                f"User question: {user_input}\n"
                f"Translate the user's question into a MongoDB query. "
                f"If the collection or intent is unclear think what the user might mean based on your understanding and return the MongoDB query first.\n"
                f"Return only a JSON object with keys: collection, operation, query, projection."
                f"Do not use 'name': 'John'. Always use the regex format as shown."
            )
            try:
                llm_query_response = call_groq_api(llm_query_prompt)
                st.write("**LLM Query Translation Output:**")
                st.code(llm_query_response, language="json")
                # try to extract and parse the JSON from the LLM output
                if llm_query_response:
                    # Show raw LLM output for debugging
                    st.expander("LLM Raw Output / Debug").write(llm_query_response)
                    query_info = extract_json_from_text(llm_query_response, debug=True, st_warn=st.warning)
                    # simple clarification detection
                    clarification_keywords = ["would you like", "do you want", "should I", "can I", "could you", "please specify", "which", "what kind", "narrow down", "filter further"]
                    clarification_sentence = None
                    if llm_query_response:
                        for sentence in llm_query_response.split(". "):
                            if "?" in sentence or any(kw in sentence.lower() for kw in clarification_keywords):
                                clarification_sentence = sentence.strip()
                                break
                    if not query_info:
                        st.warning("Could not extract valid JSON from LLM output. Falling back to rule-based translation.")
                        # show attempted JSON blocks for debugging
                        import re
                        matches = re.findall(r'\{[\s\S]*?\}', llm_query_response)
                        if matches:
                            st.expander("Attempted JSON blocks").write(matches)
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
            st.write("[DEBUG] Rule-based parsed:", parsed)  # TEMP DEBUG
            st.write("[DEBUG] Rule-based query_info:", query_info)  # TEMP DEBUG
        st.write("Query Info:", query_info)  # debug output
        # ensure all required keys are present for MongoDB execution
        collection_name = query_info.get("collection")
        if "projection" not in query_info or not query_info["projection"]:
            # always set a default projection for known collections
            if collection_name and collection_name in DEFAULT_PROJECTIONS:
                st.warning(f"LLM output missing or empty 'projection' field. Using default for {collection_name}.")
                query_info["projection"] = DEFAULT_PROJECTIONS[collection_name]
            else:
                # default show 'name' and '_id' if possible
                st.warning("LLM output missing 'projection' field. Using default: {'name': 1, '_id': 0}.")
                query_info["projection"] = {"name": 1, "_id": 0}
        if not query_info.get("collection"):
            st.warning("Could not determine the collection name from your query. Please specify the collection explicitly (e.g., 'List all users from customers').")
        # --- Clarification logic: trigger immediately if needed ---
        if not collection_name or clarification_sentence:
            st.session_state["clarification_needed"] = True
            st.session_state["clarification_question"] = clarification_sentence or "Could not determine the collection name from your query. Please specify the collection explicitly."
            st.session_state["clarification_prev_query"] = user_input
            st.stop()
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
                st.warning("Aggregation pipeline is not supported in this app.")
                mongo_result = "Aggregation pipeline is not supported."
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
            if client_db is not None:
                collections = client_db.list_collection_names()
                st.write(f"Collections in DB: {collections}")
                if query_info["collection"] in collections:
                    collection_obj = client_db.get_collection(query_info["collection"])
                    if collection_obj is not None:
                        sample_doc = collection_obj.find_one()
                        st.write(f"Sample doc in '{query_info['collection']}': {sample_doc}")
            else:
                st.write("No database connection available for listing collections or sample doc.")
        except Exception as e:
            st.write(f"Error listing collections or sample doc: {e}")
        # Removed product extraction feature (UI and logic)
        # Groq LangChain chain for structured output product extraction
        if st.checkbox("Extract product details from your question (Groq LLM JSON)", key="extract_product_checkbox_main"):
            try:
                chain = get_groq_chat_chain(prompt_template=product_prompt, output_parser=product_json_parser)
                product_json = chain.invoke({"input": user_input})
                st.write("**Extracted Product JSON:**")
                st.json(product_json)
                context.add_message("agent", str(product_json))
            except Exception as e:
                st.error(f"Groq LangChain Error: {e}")
                context.add_message("agent", f"Groq LangChain Error: {e}")
        # Always show LLM conversational output after MongoDB result
        chat_history = "\n".join([
            f"{msg['role'].capitalize()}: {msg['message']}" for msg in context.get_history(5)
        ])
        llm_prompt = f"Conversation so far:\n{chat_history}\nUser asked: {user_input}\nMongoDB result: {mongo_result}\nRespond conversationally, ask clarifying questions if needed."
        try:
            llm_response = call_groq_api(llm_prompt)
            clarification_keywords = ["would you like", "do you want", "should I", "can I", "could you", "please specify", "which", "what kind", "narrow down", "filter further"]
            clarification_sentence = None
            if llm_response:
                for sentence in llm_response.split(". "):
                    if "?" in sentence or any(kw in sentence.lower() for kw in clarification_keywords):
                        clarification_sentence = sentence.strip()
                        break
            if clarification_sentence:
                st.session_state["clarification_needed"] = True
                st.session_state["clarification_question"] = clarification_sentence
            st.write("**LLM Response:**")
            st.write(llm_response)
            context.add_message("agent", llm_response or "(No response)")
        except Exception as e:
            st.error(f"LLM Error: {e}")
            context.add_message("agent", f"LLM Error: {e}")

    # clarification logic only run if clarification form submitted
    if clarification_submitted and clarification_response and client is not None:
        # add the clarification as a user message
        context.add_message("user", clarification_response)
        # reset clarification state
        st.session_state["clarification_needed"] = False
        st.session_state["clarification_question"] = ""
        st.session_state["clarification_prev_query"] = ""
        # rerun the main query logic with the clarification as the latest message
        # LLM query translation
        if use_llm_query:
            # compose a prompt with context, system message, and user input
            chat_history = "\n".join([
                f"{msg['role'].capitalize()}: {msg['message']}" for msg in context.get_history(5)
            ])
            llm_query_prompt = (
                f"{SAMPLE_ANALYTICS_SYSTEM_MSG}\n"
                f"Conversation so far:\n{chat_history}\n"
                f"User question: {clarification_response}\n"
                f"Translate the user's question into a MongoDB query. "
                f"If the collection or intent is unclear think what the user might mean based on your understanding and return the MongoDB query first.\n"
                f"Return only a JSON object with keys: collection, operation, query, projection."
                f"Do not use 'name': 'John'. Always use the regex format as shown."            
            )
            try:
                llm_query_response = call_groq_api(llm_query_prompt)
                st.write("**LLM Query Translation Output:**")
                st.code(llm_query_response, language="json")
                # try to extract and parse the JSON from the LLM output
                if llm_query_response:
                    # show raw LLM output for debugging
                    st.expander("LLM Raw Output / Debug").write(llm_query_response)
                    query_info = extract_json_from_text(llm_query_response, debug=True, st_warn=st.warning)
                    if not query_info:
                        st.warning("Could not extract valid JSON from LLM output. Falling back to rule-based translation.")
                        # show attempted JSON blocks for debugging
                        import re
                        matches = re.findall(r'\{[\s\S]*?\}', llm_query_response)
                        if matches:
                            st.expander("Attempted JSON blocks").write(matches)
                        parsed = nl_processor.parse(clarification_response)
                        st.write("Parsed:", parsed)  # debug output
                        query_info = query_generator.generate(parsed)
                else:
                    st.warning("LLM did not return a response. Falling back to rule-based translation.")
                    parsed = nl_processor.parse(clarification_response)
                    st.write("Parsed:", parsed)  # debug output
                    query_info = query_generator.generate(parsed)
            except Exception as e:
                st.error(f"LLM Query Translation Error: {e}")
                parsed = nl_processor.parse(clarification_response)
                st.write("Parsed:", parsed)  # debug output
                query_info = query_generator.generate(parsed)
        else:
            parsed = nl_processor.parse(clarification_response)
            st.write("Parsed:", parsed)  # debug output
            query_info = query_generator.generate(parsed)
            st.write("[DEBUG] Rule-based parsed:", parsed)  # TEMP DEBUG
            st.write("[DEBUG] Rule-based query_info:", query_info)  # TEMP DEBUG
        st.write("Query Info:", query_info)  # debug output
        # ensure all required keys are present for MongoDB execution
        collection_name = query_info.get("collection")
        if "projection" not in query_info or not query_info["projection"]:
            # always set a default projection for known collections
            if collection_name and collection_name in DEFAULT_PROJECTIONS:
                st.warning(f"LLM output missing or empty 'projection' field. Using default for {collection_name}.")
                query_info["projection"] = DEFAULT_PROJECTIONS[collection_name]
            else:
                # default show 'name' and '_id' if possible
                st.warning("LLM output missing 'projection' field. Using default: {'name': 1, '_id': 0}.")
                query_info["projection"] = {"name": 1, "_id": 0}
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
                st.warning("Aggregation pipeline is not supported in this app.")
                mongo_result = "Aggregation pipeline is not supported."
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
            if client_db is not None:
                collections = client_db.list_collection_names()
                st.write(f"Collections in DB: {collections}")
                if query_info["collection"] in collections:
                    collection_obj = client_db.get_collection(query_info["collection"])
                    if collection_obj is not None:
                        sample_doc = collection_obj.find_one()
                        st.write(f"Sample doc in '{query_info['collection']}': {sample_doc}")
            else:
                st.write("No database connection available for listing collections or sample doc.")
        except Exception as e:
            st.write(f"Error listing collections or sample doc: {e}")
        # Removed product extraction feature (UI and logic)
        # Groq LangChain chain for structured output product extraction
        if st.checkbox("Extract product details from your question (Groq LLM JSON)", key="extract_product_checkbox_clarification"):
            try:
                chain = get_groq_chat_chain(prompt_template=product_prompt, output_parser=product_json_parser)
                product_json = chain.invoke({"input": clarification_response})
                st.write("**Extracted Product JSON:**")
                st.json(product_json)
                context.add_message("agent", str(product_json))
            except Exception as e:
                st.error(f"Groq LangChain Error: {e}")
                context.add_message("agent", f"Groq LangChain Error: {e}")
        # Always show LLM conversational output after MongoDB result (clarification flow)
        chat_history = "\n".join([
            f"{msg['role'].capitalize()}: {msg['message']}" for msg in context.get_history(5)
        ])
        llm_prompt = f"Conversation so far:\n{chat_history}\nUser asked: {clarification_response}\nMongoDB result: {mongo_result}\nRespond conversationally, ask clarifying questions if needed."
        try:
            llm_response = call_groq_api(llm_prompt)
            clarification_keywords = ["would you like", "do you want", "should I", "can I", "could you", "please specify", "which", "what kind", "narrow down", "filter further"]
            clarification_sentence = None
            if llm_response:
                for sentence in llm_response.split(". "):
                    if "?" in sentence or any(kw in sentence.lower() for kw in clarification_keywords):
                        clarification_sentence = sentence.strip()
                        break
            if clarification_sentence:
                st.session_state["clarification_needed"] = True
                st.session_state["clarification_question"] = clarification_sentence
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
