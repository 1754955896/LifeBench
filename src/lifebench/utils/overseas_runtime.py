"""CLI configuration only: no class replacement, import hooks, or CRS patches."""
import json
from pathlib import Path
from .locale_context import configure_settings
from .overseas_maptool import OverseasMapMaintenanceTool


def add_map_arguments(parser):
    parser.add_argument("--map-tool", choices=("amap", "overseas", "auto"), default="amap", help="地图工具，默认 amap；auto 按目标国家路由")
    parser.add_argument("--map-config", default=None, help="海外/auto 服务配置 JSON")


def _map_options(config):
    if not isinstance(config, dict) or not isinstance(config.get("map_tool", config), dict):
        raise ValueError("Map configuration must be an object")
    options = dict(config.get("map_tool", config))
    defaults = dict(options.pop("locale_defaults", {}))
    if options.get("country_code"):
        defaults.setdefault("country_code", options.pop("country_code"))
    for key in ("provider", "api_key"):
        options.pop(key, None)
    return options, defaults


def validate_map_arguments(parser, args):
    if args.map_tool != "amap":
        if not args.map_config:
            parser.error("International map mode requires --map-config")
        path = Path(args.map_config).resolve()
        try:
            options, defaults = _map_options(json.loads(path.read_text(encoding="utf-8-sig")))
            OverseasMapMaintenanceTool(country_code=defaults.get("country_code") or "GB", **options)
        except (ValueError, OSError, TypeError) as exc:
            parser.error("Invalid map configuration (%s)" % type(exc).__name__)
        args.map_config = str(path)
    elif args.map_config:
        parser.error("--map-config requires overseas or auto mode")
    return args


def map_cli_arguments(args):
    result = ["--map-tool", args.map_tool]
    if args.map_config:
        result.extend(["--map-config", args.map_config])
    return result


def configure_map_tool(args):
    if args.map_tool == "amap":
        configure_settings()
    else:
        options, defaults = _map_options(json.loads(Path(args.map_config).read_text(encoding="utf-8-sig")))
        configure_settings(args.map_tool, options, defaults)
