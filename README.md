<div align="center">

# servernah-sla-pipeline

[![Validate Spec](https://github.com/Lewiskunta/servernah-sla-pipeline/actions/workflows/validate-spec.yml/badge.svg)](https://github.com/Lewiskunta/servernah-sla-pipeline/actions/workflows/validate-spec.yml)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![Schema: JSON Schema Draft-07](https://img.shields.io/badge/schema-JSON%20Schema%20Draft--07-lightgrey)
![Platform: OpenStack](https://img.shields.io/badge/platform-OpenStack-red)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

</div>

This repository is the programmatic source of truth for SLA parameters,
service topology, and disaster recovery sequencing across Atlancis
Technologies' Servernah IaaS platform. It compiles declarative YAML
configurations into validated, audit-ready operational models that feed
the live Airflow/Spark/InfluxDB monitoring pipeline.

---

## Quickstart

```bash
git clone https://github.com/Lewiskunta/servernah-sla-pipeline.git
cd servernah-sla-pipeline
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
python scripts/validate.py && python -m pytest tests/ -v
```

On Windows:
```powershell
git clone https://github.com/Lewiskunta/servernah-sla-pipeline.git
cd servernah-sla-pipeline
python -m venv .venv; .venv\Scripts\Activate.ps1; pip install -r requirements.txt
python scripts/validate.py; python -m pytest tests/ -v
```

A passing run produces:
```
Result: PASSED — 6 file(s) validated with 0 errors
64 passed in 0.XXs
```

---

## What This Repository Does

| Script | Purpose |
|--------|---------|
| `scripts/validate.py` | Validates all catalog YAML files against JSON Schema contracts and checks cross-file referential integrity |
| `scripts/compute_metrics.py` | Computes RTO, RPO, MTTR, and MTBF from the declared SLA parameters using the infrastructure-adjusted formulas |
| `scripts/simulate_incident.py` | Simulates a five-phase incident lifecycle and produces a schema-validated incident record |

---

## Repository Structure

```
servernah-sla-pipeline/
├── schemas/                    JSON Schema contracts
├── catalog/
│   └── servernah-iaas-compute/ Full service topology and SLA parameters
├── scripts/                    Validation, formula, and simulation engine
├── tests/                      64 tests covering all engine functions
└── docs/                       Architecture and formula reference
```

---

## Project Context

This repository was built as the foundation layer for a full SLA monitoring
overhaul at Atlancis Technologies. The YAML catalog and JSON Schema contracts
act as the static governance layer. The live monitoring pipeline - Airflow
DAGs correlating Zabbix alerts, MySupport ticket timestamps, and OpenSearch
service states - pulls from these definitions to compute real-time SLA
compliance.

The Excel workbooks that preceded this repository are available as downloads
for teams that need the human-readable design layer alongside the
machine-readable specifications.

- [Service Recovery Objectives Template](https://lewisinjai.dev/templates/service-recovery-objectives.xlsx)
- [Service Dependency Mapping Template](https://lewisinjai.dev/templates/service-dependency-mapping.xlsx)

Full project write-up: [Servernah SLA Monitoring Framework](https://lewisinjai.dev/work/sla-monitoring-framework/)

---

## Documentation

- [Architecture](docs/architecture.md) - repository boundary, pipeline overview, validation flow
- [Mathematical Models](docs/mathematical-models.md) - all formulas with worked examples
- [Data Dictionary](docs/data-dictionary.md) - parameter reference and Excel workbook mapping
