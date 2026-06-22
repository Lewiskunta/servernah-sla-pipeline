# Data Dictionary

Translation matrix between the SLA Excel workbooks and the platform
engineering files in this repository. Every parameter in
`catalog/servernah-iaas-compute/sla-parameters.yaml` is defined here
with its workbook source, schema key, type, bounds, and formula role.

## Time-Based Parameters

| Schema Key | Type | Unit | Min | Max | Workbook Sheet | Workbook Row | Formula Role |
|-----------|------|------|-----|-----|---------------|-------------|-------------|
| `ttd_minutes` | integer | minutes | 1 | 1440 | Parameters | 5 | Base MTTR addend |
| `ttir_minutes` | integer | minutes | 1 | 1440 | Parameters | 6 | Base MTTR and Base RTO addend |
| `ttcr_minutes` | integer | minutes | 1 | 1440 | Parameters | 7 | Base MTTR and Base RTO addend |
| `ttvr_minutes` | integer | minutes | 1 | 1440 | Parameters | 8 | Base MTTR and Base RTO addend |

## Frequency and Data Parameters

| Schema Key | Type | Unit | Min | Max | Workbook Sheet | Workbook Row | Formula Role |
|-----------|------|------|-----|-----|---------------|-------------|-------------|
| `backup_frequency_minutes` | integer | minutes | 1 | 1440 | Parameters | 10 | Base RPO primary term |
| `data_change_rate_gb_per_hour` | number | GB/hour | 0 | 10000 | Parameters | 11 | Base RPO lag factor |
| `incident_frequency_per_day` | number | per day | 0.001 | 100 | Parameters | 12 | Base MTBF divisor |

## Dependency Metrics

| Schema Key | Type | Unit | Min | Max | Workbook Sheet | Workbook Row | Formula Role |
|-----------|------|------|-----|-----|---------------|-------------|-------------|
| `rtd_minutes` | integer | minutes | 0 | 1440 | Parameters | 14 | Dependency Floor base |
| `ncd_count` | integer | count | 0 | 50 | Parameters | 15 | Dependency Floor penalty multiplier |

## Qualitative Parameters

| Schema Key | Type | Scale | Min | Max | Workbook Sheet | Workbook Row | Formula Role |
|-----------|------|-------|-----|-----|---------------|-------------|-------------|
| `ic` | integer | 1=Simple, 5=Very Complex | 1 | 5 | Parameters | 17 | MTTR complexity inflation via `(IC-1)/4` |
| `gd` | integer | 1=Single site, 3=Multi-region | 1 | 3 | Parameters | 18 | MTTR geo inflation via `(GD-1)/4` |
| `ra` | integer | 1=Limited, 3=Abundant | 1 | 3 | Parameters | 19 | MTBF deflation via `RA/3` |
| `sea` | integer | 1=Limited, 3=Expert | 1 | 3 | Parameters | 20 | MTBF deflation via `SEA/3` |
| `sc` | integer | 1=Mission Critical, 4=Low | 1 | 4 | Parameters | 21 | RTO criticality adjustment via `SC/4` |

## Customer Override Parameters

| Schema Key | Type | Unit | Min | Max | Workbook Sheet | Workbook Row | Formula Role |
|-----------|------|------|-----|-----|---------------|-------------|-------------|
| `csr` | integer | 0 or 1 | 0 | 1 | Parameters | 22 | Override activation switch |
| `customer_rto_minutes` | integer | minutes | 1 | 1440 | Parameters | 24 | Replaces Adjusted RTO when CSR = 1 |
| `customer_rpo_minutes` | integer | minutes | 1 | 1440 | Parameters | 25 | Replaces Base RPO when CSR = 1 |

## Schema Enforcement Notes

All bounds in this table are enforced by `schemas/sla-parameters.json` at
validation time. The `incident_frequency_per_day` minimum is 0.001 rather
than 0 to prevent division by zero in the MTBF formula at the data entry
level. The formula engine in `scripts/compute_metrics.py` additionally
raises a `ValueError` if this boundary is violated at runtime.

Qualitative parameter denominators (4 for IC and GD, 3 for RA and SEA)
are the normalizing constants derived from each scale's maximum range.
They bound the resulting multipliers to physically meaningful values that
cannot produce negative recovery times or infinite failure rates.