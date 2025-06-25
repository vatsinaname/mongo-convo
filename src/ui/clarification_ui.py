import streamlit as st

def clarification_form(clarification_question: str, key_prefix: str = "clarification"):
    """
    Renders a clarification form with a question and input box.
    Returns (clarification_response, clarification_submitted)
    """
    with st.form(key=f"{key_prefix}_form", clear_on_submit=True):
        st.info(f"LLM follow-up: {clarification_question}")
        clarification_response = st.text_input("Your clarification:", key=f"{key_prefix}_input")
        clarification_submitted = st.form_submit_button("Send Clarification")
    return clarification_response, clarification_submitted

def clarification_window(clarification_question: str):
    """
    Renders the clarification window/form for the user to answer a follow-up question.
    Returns (response, submitted) tuple.
    """
    with st.form(key="clarification_window_form", clear_on_submit=True):
        st.info(f"**Clarification needed:** {clarification_question}")
        clarification_response = st.text_input("Your answer:", key="clarification_window_response_input")
        clarification_submitted = st.form_submit_button("Submit Clarification")
    return clarification_response, clarification_submitted
