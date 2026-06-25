"""
core/llm.py

Single factory for the LLM client used across the entire project.
Swap provider by changing LLM_API_KEY, LLM_BASE_URL, and LLM_MODEL in .env —
any OpenAI-compatible provider (Groq, OpenAI, Together AI, Mistral, Fireworks…) works.
"""
from openai import OpenAI
from core.secrets import llm


def get_client() -> OpenAI:
    return OpenAI(api_key=llm.api_key, base_url=llm.base_url, timeout=15.0)


def model() -> str:
    return llm.model
