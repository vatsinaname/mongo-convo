import os
import requests
from typing import Optional

# langChain imports
from langchain.llms import OpenAI  #can be replaced with Groq compatible LLM
from langchain.chains import LLMChain


def call_groq_api(prompt: str, model: str = "mixtral-8x7b-32768", max_tokens: int = 256) -> Optional[str]:
    """
    Call the Groq API for LLM completions.
    Requires GROQ_API_KEY in environment variables.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not set in environment.")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        raise RuntimeError(f"Groq API error: {response.status_code} {response.text}")


def get_basic_langchain_chain():
    """
    Returns a basic LangChain LLMChain (OpenAI placeholder, replace with Groq-compatible LLM as needed).
    """
    llm = OpenAI(temperature=0)
    chain = LLMChain(llm=llm)
    return chain
