import os
import requests
from typing import Optional

# langChain imports
#from langchain.llms import OpenAI  #can be replaced with Groq compatible LLM
from langchain.chains import LLMChain
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import json


def call_groq_api(prompt: str, model: str = "llama-3.1-8b-instant", max_tokens: int = 256) -> Optional[str]:
    """
    Call the Groq API for LLM completions
    Uses llama-3.1-8b-instant as the default model
    Requires GROQ_API_KEY in environment variables
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


# langChain Groq LLM integration stub (groq is OpenAI compatible but LangChain may need a custom wrapper)
def get_basic_langchain_chain():
    """
    Returns a basic LangChain LLMChain using Groq-compatible LLM.
    Note: You may need to implement a custom LangChain LLM class for Groq if not natively supported.
    """
    # from langchain_groq import Groq 
    # llm = Groq(model="llama-3.1-8b-instant", api_key=os.getenv("GROQ_API_KEY"))
    # chain = LLMChain(llm=llm)
    # return chain
    raise NotImplementedError("Groq LLM integration for LangChain is not yet implemented.")


def get_groq_chat_chain(
    model_name: str = "llama-3.3-70b-versatile",
    temperature: float = 0.7,
    prompt_template: ChatPromptTemplate = None,
    output_parser: JsonOutputParser = None
):
    """
    Returns a LangChain chat chain using Groq LLM.
    Allows custom prompt templates and output parsers.
    """
    llm = ChatGroq(
        model_name=model_name,
        temperature=temperature
    )
    if prompt_template and output_parser:
        chain = prompt_template | llm | output_parser
    elif prompt_template:
        chain = prompt_template | llm
    else:
        chain = llm
    return chain


# Example: JSON extraction chain for product details
product_json_parser = JsonOutputParser(pydantic_object={
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "price": {"type": "number"},
        "features": {
            "type": "array",
            "items": {"type": "string"}
        }
    }
})

product_prompt = ChatPromptTemplate.from_messages([
    ("system", """Extract product details into JSON with this structure:\n    {{\n        \"name\": \"product name here\",\n        \"price\": number_here_without_currency_symbol,\n        \"features\": [\"feature1\", \"feature2\", \"feature3\"]\n    }}"""),
    ("user", "{input}")
])

def parse_product(description: str) -> dict:
    chain = get_groq_chat_chain(
        prompt_template=product_prompt,
        output_parser=product_json_parser
    )
    result = chain.invoke({"input": description})
    return result
