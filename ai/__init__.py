"""AI integration layer for the Personal Activity Intelligence System.

Provides LangChain-based LLM interactions through OpenRouter for
webpage summarization, daily activity processing, and weekly synthesis.

Quick usage::

    from ai.langchain_client import AIClient
"""

from ai.langchain_client import AIClient

__all__ = ["AIClient"]
