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
