"""
LLM provider factory.

Select the active provider via LLM_PROVIDER in .env.  Only the package for the
chosen provider needs to be installed; the imports are lazy (inside each branch)
so a missing optional package will not break other providers.

Supported providers
-------------------
openai          langchain-openai   ChatOpenAI / AzureChatOpenAI
anthropic        langchain-anthropic ChatAnthropic
google_genai     langchain-google-genai ChatGoogleGenerativeAI
azure_openai     langchain-openai   AzureChatOpenAI
mistralai        langchain-mistralai ChatMistralAI
"""

import logging

from langchain_core.language_models.chat_models import BaseChatModel

from app.core.config import settings

logger = logging.getLogger(__name__)

_SUPPORTED_PROVIDERS = [
    "openai",
    "anthropic",
    "google_genai",
    "azure_openai",
    "mistralai",
]


def get_llm() -> BaseChatModel:
    """Instantiate and return the configured LLM provider."""
    provider = settings.LLM_PROVIDER.lower().strip()
    model = settings.LLM_MODEL
    api_key = settings.LLM_API_KEY
    temperature = settings.LLM_TEMPERATURE
    max_tokens = settings.LLM_MAX_TOKENS
    streaming = settings.LLM_STREAMING

    logger.debug(
        "Initializing LLM provider=%s model=%s temperature=%s streaming=%s",
        provider,
        model,
        temperature,
        streaming,
    )

    if provider == "openai":
        from langchain_openai import ChatOpenAI  # noqa: PLC0415

        return ChatOpenAI(
            model=model,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=streaming,
        )

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic  # noqa: PLC0415

        return ChatAnthropic(
            model=model,
            anthropic_api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=streaming,
        )

    if provider == "google_genai":
        from langchain_google_genai import ChatGoogleGenerativeAI  # noqa: PLC0415

        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

    if provider == "azure_openai":
        from langchain_openai import AzureChatOpenAI  # noqa: PLC0415

        return AzureChatOpenAI(
            azure_deployment=model,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=streaming,
        )

    if provider == "mistralai":
        from langchain_mistralai import ChatMistralAI  # noqa: PLC0415

        return ChatMistralAI(
            model=model,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    raise ValueError(
        f"Unsupported LLM_PROVIDER: '{provider}'. "
        f"Supported providers: {', '.join(_SUPPORTED_PROVIDERS)}"
    )


def get_embeddings():
    """
    Return a LangChain Embeddings instance for the configured provider.

    Provider → model mapping (when EMBEDDING_MODEL is not explicitly set):
      openai / azure_openai → text-embedding-3-small  (1536 dims)
      google_genai          → text-embedding-004       (768 dims)
      mistralai             → mistral-embed            (1024 dims)
      anthropic             → falls back to OpenAI embeddings
    """
    provider = settings.LLM_PROVIDER.lower().strip()
    api_key = settings.LLM_API_KEY
    model = settings.EMBEDDING_MODEL  # may be empty — resolved below per-provider

    if provider in ("openai", "anthropic"):
        from langchain_openai import OpenAIEmbeddings  # noqa: PLC0415

        return OpenAIEmbeddings(
            model=model or "text-embedding-3-small",
            api_key=api_key,
        )

    if provider == "azure_openai":
        from langchain_openai import AzureOpenAIEmbeddings  # noqa: PLC0415

        return AzureOpenAIEmbeddings(
            azure_deployment=model or "text-embedding-3-small",
            api_key=api_key,
        )

    if provider == "google_genai":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings  # noqa: PLC0415

        return GoogleGenerativeAIEmbeddings(
            model=model or "models/text-embedding-004",
            google_api_key=api_key,
        )

    if provider == "mistralai":
        from langchain_mistralai import MistralAIEmbeddings  # noqa: PLC0415

        return MistralAIEmbeddings(
            model=model or "mistral-embed",
            api_key=api_key,
        )

    raise ValueError(
        f"Unsupported LLM_PROVIDER for embeddings: '{provider}'. "
        f"Supported providers: {', '.join(_SUPPORTED_PROVIDERS)}"
    )
