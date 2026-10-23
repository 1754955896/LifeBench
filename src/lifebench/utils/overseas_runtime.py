"""Explicit CLI selection of map services; AMap is the default."""
import importlib
import json
from pathlib import Path
import sys

from .overseas_maptool import OverseasMapMaintenanceTool


def add_map_arguments(parser):
    parser.add_argument("--map-tool", choices=("amap", "overseas"), default="amap",
                        help="地图工具（默认 amap；overseas 使用海外地图）")
    parser.add_argument("--map-config", default=None,
                        help="海外地图 JSON 配置文件（--map-tool overseas 时必填）")


def validate_map_arguments(parser, args):
    if args.map_tool == "overseas":
        if not args.map_config:
            parser.error("--map-tool overseas requires --map-config")
        path = Path(args.map_config).resolve()
        if not path.is_file():
            parser.error("Map configuration file does not exist")
        try:
            config = json.loads(path.read_text(encoding="utf-8-sig"))
            OverseasMapMaintenanceTool(**_map_options(config))
        except (ValueError, OSError, TypeError) as exc:
            parser.error("Invalid map configuration (%s)" % type(exc).__name__)
        args.map_config = str(path)
    elif args.map_config:
        parser.error("--map-config requires --map-tool overseas")
    return args


def map_cli_arguments(args):
    """Forward explicit options to subprocesses without startup hooks or env vars."""
    result = ["--map-tool", args.map_tool]
    if args.map_config:
        result.extend(["--map-config", args.map_config])
    return result


def configure_map_tool(args):
    if args.map_tool == "amap":
        return
    config = json.loads(Path(args.map_config).read_text(encoding="utf-8-sig"))
    return install_overseas_maptool(config)


def _map_options(config):
    if not isinstance(config, dict) or not isinstance(config.get("map_tool", config), dict):
        raise ValueError("Map configuration must be an object")
    options = dict(config.get("map_tool", config))
    options.pop("provider", None)
    options.pop("api_key", None)
    return options


def install_overseas_maptool(config):
    """Select overseas services explicitly for this dedicated generation process."""
    options = _map_options(config)

    class ConfiguredOverseasMapTool(OverseasMapMaintenanceTool):
        def __init__(self, *args, **kwargs):
            # Explicit legacy call arguments remain valid, config supplies new
            # endpoint/country settings without changing old constructors.
            configured = dict(options)
            positional = ("api_key", "cache_expire_seconds", "persona_address_data",
                          "requests_per_second", "rate_limit_retries")
            for name in positional[:len(args)]:
                configured.pop(name, None)
            configured.update(kwargs)
            super().__init__(*args, **configured)

    # Validate configuration now; startup errors must not silently select AMap.
    ConfiguredOverseasMapTool()
    module = importlib.import_module("src.lifebench.utils.maptool")
    original_tool = module.MapMaintenanceTool
    module.MapMaintenanceTool = ConfiguredOverseasMapTool
    for name, loaded in list(sys.modules.items()):
        if name.startswith("src.lifebench.") and loaded is not None:
            if getattr(loaded, "MapMaintenanceTool", None) is original_tool:
                loaded.MapMaintenanceTool = ConfiguredOverseasMapTool

    # The legacy simulation exporter assumes GCJ-02. In this dedicated overseas
    # process every map input/output is WGS-84, including unlabelled legacy POIs.
    coordinates = importlib.import_module("src.lifebench.event.simulation.geolocation.coordinates")
    export = importlib.import_module("src.lifebench.event.simulation.geolocation.export")
    old_convert = coordinates.gcj02_to_wgs84
    old_point = coordinates.attach_wgs84
    old_records = coordinates.attach_record_wgs84

    def identity(longitude, latitude):
        return float(longitude), float(latitude)

    def attach_point(point):
        point["coordinate_system"] = "WGS-84"
        return old_point(point)

    def attach_records(records):
        if isinstance(records, dict):
            records["coordinate_system"] = "WGS-84"
        return old_records(records)

    replacements = ((old_convert, identity), (old_point, attach_point), (old_records, attach_records))
    # The geolocation package re-exports these helpers during import. Update
    # those already-bound aliases as well as the originating module.
    for name, loaded in list(sys.modules.items()):
        if name.startswith("src.lifebench.") and loaded is not None:
            for attribute, value in list(vars(loaded).items()):
                for old, new in replacements:
                    if value is old:
                        setattr(loaded, attribute, new)
                        break
    export.COORDINATE_SYSTEM = "WGS-84"
    return ConfiguredOverseasMapTool
