"""LANTERN: the Economic Offences Wing's offline analysis workstation.

A thin, readable client over a local Ollama server (and, optionally, cloud models)
used by every lesson in this lab.
"""

from lantern.config import load_config
from lantern.llm import Reply, chat, model_info

__all__ = ["Reply", "chat", "load_config", "model_info"]
