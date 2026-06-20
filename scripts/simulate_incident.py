import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import compute_metrics
import validate as validator


SCHEMA_DIR = Path(__file__).parent.parent / "schemas"
CATALOG_DIR = Path(__file__).parent.parent / "catalog" / "servernah-iaas-compute"
PARAMS_FILE = CATALOG_DIR / "sla-parameters.yaml"
INCIDENT_SCHEMA = "incident-record.json"

SIMULATION_BASE_TIME = datetime(2025, 4, 15, 8, 0, 0, tzinfo=timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _incident_id(dt: datetime) -> str:
    date_part = dt.strftime("%Y%m%d")
    suffix = "A3F9K2"
    return f"INC-{date_part}-{suffix}"


def phase_detection(state: dict[str, Any]) -> dict[str, Any]:
    params = state["_params"]["time_based"]
    ttd = params["ttd_minutes"]
    detected_at = state["_base_time"]
    recorded_at = detected_at + timedelta(minutes=ttd)

    print(f"  Phase 1 — Detection")
    print(f"    Zabbix alert raised at:       {_iso(detected_at)}")
    print(f"    TTD:                          {ttd} min")
    print(f"    Incident recorded at:         {_iso(recorded_at)}")

    return {
        **state,
        "detected_at": detected_at,
        "recorded_at": recorded_at,
        "ttd_minutes": ttd,
    }


def phase_recording(state: dict[str, Any]) -> dict[str, Any]:
    print(f"  Phase 2 — Recording")
    print(f"    Incident start committed to InfluxDB")
    print(f"    OpenSearch service state snapshot captured")
    print(f"    PostgreSQL metadata record initialised")
    return {**state}


def phase_initiation(state: dict[str, Any]) -> dict[str, Any]:
    params = state["_params"]["time_based"]
    ttir = params["ttir_minutes"]
    recovery_initiated_at = state["recorded_at"] + timedelta(minutes=ttir)

    print(f"  Phase 3 — Recovery Initiation")
    print(f"    TTIR:                         {ttir} min")
    print(f"    Recovery initiated at:        {_iso(recovery_initiated_at)}")

    return {
        **state,
        "recovery_initiated_at": recovery_initiated_at,
        "ttir_minutes": ttir,
    }


def phase_resolution(state: dict[str, Any]) -> dict[str, Any]:
    params = state["_params"]["time_based"]
    ttcr = params["ttcr_minutes"]
    resolved_at = state["recovery_initiated_at"] + timedelta(minutes=ttcr)

    metrics = compute_metrics.run(PARAMS_FILE)

    print(f"  Phase 4 — Resolution")
    print(f"    TTCR:                         {ttcr} min")
    print(f"    Resolved at:                  {_iso(resolved_at)}")
    print(f"    Computed RTO:                 {metrics['rto']['final_minutes']} min")
    print(f"    Computed RPO:                 {metrics['rpo']['final_minutes']} min")
    print(f"    Computed MTTR:                {metrics['mttr']['adjusted_minutes']} min")

    rto_target = state["_params_raw"]["spec"]["sla_targets"]["rto_minutes"] \
        if "_params_raw" in state else 240
    rpo_target = state["_params_raw"]["spec"]["sla_targets"]["rpo_minutes"] \
        if "_params_raw" in state else 15

    rto_actual = metrics["rto"]["final_minutes"]
    rpo_actual = metrics["rpo"]["final_minutes"]

    def compliance_status(actual: float, target: float) -> str:
        if actual <= target:
            return "compliant"
        if actual <= target * 1.25:
            return "marginal"
        return "breached"

    rto_status = compliance_status(rto_actual, rto_target)
    rpo_status = compliance_status(rpo_actual, rpo_target)
    overall = "breached" if "breached" in (rto_status, rpo_status) else \
              "marginal" if "marginal" in (rto_status, rpo_status) else "compliant"

    breach_gap = round(max(rto_actual - rto_target, rpo_actual - rpo_target, 0), 2)

    return {
        **state,
        "resolved_at": resolved_at,
        "ttcr_minutes": ttcr,
        "computed_metrics": metrics,
        "rto_status": rto_status,
        "rpo_status": rpo_status,
        "overall_status": overall,
        "breach_gap_minutes": breach_gap,
    }


def phase_reporting(state: dict[str, Any]) -> dict[str, Any]:
    reported_at = state["resolved_at"] + timedelta(minutes=5)

    print(f"  Phase 5 — Reporting")
    print(f"    MTBF computed across resolved incidents")
    print(f"    Compliance status evaluated:  {state['overall_status']}")
    print(f"    Executive dashboard refreshed")
    print(f"    Reported at:                  {_iso(reported_at)}")

    return {**state, "reported_at": reported_at}


def build_incident_record(state: dict[str, Any]) -> dict[str, Any]:
    metrics = state["computed_metrics"]
    return {
        "apiVersion": "resilience/v1",
        "kind": "IncidentRecord",
        "metadata": {
            "incident_id": _incident_id(state["detected_at"]),
            "service_ref": "servernah-iaas-compute",
            "severity": "p1-critical",
            "created_by": "zabbix-alert",
        },
        "timeline": {
            "detected_at": _iso(state["detected_at"]),
            "recorded_at": _iso(state["recorded_at"]),
            "recovery_initiated_at": _iso(state["recovery_initiated_at"]),
            "resolved_at": _iso(state["resolved_at"]),
            "reported_at": _iso(state["reported_at"]),
        },
        "raw_metrics": {
            "ttd_minutes": state["ttd_minutes"],
            "ttir_minutes": state["ttir_minutes"],
            "ttcr_minutes": state["ttcr_minutes"],
        },
        "computed_metrics": {
            "rto_minutes": metrics["rto"]["final_minutes"],
            "rpo_minutes": metrics["rpo"]["final_minutes"],
            "mttr_minutes": metrics["mttr"]["adjusted_minutes"],
            "mtbf_days": metrics["mtbf"]["adjusted_days"],
        },
        "compliance": {
            "rto_status": state["rto_status"],
            "rpo_status": state["rpo_status"],
            "overall_status": state["overall_status"],
            "breach_gap_minutes": state["breach_gap_minutes"],
        },
    }


def validate_incident_record(record: dict[str, Any]) -> None:
    schema = validator.load_schema(INCIDENT_SCHEMA)
    errors = validator.validate_document(record, schema, "incident-record (simulated)")
    if errors:
        print("\n[SIMULATION ERROR] Generated incident record failed schema validation:", file=sys.stderr)
        for error in errors:
            print(error, file=sys.stderr)
        sys.exit(1)


def load_service_profile(catalog_dir: Path) -> dict[str, Any]:
    path = catalog_dir / "service.yaml"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except (FileNotFoundError, yaml.YAMLError) as exc:
        print(f"[IO ERROR] Could not load service.yaml: {exc}", file=sys.stderr)
        sys.exit(2)


def main() -> None:
    print("=" * 60)
    print("INCIDENT SIMULATION — servernah-iaas-compute")
    print("=" * 60)
    print()

    params_data = compute_metrics.load_parameters(PARAMS_FILE)
    service_profile = load_service_profile(CATALOG_DIR)

    initial_state: dict[str, Any] = {
        "_params": params_data,
        "_params_raw": service_profile,
        "_base_time": SIMULATION_BASE_TIME,
    }

    state = phase_detection(initial_state)
    print()
    state = phase_recording(state)
    print()
    state = phase_initiation(state)
    print()
    state = phase_resolution(state)
    print()
    state = phase_reporting(state)

    print()
    print("-" * 60)
    print("Building incident record...")
    record = build_incident_record(state)

    print("Validating record against incident-record.json schema...")
    validate_incident_record(record)
    print("Schema validation: PASSED")

    print()
    print("=" * 60)
    print("INCIDENT RECORD OUTPUT")
    print("=" * 60)
    print(json.dumps(record, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()