"""Backend registry. A new provider is a new module in this package plus one line here."""

from importlib import import_module

from mcp_servers_cli.llm import LLMBackend

# Backend name -> (module, class). Each backend is named after the SDK it imports.
BACKENDS: dict[str, tuple[str, str]] = {
    "ollama": ("mcp_servers_cli.backends.ollama", "OllamaBackend"),
    "anthropic": ("mcp_servers_cli.backends.anthropic", "AnthropicBackend"),
}


def create_backend(name: str, model: str) -> LLMBackend:
    """Import a backend only once chosen, so an optional SDK stays optional."""
    if name not in BACKENDS:
        raise ValueError(f"Unknown backend '{name}'. Available: {sorted(BACKENDS)}")
    module_name, class_name = BACKENDS[name]
    try:
        module = import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name != name:
            raise
        raise ModuleNotFoundError(
            f"The {name} backend needs an optional dependency: install mcp-servers-cli[{name}]",
            name=name,
        ) from exc
    return getattr(module, class_name)(model=model)
