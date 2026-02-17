#!/usr/bin/env python3
"""Export Prometheus alert rules from the operational catalog.

Bead: bd-223o.4 (P4)

Generates deploy/prometheus/rules.yaml from the canonical SLO/alert
catalog defined in control_plane.app.operations.slo_alerts.

Usage::

    python scripts/export_prometheus_rules.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure src directories are on the path.
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src" / "back"))
sys.path.insert(0, str(project_root / "src"))

from control_plane.app.operations.slo_alerts import (
    DEFAULT_OPERATIONAL_CATALOG,
    build_prometheus_rule_groups,
    operational_catalog_as_dict,
)


def _yaml_dump_rules(rule_groups: list[dict]) -> str:
    """Minimal YAML serializer for Prometheus rule groups.

    Avoids requiring PyYAML as a dependency by manually formatting
    the well-known rule-group structure.
    """
    lines = ["# Auto-generated from slo_alerts.py -- do not edit manually.", "groups:"]
    for group in rule_groups:
        lines.append(f"  - name: {group['name']}")
        lines.append("    rules:")
        for rule in group["rules"]:
            lines.append(f"      - alert: {rule['alert']}")
            # Use json.dumps for expr to handle special chars.
            lines.append(f"        expr: {json.dumps(rule['expr'])}")
            lines.append(f"        for: {rule['for']}")
            lines.append("        labels:")
            for k, v in rule["labels"].items():
                lines.append(f"          {k}: {json.dumps(v)}")
            lines.append("        annotations:")
            for k, v in rule["annotations"].items():
                lines.append(f"          {k}: {json.dumps(v)}")
    return "\n".join(lines) + "\n"


def main() -> None:
    rule_groups = build_prometheus_rule_groups(DEFAULT_OPERATIONAL_CATALOG)

    out_path = project_root / "deploy" / "prometheus" / "rules.yaml"
    out_path.write_text(_yaml_dump_rules(rule_groups))
    print(f"Wrote {out_path}")

    # Also write a JSON version for programmatic consumption.
    json_path = project_root / "deploy" / "prometheus" / "rules.json"
    json_path.write_text(json.dumps({"groups": rule_groups}, indent=2) + "\n")
    print(f"Wrote {json_path}")

    # Write catalog summary.
    catalog_path = project_root / "deploy" / "prometheus" / "catalog.json"
    catalog_path.write_text(
        json.dumps(operational_catalog_as_dict(), indent=2) + "\n"
    )
    print(f"Wrote {catalog_path}")


if __name__ == "__main__":
    main()
