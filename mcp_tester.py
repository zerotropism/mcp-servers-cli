#!/usr/bin/env python3
"""
mcp_tester.py — Client MCP générique pour explorer/tester n'importe quel serveur MCP.

Usage:
    # Serveur local (stdio) — commande à lancer
    python mcp_tester.py stdio "python server.py"
    python mcp_tester.py stdio "uv run server.py"

    # Serveur distant (HTTP/SSE)
    python mcp_tester.py http https://exemple.com/mcp

    # Depuis un fichier de config (format claude_desktop_config.json / mcpServers)
    python mcp_tester.py config config.json my-server

Une fois connecté : liste tools/resources/prompts, puis mode interactif
pour appeler un tool avec des arguments JSON.

Dépendances : pip install fastmcp
"""

import os
import sys
import json
import shlex
import asyncio

from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from fastmcp.client.transports import StreamableHttpTransport


def print_section(title: str):
    print(f"\n{'─' * 50}\n{title}\n{'─' * 50}")


async def explore(client: Client):
    async with client:
        print_section("🔧 TOOLS")
        tools = await client.list_tools()
        for t in tools:
            print(f"  • {t.name} — {t.description or '(pas de description)'}")
            if t.inputSchema and t.inputSchema.get("properties"):
                for pname, pschema in t.inputSchema["properties"].items():
                    req = (
                        " (requis)"
                        if pname in t.inputSchema.get("required", [])
                        else ""
                    )
                    print(f"      - {pname}: {pschema.get('type', '?')}{req}")

        print_section("📦 RESOURCES")
        try:
            resources = await client.list_resources()
            for r in resources:
                print(f"  • {r.uri} — {r.name or ''}")
        except Exception as e:
            print(f"  (non supporté ou vide: {e})")

        print_section("💬 PROMPTS")
        try:
            prompts = await client.list_prompts()
            for p in prompts:
                print(f"  • {p.name} — {p.description or ''}")
        except Exception as e:
            print(f"  (non supporté ou vide: {e})")

        # Mode interactif
        print_section("🧪 MODE INTERACTIF")
        print("Commandes: call <tool_name> <json_args> | read <resource_uri> | quit\n")
        while True:
            try:
                cmd = input(">> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not cmd or cmd == "quit":
                break

            parts = cmd.split(maxsplit=2)
            action = parts[0]

            try:
                if action == "call" and len(parts) >= 2:
                    name = parts[1]
                    args = json.loads(parts[2]) if len(parts) > 2 else {}
                    result = await client.call_tool(name, args)
                    print(
                        json.dumps(
                            [
                                c.text if hasattr(c, "text") else str(c)
                                for c in result.content
                            ],
                            indent=2,
                            ensure_ascii=False,
                        )
                    )
                elif action == "read" and len(parts) >= 2:
                    result = await client.read_resource(parts[1])
                    print(
                        json.dumps(
                            [c.text if hasattr(c, "text") else str(c) for c in result],
                            indent=2,
                            ensure_ascii=False,
                        )
                    )
                else:
                    print(
                        'Syntaxe: call <tool_name> {"arg": "valeur"}  |  read <uri>  |  quit'
                    )
            except Exception as e:
                print(f"❌ Erreur: {e}")


def build_client(mode: str, args: list[str]) -> Client:
    if mode == "stdio":
        # ex: "python server.py" ou "uv run --directory ../x python server.py"
        parts = shlex.split(args[0])
        return Client(StdioTransport(command=parts[0], args=parts[1:]))

    if mode == "http":
        url = args[0]
        token = os.environ.get("MCP_TOKEN")
        if token:
            return Client(
                StreamableHttpTransport(
                    url, headers={"Authorization": f"Bearer {token}"}
                )
            )
        return Client(url)

    if mode == "config":
        config_path, server_name = args[0], args[1]
        config = json.loads(Path(config_path).read_text())
        servers = config.get("mcpServers", config)
        if server_name not in servers:
            print(
                f"Serveur '{server_name}' introuvable. Disponibles: {list(servers.keys())}"
            )
            sys.exit(1)
        return Client({"mcpServers": {server_name: servers[server_name]}})

    raise ValueError(f"Mode inconnu: {mode}")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    mode = sys.argv[1]
    rest = sys.argv[2:]

    client = build_client(mode, rest)
    asyncio.run(explore(client))


if __name__ == "__main__":
    main()
