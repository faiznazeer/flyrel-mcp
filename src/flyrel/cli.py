import argparse
import json
import os
from pathlib import Path

from flyrel.config import Settings
from flyrel.models import Policy
from flyrel.server import create_server
from flyrel.store import Store


def main():
    parser = argparse.ArgumentParser(description="Flyrel local MCP server and paper controls")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("serve", help="Run the stdio MCP server")
    commands.add_parser("check", help="Inspect local config without connecting to broker APIs")
    commands.add_parser("halt", help="Disable new local paper orders")
    commands.add_parser("resume", help="Re-enable paper orders after a kill switch")
    policy = commands.add_parser("set-policy", help="Validate and install a local paper policy")
    policy.add_argument("file", type=Path)
    args = parser.parse_args()
    settings = Settings()
    if args.command == "serve":
        mcp, service = create_server(settings)
        try:
            mcp.run(transport="stdio")
        finally:
            service.close()
    elif args.command == "set-policy":
        validated = Policy.model_validate_json(args.file.read_text())
        Store(settings.state_dir)
        destination = settings.state_dir / "policy.json"
        temporary = destination.with_suffix(".tmp")
        temporary.write_text(validated.model_dump_json(indent=2) + "\n")
        os.replace(temporary, destination)
        print("Local paper policy updated")
    elif args.command == "check":
        _, service = create_server(settings)
        try:
            print(
                json.dumps(
                    {
                        "brokers": list(service.adapters),
                        "transport": "stdio",
                        "live_execution": False,
                        "state_dir": str(settings.state_dir),
                        "policy": service.policy().model_dump(mode="json"),
                        "halted": service.store.halted(),
                    },
                    indent=2,
                )
            )
        finally:
            service.close()
    else:
        store = Store(settings.state_dir)
        if args.command == "halt":
            print(json.dumps(store.halt()))
        else:
            store.resume()
            print("Local paper orders resumed")


if __name__ == "__main__":
    main()
