import streamlit as st
import os
from dotenv import load_dotenv

# load environment variables
load_dotenv()

def main():
    st.title("MongoDB Conversation Agent")
    st.write("Under Development")
    
    # basic UI elements
    st.sidebar.header("Settings")
    connection_string = st.sidebar.text_input(
        "MongoDB Connection String",
        value=os.getenv("MONGO_URI", ""),
        type="password"
    )
    
    # main chat interface placeholder
    user_input = st.text_input("Ask about your database:")
    if user_input:
        st.info("Query processing coming soon!")

if __name__ == "__main__":
    main()
