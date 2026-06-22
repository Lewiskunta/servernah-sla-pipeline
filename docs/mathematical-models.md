# Mathematical Models

All formulas are implemented in `scripts/compute_metrics.py` and tested in
`tests/test_compute_metrics.py`. Variable names in this document match the
`snake_case` keys in `catalog/servernah-iaas-compute/sla-parameters.yaml`
exactly.

## Variable Definitions

| Variable | Schema Key | Unit | Description |
|----------|-----------|------|-------------|
| TTD | `ttd_minutes` | minutes | Time to Detect — first alert to acknowledgement |
| TTIR | `ttir_minutes` | minutes | Time to Initiate Recovery — acknowledgement to first action |
| TTCR | `ttcr_minutes` | minutes | Time to Complete Recovery — active repair duration |
| TTVR | `ttvr_minutes` | minutes | Time to Validate Recovery — confirmation of full restoration |
| BF | `backup_frequency_minutes` | minutes | Interval between backup snapshots |
| DCR | `data_change_rate_gb_per_hour` | GB/hour | Average data change rate between backups |
| IF | `incident_frequency_per_day` | per day | Average service-impacting incidents per day |
| RTD | `rtd_minutes` | minutes | Recovery Times for Dependencies — weighted average upstream RTO |
| NCD | `ncd_count` | count | Number of Critical Dependencies whose failure cascades to this service |
| IC | `ic` | 1 to 5 | Infrastructure Complexity |
| GD | `gd` | 1 to 3 | Geographic Distribution |
| RA | `ra` | 1 to 3 | Resource Availability |
| SEA | `sea` | 1 to 3 | Staff Expertise and Availability |
| SC | `sc` | 1 to 4 | Service Criticality |

---

## Mean Time to Recovery (MTTR)

### Base MTTR

$$
\text{Base MTTR} = TTD + TTIR + TTCR + TTVR
$$

This is the raw sum of the four measurable phases of the incident lifecycle.
It represents the theoretical minimum recovery time assuming no infrastructure
complexity or geographic penalty.

### Adjusted MTTR

$$
\text{Adjusted MTTR} = \text{Base MTTR} \times \left(1 + \frac{IC - 1}{4}\right) \times \left(1 + \frac{GD - 1}{4}\right)
$$

The two multipliers inflate the base recovery time based on:

- **Infrastructure Complexity (IC):** A more complex stack - more services,
  more dependencies, more failure modes - takes longer to diagnose and restore.
  At IC = 1 (Simple), the multiplier is 1.0 (no penalty). At IC = 5 (Very Complex),
  the multiplier is 2.0 (doubles recovery time).

- **Geographic Distribution (GD):** Recovery actions across multiple sites
  introduce coordination overhead, network latency, and physical access constraints.
  At GD = 1 (Single site), the multiplier is 1.0. At GD = 3 (Multi-region),
  the multiplier is 1.5.

The denominator `4` in each term is the normalizing constant derived from the
maximum scale range. For IC (range 1 to 5), the maximum excess above baseline
is 4. For GD (range 1 to 3), the same denominator is used to keep the penalty
proportional and bounded.

### Worked Example

Using `catalog/servernah-iaas-compute/sla-parameters.yaml`:

$$
TTD = 15,\quad TTIR = 30,\quad TTCR = 60,\quad TTVR = 15
$$

$$
\text{Base MTTR} = 15 + 30 + 60 + 15 = 120 \text{ min}
$$

$$
IC = 3,\quad GD = 2
$$

$$
\text{Adjusted MTTR} = 120 \times \left(1 + \frac{3-1}{4}\right) \times \left(1 + \frac{2-1}{4}\right)
= 120 \times 1.5 \times 1.25 = 225 \text{ min}
$$

The Adjusted MTTR of 225 minutes falls within the Tier 1 Mission Critical
ceiling of 240 minutes, confirming the service's SLA target is achievable.

---

## Recovery Time Objective (RTO)

### Base RTO

$$
\text{Base RTO} = TTIR + TTCR + TTVR
$$

TTD is excluded because the detection phase, while part of MTTR, occurs before
the recovery clock starts in most SLA definitions.

### Dependency Floor

$$
\text{Dependency Floor} = RTD \times (1 + NCD \times 0.05)
$$

**Why the Dependency Floor exists:**

A virtualized compute instance cannot possess a recovery time objective lower
than the physical restoration limits of the infrastructure it runs on. If the
upstream Ceph storage cluster or MPLS circuit takes 45 minutes to restore, any
service sitting on top of that infrastructure cannot recover in 30 minutes
regardless of how well the application layer is engineered.

The Dependency Floor enforces this physical reality. Each additional critical
dependency adds a 5% penalty to the weighted average upstream RTO, reflecting
the increased probability that at least one dependency will be on its critical
path during a site-level failure.

### Final RTO

$$
\text{Final RTO} = \max\left(\text{Adjusted RTO},\ \text{Dependency Floor}\right)
$$

If a customer override is active (`csr = 1`), the customer-mandated RTO
replaces the Adjusted RTO in the comparison, but the Dependency Floor still
applies as an absolute minimum.

### Worked Example

$$
RTD = 45 \text{ min},\quad NCD = 3
$$

$$
\text{Dependency Floor} = 45 \times (1 + 3 \times 0.05) = 45 \times 1.15 = 51.75 \text{ min}
$$

$$
\text{Base RTO} = 30 + 60 + 15 = 105 \text{ min}
$$

$$
\text{Final RTO} = \max(105, 51.75) = 105 \text{ min}
$$

---

## Recovery Point Objective (RPO)

### Base RPO

$$
\text{Base RPO} = BF + \frac{DCR \times 1.5}{1000}
$$

The backup frequency sets the primary RPO bound. The data change rate term
adds a lag factor: higher data change rates increase the volume of data
written between snapshots, increasing the exposure window even at the same
snapshot frequency.

### Worked Example

$$
BF = 15 \text{ min},\quad DCR = 50 \text{ GB/hour}
$$

$$
\text{Base RPO} = 15 + \frac{50 \times 1.5}{1000} = 15 + 0.075 = 15.07 \text{ min}
$$

The 15-minute backup frequency keeps RPO within the Tier 1 target of 15 minutes,
with a marginal 0.07-minute overage from the data change rate lag.

---

## Mean Time Between Failures (MTBF)

### Base MTBF

$$
\text{Base MTBF} = \frac{1}{IF}
$$

MTBF is the inverse of incident frequency. At `incident_frequency_per_day = 0.022`
(approximately 8 incidents per year), Base MTBF is 45.45 days.

The schema enforces a minimum `incident_frequency_per_day` of 0.001 to prevent
division by zero. The formula engine additionally raises a `ValueError` if this
boundary is violated at runtime.

### Adjusted MTBF

$$
\text{Adjusted MTBF} = \text{Base MTBF} \times \frac{RA}{3} \times \frac{SEA}{3}
$$

Higher resource availability and staff expertise reduce the effective failure
rate by enabling faster detection and prevention. Both factors are deflation
multipliers bounded between 0.33 and 1.0.

### Worked Example

$$
IF = 0.022 \text{ per day},\quad RA = 2,\quad SEA = 3
$$

$$
\text{Base MTBF} = \frac{1}{0.022} = 45.45 \text{ days}
$$

$$
\text{Adjusted MTBF} = 45.45 \times \frac{2}{3} \times \frac{3}{3} = 45.45 \times 0.667 \times 1.0 = 30.30 \text{ days}
$$

---

## Tier Classification Thresholds

### RTO Tiers

| Tier | Label | Ceiling |
|------|-------|---------|
| 1 | Mission Critical | 240 min (4 hours) |
| 2 | Business Critical | 480 min (8 hours) |
| 3 | Business Operational | 1440 min (24 hours) |
| 4 | Non-Critical | No ceiling |

### RPO Tiers

| Tier | Label | Ceiling |
|------|-------|---------|
| 1 | No Data Loss | 15 min |
| 2 | Minimal Loss | 60 min |
| 3 | Moderate Loss | 240 min (4 hours) |
| 4 | Significant Loss | No ceiling |