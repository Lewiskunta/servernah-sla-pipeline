import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import compute_metrics


class TestComputeBaseMttr:

    @pytest.mark.parametrize("ttd,ttir,ttcr,ttvr,expected", [
        (15, 30, 60, 15, 120.0),
        (10, 20, 45, 10, 85.0),
        (5,  5,  5,  5, 20.0),
    ])
    def test_base_mttr_sum(self, ttd, ttir, ttcr, ttvr, expected):
        # Arrange - inputs provided via parametrize

        # Act
        result = compute_metrics.compute_base_mttr(ttd, ttir, ttcr, ttvr)

        # Assert
        assert result == pytest.approx(expected)


class TestComputeAdjustedMttr:

    @pytest.mark.parametrize("base,ic,gd,expected", [
        (120.0, 3, 2, 225.0),
        (120.0, 1, 1, 120.0),
        (120.0, 5, 3, 360.0),
        (100.0, 2, 1, 125.0),
    ])
    def test_adjusted_mttr_formula(self, base, ic, gd, expected):
        # Arrange - inputs provided via parametrize

        # Act
        result = compute_metrics.compute_adjusted_mttr(base, ic, gd)

        # Assert
        assert result == pytest.approx(expected)

    @pytest.mark.parametrize("ic,gd", [
        (0, 2),
        (6, 2),
        (3, 0),
        (3, 4),
    ])
    def test_out_of_bounds_ic_or_gd_raises(self, ic, gd):
        # Arrange - out-of-bounds qualitative parameters

        # Act / Assert
        with pytest.raises(ValueError):
            compute_metrics.compute_adjusted_mttr(120.0, ic, gd)


class TestComputeBaseRto:

    @pytest.mark.parametrize("ttir,ttcr,ttvr,expected", [
        (30, 60, 15, 105.0),
        (10, 20, 10, 40.0),
        (60, 120, 30, 210.0),
    ])
    def test_base_rto_sum(self, ttir, ttcr, ttvr, expected):
        # Arrange - inputs provided via parametrize

        # Act
        result = compute_metrics.compute_base_rto(ttir, ttcr, ttvr)

        # Assert
        assert result == pytest.approx(expected)


class TestComputeDependencyFloor:

    @pytest.mark.parametrize("rtd,ncd,expected", [
        (45, 3, 51.75),
        (45, 0, 45.0),
        (60, 5, 75.0),
        (0,  3, 0.0),
    ])
    def test_dependency_floor_formula(self, rtd, ncd, expected):
        # Arrange - inputs provided via parametrize

        # Act
        result = compute_metrics.compute_dependency_floor(rtd, ncd)

        # Assert
        assert result == pytest.approx(expected)

    def test_negative_rtd_raises(self):
        # Arrange - invalid negative RTD

        # Act / Assert
        with pytest.raises(ValueError):
            compute_metrics.compute_dependency_floor(-1, 3)

    def test_negative_ncd_raises(self):
        # Arrange - invalid negative NCD

        # Act / Assert
        with pytest.raises(ValueError):
            compute_metrics.compute_dependency_floor(45, -1)


class TestComputeFinalRto:

    def test_customer_override_active(self):
        # Arrange
        adjusted_rto = 150.0
        dep_floor = 51.75
        customer_rto = 60
        csr = 1

        # Act
        result = compute_metrics.compute_final_rto(adjusted_rto, dep_floor, customer_rto, csr)

        # Assert
        assert result == pytest.approx(60.0)

    def test_customer_override_inactive_uses_adjusted(self):
        # Arrange
        adjusted_rto = 105.0
        dep_floor = 51.75
        customer_rto = 60
        csr = 0

        # Act
        result = compute_metrics.compute_final_rto(adjusted_rto, dep_floor, customer_rto, csr)

        # Assert
        assert result == pytest.approx(105.0)

    def test_dependency_floor_enforced_when_above_adjusted(self):
        # Arrange
        adjusted_rto = 30.0
        dep_floor = 51.75
        customer_rto = 60
        csr = 0

        # Act
        result = compute_metrics.compute_final_rto(adjusted_rto, dep_floor, customer_rto, csr)

        # Assert
        assert result == pytest.approx(51.75)

    def test_invalid_csr_raises(self):
        # Arrange - CSR must be 0 or 1

        # Act / Assert
        with pytest.raises(ValueError):
            compute_metrics.compute_final_rto(105.0, 51.75, 60, 2)


class TestComputeBaseRpo:

    @pytest.mark.parametrize("bf,dcr,expected", [
        (15, 50.0, 15.07),
        (30, 0.0,  30.0),
        (10, 100.0, 10.15),
    ])
    def test_base_rpo_formula(self, bf, dcr, expected):
        # Arrange - inputs provided via parametrize

        # Act
        result = compute_metrics.compute_base_rpo(bf, dcr)

        # Assert
        assert result == pytest.approx(expected)

    def test_zero_backup_frequency_raises(self):
        # Arrange - backup frequency of zero is invalid

        # Act / Assert
        with pytest.raises(ValueError):
            compute_metrics.compute_base_rpo(0, 50.0)


class TestComputeBaseMtbf:

    @pytest.mark.parametrize("freq,expected", [
        (0.022, 45.45),
        (0.5,   2.0),
        (1.0,   1.0),
    ])
    def test_base_mtbf_inverse(self, freq, expected):
        # Arrange - inputs provided via parametrize

        # Act
        result = compute_metrics.compute_base_mtbf(freq)

        # Assert
        assert result == pytest.approx(expected, rel=1e-2)

    def test_zero_frequency_raises(self):
        # Arrange - zero incident frequency must raise, not return 9999
        # Note: schema enforces minimum 0.001, but the function defends itself too

        # Act / Assert
        with pytest.raises(ValueError):
            compute_metrics.compute_base_mtbf(0)

    def test_negative_frequency_raises(self):
        # Arrange - negative incident frequency is physically impossible

        # Act / Assert
        with pytest.raises(ValueError):
            compute_metrics.compute_base_mtbf(-0.1)


class TestComputeAdjustedMtbf:

    @pytest.mark.parametrize("base,ra,sea,expected", [
        (45.45, 2, 3, 30.3),
        (45.45, 3, 3, 45.45),
        (45.45, 1, 1, 5.05),
        (100.0, 2, 2, 44.44),
    ])
    def test_adjusted_mtbf_formula(self, base, ra, sea, expected):
        # Arrange - inputs provided via parametrize

        # Act
        result = compute_metrics.compute_adjusted_mtbf(base, ra, sea)

        # Assert
        assert result == pytest.approx(expected, rel=1e-2)

    @pytest.mark.parametrize("ra,sea", [
        (0, 2),
        (4, 2),
        (2, 0),
        (2, 4),
    ])
    def test_out_of_bounds_ra_or_sea_raises(self, ra, sea):
        # Arrange - out-of-bounds qualitative parameters

        # Act / Assert
        with pytest.raises(ValueError):
            compute_metrics.compute_adjusted_mtbf(45.45, ra, sea)


class TestClassifyTier:

    @pytest.mark.parametrize("rto_value,expected_tier", [
        (51.75,  "tier-1-mission-critical-0-4h"),
        (240.0,  "tier-1-mission-critical-0-4h"),
        (241.0,  "tier-2-business-critical-4-8h"),
        (480.0,  "tier-2-business-critical-4-8h"),
        (481.0,  "tier-3-business-operational-8-24h"),
        (1440.0, "tier-3-business-operational-8-24h"),
        (1441.0, "tier-4-non-critical-24h-plus"),
    ])
    def test_rto_tier_classification(self, rto_value, expected_tier):
        # Arrange - inputs provided via parametrize

        # Act
        result = compute_metrics.classify_tier(rto_value, compute_metrics.RTO_TIERS)

        # Assert
        assert result == expected_tier

    @pytest.mark.parametrize("rpo_value,expected_tier", [
        (15.07,  "tier-2-minimal-loss-15-60min"),
        (15.0,   "tier-1-no-data-loss-0-15min"),
        (16.0,   "tier-2-minimal-loss-15-60min"),
        (60.0,   "tier-2-minimal-loss-15-60min"),
        (61.0,   "tier-3-moderate-loss-1-4h"),
        (241.0,  "tier-4-significant-loss-4h-plus"),
    ])
    def test_rpo_tier_classification(self, rpo_value, expected_tier):
        # Arrange - inputs provided via parametrize

        # Act
        result = compute_metrics.classify_tier(rpo_value, compute_metrics.RPO_TIERS)

        # Assert
        assert result == expected_tier