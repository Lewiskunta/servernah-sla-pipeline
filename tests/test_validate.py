import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import validate


SCHEMAS_DIR = Path(__file__).parent.parent / "schemas"
VALID_DIR = Path(__file__).parent / "fixtures" / "valid"
INVALID_DIR = Path(__file__).parent / "fixtures" / "invalid"


def load_fixture(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_schema(name: str) -> dict:
    return validate.load_schema(name)


class TestValidFixtures:

    def test_valid_service_passes(self):
        # Arrange
        document = load_fixture(VALID_DIR / "service-valid.yaml")
        schema = load_schema("service-profile.json")

        # Act
        errors = validate.validate_document(document, schema, "service-valid.yaml")

        # Assert
        assert errors == []

    def test_valid_sla_parameters_passes(self):
        # Arrange
        document = load_fixture(VALID_DIR / "sla-parameters-valid.yaml")
        schema = load_schema("sla-parameters.json")

        # Act
        errors = validate.validate_document(document, schema, "sla-parameters-valid.yaml")

        # Assert
        assert errors == []

    def test_valid_recovery_playbook_passes(self):
        # Arrange
        document = load_fixture(VALID_DIR / "recovery-valid.yaml")
        schema = load_schema("recovery-sequence.json")

        # Act
        errors = validate.validate_document(document, schema, "recovery-valid.yaml")

        # Assert
        assert errors == []


class TestInvalidFixtures:

    def test_missing_tier_produces_error(self):
        # Arrange
        document = load_fixture(INVALID_DIR / "service-missing-tier.yaml")
        schema = load_schema("service-profile.json")

        # Act
        errors = validate.validate_document(document, schema, "service-missing-tier.yaml")

        # Assert
        assert len(errors) >= 1
        assert any("tier" in e for e in errors)

    def test_rto_out_of_bounds_produces_error(self):
        # Arrange
        document = load_fixture(INVALID_DIR / "rto-out-of-bounds.yaml")
        schema = load_schema("service-profile.json")

        # Act
        errors = validate.validate_document(document, schema, "rto-out-of-bounds.yaml")

        # Assert
        assert len(errors) >= 1
        assert any("rto_minutes" in e for e in errors)

    def test_unrecognised_key_is_rejected(self):
        # Arrange
        document = load_fixture(VALID_DIR / "service-valid.yaml")
        document["metadata"]["phantom_field"] = "this should not exist"
        schema = load_schema("service-profile.json")

        # Act
        errors = validate.validate_document(document, schema, "service-valid.yaml")

        # Assert
        assert len(errors) >= 1
        assert any("phantom_field" in e for e in errors)

    def test_string_typed_integer_is_rejected(self):
        # Arrange
        document = load_fixture(VALID_DIR / "sla-parameters-valid.yaml")
        document["time_based"]["ttd_minutes"] = "fifteen"
        schema = load_schema("sla-parameters.json")

        # Act
        errors = validate.validate_document(document, schema, "sla-parameters-valid.yaml")

        # Assert
        assert len(errors) >= 1
        assert any("ttd_minutes" in e for e in errors)

    def test_all_errors_collected_not_just_first(self):
        # Arrange
        document = load_fixture(VALID_DIR / "service-valid.yaml")
        document["metadata"]["phantom_one"] = "bad"
        document["spec"]["sla_targets"]["rto_minutes"] = 99999
        schema = load_schema("service-profile.json")

        # Act
        errors = validate.validate_document(document, schema, "service-valid.yaml")

        # Assert
        assert len(errors) >= 2
        assert any("phantom_one" in e for e in errors)
        assert any("rto_minutes" in e for e in errors)


class TestReferentialIntegrity:

    def test_mismatched_service_ref_produces_error(self):
        # Arrange
        valid_service = load_fixture(VALID_DIR / "service-valid.yaml")
        valid_params = load_fixture(VALID_DIR / "sla-parameters-valid.yaml")
        valid_params["metadata"]["service_ref"] = "completely-wrong-id"

        catalog = {
            "service.yaml": valid_service,
            "sla-parameters.yaml": valid_params,
            "infrastructure.yaml": {"metadata": {"service_ref": "test-service-01"}},
            "software.yaml": {"metadata": {"service_ref": "test-service-01"}},
            "external.yaml": {"metadata": {"service_ref": "test-service-01"}},
            "recovery-playbook.yaml": {
                "metadata": {"service_ref": "test-service-01"},
                "steps": [],
            },
        }

        # Act
        errors = validate.check_referential_integrity(catalog)

        # Assert
        assert len(errors) >= 1
        assert any("sla-parameters.yaml" in e for e in errors)
        assert any("completely-wrong-id" in e for e in errors)

    def test_orphaned_component_ref_produces_error(self):
        # Arrange
        valid_service = load_fixture(VALID_DIR / "service-valid.yaml")
        recovery_with_orphan = load_fixture(INVALID_DIR / "recovery-broken-order.yaml")

        catalog = {
            "service.yaml": valid_service,
            "sla-parameters.yaml": {"metadata": {"service_ref": "test-service-01"}},
            "infrastructure.yaml": {"metadata": {"service_ref": "test-service-01"}},
            "software.yaml": {"metadata": {"service_ref": "test-service-01"}},
            "external.yaml": {"metadata": {"service_ref": "test-service-01"}},
            "recovery-playbook.yaml": recovery_with_orphan,
        }

        # Act
        errors = validate.check_referential_integrity(catalog)

        # Assert
        assert len(errors) >= 1
        assert any("step-99" in e for e in errors)