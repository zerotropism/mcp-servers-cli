"""Reading what a server exposes. Returns data; printing belongs to rendering."""

from dataclasses import dataclass, field

from fastmcp import Client
from mcp.shared.exceptions import MCPError
from mcp.types import METHOD_NOT_FOUND


@dataclass(frozen=True, slots=True)
class Parameter:
    name: str
    type: str
    required: bool


@dataclass(frozen=True, slots=True)
class ToolInfo:
    name: str
    description: str
    parameters: list[Parameter] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ResourceInfo:
    uri: str
    name: str
    description: str


@dataclass(frozen=True, slots=True)
class PromptInfo:
    name: str
    description: str
    arguments: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ServerInfo:
    """None means the server does not implement that capability, unlike an empty list."""

    tools: list[ToolInfo]
    resources: list[ResourceInfo] | None
    prompts: list[PromptInfo] | None


def _parameters(schema: dict | None) -> list[Parameter]:
    if not schema:
        return []
    required = set(schema.get("required", []))
    return [
        Parameter(name=name, type=spec.get("type", "?"), required=name in required)
        for name, spec in schema.get("properties", {}).items()
    ]


async def _optional(coroutine):
    """None when the server does not implement the capability; raise on anything else."""
    try:
        return await coroutine
    except MCPError as exc:
        if exc.code == METHOD_NOT_FOUND:
            return None
        raise


async def inspect_tools(client: Client) -> list[ToolInfo]:
    return [
        ToolInfo(
            name=tool.name,
            description=tool.description or "",
            parameters=_parameters(tool.input_schema),
        )
        for tool in await client.list_tools()
    ]


async def inspect_resources(client: Client) -> list[ResourceInfo] | None:
    resources = await _optional(client.list_resources())
    if resources is None:
        return None
    return [
        ResourceInfo(uri=str(r.uri), name=r.name or "", description=r.description or "")
        for r in resources
    ]


async def inspect_prompts(client: Client) -> list[PromptInfo] | None:
    prompts = await _optional(client.list_prompts())
    if prompts is None:
        return None
    return [
        PromptInfo(
            name=p.name,
            description=p.description or "",
            arguments=[a.name for a in (p.arguments or [])],
        )
        for p in prompts
    ]


async def inspect_server(client: Client) -> ServerInfo:
    """One round trip per capability, against an already-connected client."""
    return ServerInfo(
        tools=await inspect_tools(client),
        resources=await inspect_resources(client),
        prompts=await inspect_prompts(client),
    )
