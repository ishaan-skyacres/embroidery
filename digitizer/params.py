"""Parameter loading: params.yaml defaults, fabric presets, per-run overrides."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Iterable

import yaml

PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_PARAMS_FILE = PACKAGE_DIR.parent / "params.yaml"


class Params:
    """Dict-like parameter store with dotted-path access."""

    def __init__(self, data: dict[str, Any]):
        self.data = data
        self.applied_overrides: list[str] = []

    def get(self, path: str, default: Any = None) -> Any:
        node: Any = self.data
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def __getitem__(self, path: str) -> Any:
        value = self.get(path, KeyError)
        if value is KeyError:
            raise KeyError(path)
        return value

    def set(self, path: str, value: Any) -> None:
        parts = path.split(".")
        node = self.data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value

    def apply_overrides(self, overrides: dict[str, Any], label: str) -> None:
        for path, value in overrides.items():
            self.set(path, value)
            self.applied_overrides.append(f"{label}: {path} = {value}")

    def apply_fabric(self, fabric: str) -> None:
        fabrics = self.get("fabrics", {})
        if fabric not in fabrics:
            raise ValueError(f"Unknown fabric preset {fabric!r}; choose one of {', '.join(fabrics)}")
        self.set("fabric", fabric)
        self.apply_overrides(fabrics[fabric].get("overrides", {}) or {}, f"fabric {fabric}")

    def fabric_info(self) -> dict[str, Any]:
        return self.get("fabrics", {}).get(self.get("fabric", "woven"), {})

    def copy(self) -> "Params":
        p = Params(copy.deepcopy(self.data))
        p.applied_overrides = list(self.applied_overrides)
        return p

    def to_yaml(self) -> str:
        return yaml.safe_dump(self.data, sort_keys=False, allow_unicode=True)


def parse_set_value(text: str) -> Any:
    """Parse a --set value: numbers, booleans, null, lists, else string."""
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError:
        return text


def load_params(params_file: str | Path | None = None,
                fabric: str = "woven",
                sets: Iterable[str] = (),
                hoop: str | None = None,
                knockdown: bool = False) -> Params:
    with open(DEFAULT_PARAMS_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    params = Params(data)
    if params_file:
        with open(params_file, "r", encoding="utf-8") as f:
            user = yaml.safe_load(f) or {}
        params.apply_overrides(_flatten(user), f"params file {params_file}")
    params.apply_fabric(fabric)
    if hoop:
        params.set("machine.default_hoop", hoop)
    if knockdown:
        params.set("knockdown.enabled", True)
    for item in sets:
        if "=" not in item:
            raise ValueError(f"--set expects key.path=value, got {item!r}")
        key, value = item.split("=", 1)
        params.apply_overrides({key.strip(): parse_set_value(value.strip())}, "--set")
    return params


def _flatten(d: dict, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in d.items():
        path = f"{prefix}{k}"
        if isinstance(v, dict) and not path.startswith("fabrics") and k != "hoops_mm":
            out.update(_flatten(v, path + "."))
        else:
            out[path] = v
    return out


def hoop_size(params: Params, name: str | None = None) -> tuple[str, float, float]:
    """Return (name, width, height) for a hoop name like '280x200' (custom sizes allowed)."""
    name = name or params["machine.default_hoop"]
    hoops = params["machine.hoops_mm"]
    if name in hoops:
        w, h = hoops[name]
        return name, float(w), float(h)
    try:
        w, h = name.lower().split("x")
        return name, float(w), float(h)
    except ValueError as exc:
        raise ValueError(f"Hoop {name!r} is not one of {', '.join(hoops)} and is not WxH") from exc
