import sys
from pathlib import Path
from typing import Any

import yaml


CATALOG_DIR = Path(__file__).parent.parent / "catalog" / "servernah-iaas-compute"
PARAMS_FILE = CATALOG_DIR / "sla-parameters.yaml"

RTO_TIERS: list[tuple[float, str]] = [
    (240, "tier-1-mission-critical-0-4h"),
    (480, "tier-2-business-critical-4-8h"),
    (1440, "tier-3-business-operational-8-24h"),
    (float("inf"), "tier-4-non-critical-24h-plus"),
]

RPO_TIERS: list[tuple[float, str]] = [
    (15, "tier-1-no-data-loss-0-15min"),
    (60, "tier-2-minimal-loss-15-60min"),
    (240, "tier-3-moderate-loss-1-4h"),
    (float("inf"), "tier-4-significant-loss-4h-plus"),
]


def compute_base_mttr(
    ttd: int,
    ttir: int,
    ttcr: int,
    ttvr: int,
) -> float:
    return round(float(ttd + ttir + ttcr + ttvr), 2)


def compute_adjusted_mttr(
    base_mttr: float,
    ic: int,
    gd: int,
) -> float:
    if not (1 <= ic <= 5):
        raise ValueError(f"ic must be between 1 and 5, got {ic}")
    if not (1 <= gd <= 3):
        raise ValueError(f"gd must be between 1 and 3, got {gd}")
    complexity_factor = 1 + (ic - 1) / 4
    geo_factor = 1 + (gd - 1) / 4
    return round(base_mttr * complexity_factor * geo_factor, 2)


def compute_base_rto(
    ttir: int,
    ttcr: int,
    ttvr: int,
) -> float:
    return round(float(ttir + ttcr + ttvr), 2)


def compute_dependency_floor(
    rtd: int,
    ncd: int,
) -> float:
    if rtd < 0:
        raise ValueError(f"rtd must be >= 0, got {rtd}")
    if ncd < 0:
        raise ValueError(f"ncd must be >= 0, got {ncd}")
    return round(rtd * (1 + ncd * 0.05), 2)


def compute_final_rto(
    adjusted_rto: float,
    dependency_floor: float,
    customer_rto: int,
    csr: int,
) -> float:
    if csr not in (0, 1):
        raise ValueError(f"csr must be 0 or 1, got {csr}")
    base = customer_rto if csr == 1 else adjusted_rto
    return round(max(base, dependency_floor), 2)


def compute_base_rpo(
    backup_frequency_minutes: int,
    data_change_rate_gb_per_hour: float,
) -> float:
    if backup_frequency_minutes <= 0:
        raise ValueError(f"backup_frequency_minutes must be > 0, got {backup_frequency_minutes}")
    return round(backup_frequency_minutes + (data_change_rate_gb_per_hour * 1.5 / 1000), 2)


def compute_base_mtbf(incident_frequency_per_day: float) -> float:
    if incident_frequency_per_day <= 0:
        raise ValueError(
            f"incident_frequency_per_day must be > 0, got {incident_frequency_per_day}. "
            "Schema enforces minimum 0.001."
        )
    return round(1 / incident_frequency_per_day, 2)


def compute_adjusted_mtbf(
    base_mtbf: float,
    ra: int,
    sea: int,
) -> float:
    if not (1 <= ra <= 3):
        raise ValueError(f"ra must be between 1 and 3, got {ra}")
    if not (1 <= sea <= 3):
        raise ValueError(f"sea must be between 1 and 3, got {sea}")
    return round(base_mtbf * (ra / 3) * (sea / 3), 2)


def classify_tier(value: float, tiers: list[tuple[float, str]]) -> str:
    for ceiling, label in tiers:
        if value <= ceiling:
            return label
    return tiers[-1][1]


def load_parameters(path: Path) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"[IO ERROR] Parameters file not found: {path}", file=sys.stderr)
        sys.exit(2)
    except yaml.YAMLError as exc:
        print(f"[PARSE ERROR] Invalid YAML in {path}: {exc}", file=sys.stderr)
        sys.exit(2)


def run(params_path: Path) -> dict[str, Any]:
    params = load_parameters(params_path)

    tb = params["time_based"]
    fd = params["frequency_and_data"]
    dm = params["dependency_metrics"]
    ql = params["qualitative"]
    co = params["customer_override"]

    base_mttr = compute_base_mttr(
        tb["ttd_minutes"], tb["ttir_minutes"], tb["ttcr_minutes"], tb["ttvr_minutes"]
    )
    adjusted_mttr = compute_adjusted_mttr(base_mttr, ql["ic"], ql["gd"])

    base_rto = compute_base_rto(
        tb["ttir_minutes"], tb["ttcr_minutes"], tb["ttvr_minutes"]
    )
    dep_floor = compute_dependency_floor(dm["rtd_minutes"], dm["ncd_count"])
    final_rto = compute_final_rto(
        base_rto, dep_floor, co["customer_rto_minutes"], co["csr"]
    )

    base_rpo = compute_base_rpo(
        fd["backup_frequency_minutes"], fd["data_change_rate_gb_per_hour"]
    )

    base_mtbf = compute_base_mtbf(fd["incident_frequency_per_day"])
    adjusted_mtbf = compute_adjusted_mtbf(base_mtbf, ql["ra"], ql["sea"])

    return {
        "mttr": {
            "base_minutes": base_mttr,
            "adjusted_minutes": adjusted_mttr,
            "complexity_factor": round(1 + (ql["ic"] - 1) / 4, 4),
            "geo_factor": round(1 + (ql["gd"] - 1) / 4, 4),
        },
        "rto": {
            "base_minutes": base_rto,
            "dependency_floor_minutes": dep_floor,
            "final_minutes": final_rto,
            "tier": classify_tier(final_rto, RTO_TIERS),
        },
        "rpo": {
            "base_minutes": base_rpo,
            "final_minutes": base_rpo,
            "tier": classify_tier(base_rpo, RPO_TIERS),
        },
        "mtbf": {
            "base_days": base_mtbf,
            "adjusted_days": adjusted_mtbf,
            "ra_factor": round(ql["ra"] / 3, 4),
            "sea_factor": round(ql["sea"] / 3, 4),
        },
    }


def format_output(results: dict[str, Any]) -> str:
    lines = [
        "=" * 60,
        "SLA METRIC COMPUTATION — servernah-iaas-compute",
        "=" * 60,
        "",
        "MTTR",
        f"  Base:              {results['mttr']['base_minutes']} min",
        f"  Complexity factor: {results['mttr']['complexity_factor']}",
        f"  Geo factor:        {results['mttr']['geo_factor']}",
        f"  Adjusted:          {results['mttr']['adjusted_minutes']} min",
        "",
        "RTO",
        f"  Base:              {results['rto']['base_minutes']} min",
        f"  Dependency floor:  {results['rto']['dependency_floor_minutes']} min",
        f"  Final:             {results['rto']['final_minutes']} min",
        f"  Tier:              {results['rto']['tier']}",
        "",
        "RPO",
        f"  Base:              {results['rpo']['base_minutes']} min",
        f"  Final:             {results['rpo']['final_minutes']} min",
        f"  Tier:              {results['rpo']['tier']}",
        "",
        "MTBF",
        f"  Base:              {results['mtbf']['base_days']} days",
        f"  RA factor:         {results['mtbf']['ra_factor']}",
        f"  SEA factor:        {results['mtbf']['sea_factor']}",
        f"  Adjusted:          {results['mtbf']['adjusted_days']} days",
        "",
        "=" * 60,
    ]
    return "\n".join(lines)


def main() -> None:
    results = run(PARAMS_FILE)
    print(format_output(results))
    sys.exit(0)


if __name__ == "__main__":
    main()