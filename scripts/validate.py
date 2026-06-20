import json
import sys
from pathlib import Path
from typing import Any

import jsonschema
import yaml


SCHEMA_DIR = Path(__file__).parent.parent / "schemas"
CATALOG_DIR = Path(__file__).parent.parent / "catalog" / "servernah-iaas-compute"

SCHEMA_MAP: dict[str, str] = {
    "service.yaml": "service-profile.json",
    "sla-parameters.yaml": "sla-parameters.json",
    "infrastructure.yaml": "dependencies.json",
    "software.yaml": "dependencies.json",
    "external.yaml": "dependencies.json",
    "recovery-playbook.yaml": "recovery-sequence.json",
}


def load_json(path: Path) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[IO ERROR] Schema file not found: {path}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as exc:
        print(f"[PARSE ERROR] Invalid JSON in {path}: {exc}", file=sys.stderr)
        sys.exit(2)


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"[IO ERROR] Catalog file not found: {path}", file=sys.stderr)
        sys.exit(2)
    except yaml.YAMLError as exc:
        print(f"[PARSE ERROR] Invalid YAML in {path}: {exc}", file=sys.stderr)
        sys.exit(2)


def load_schema(schema_name: str) -> dict[str, Any]:
    return load_json(SCHEMA_DIR / schema_name)


def validate_document(
    document: dict[str, Any],
    schema: dict[str, Any],
    source_label: str,
) -> list[str]:
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(document), key=lambda e: list(e.path))
    messages: list[str] = []
    for error in errors:
        field_path = ".".join(str(p) for p in error.absolute_path) or "(root)"
        messages.append(
            f"[ERROR] {source_label}: '{field_path}' — {error.message}"
        )
    return messages


def check_referential_integrity(catalog: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []

    root_id = catalog["service.yaml"].get("metadata", {}).get("service_id")
    if not root_id:
        errors.append("[INTEGRITY] service.yaml: 'metadata.service_id' is missing")
        return errors

    for filename in [
        "sla-parameters.yaml",
        "infrastructure.yaml",
        "software.yaml",
        "external.yaml",
        "recovery-playbook.yaml",
    ]:
        doc = catalog.get(filename, {})
        ref = doc.get("metadata", {}).get("service_ref")
        if ref != root_id:
            errors.append(
                f"[INTEGRITY] {filename}: 'metadata.service_ref' is '{ref}'"
                f" but expected '{root_id}'"
            )

    declared_component_ids: set[str] = set()
    for section_key in ["physical_nodes", "network_links", "software_components", "external_dependencies"]:
        for doc_name in ["infrastructure.yaml", "software.yaml", "external.yaml"]:
            for item in catalog.get(doc_name, {}).get(section_key, []):
                cid = item.get("component_id")
                if cid:
                    declared_component_ids.add(cid)

    playbook = catalog.get("recovery-playbook.yaml", {})
    steps = playbook.get("steps", [])

    declared_step_ids: set[str] = set()
    for step in steps:
        sid = step.get("step_id")
        if sid:
            declared_step_ids.add(sid)

        ref = step.get("component_ref")
        if ref and ref not in declared_component_ids:
            errors.append(
                f"[INTEGRITY] recovery-playbook.yaml: step '{sid}'"
                f" references component_ref '{ref}' which is not declared"
                f" in infrastructure.yaml, software.yaml, or external.yaml"
            )

    for step in steps:
        sid = step.get("step_id", "unknown")
        for dep in step.get("depends_on", []):
            if dep not in declared_step_ids:
                errors.append(
                    f"[INTEGRITY] recovery-playbook.yaml: step '{sid}'"
                    f" depends_on '{dep}' which is not a declared step_id"
                )

    return errors


def run_validation(catalog_dir: Path) -> tuple[list[str], int]:
    all_errors: list[str] = []
    catalog: dict[str, dict[str, Any]] = {}

    for yaml_filename, schema_filename in SCHEMA_MAP.items():
        yaml_path = catalog_dir / yaml_filename
        document = load_yaml(yaml_path)
        schema = load_schema(schema_filename)
        catalog[yaml_filename] = document
        errors = validate_document(document, schema, yaml_filename)
        all_errors.extend(errors)

    integrity_errors = check_referential_integrity(catalog)
    all_errors.extend(integrity_errors)

    return all_errors, len(SCHEMA_MAP)


def main() -> None:
    print(f"Validating catalog: {CATALOG_DIR}", file=sys.stdout)
    print(f"Against schemas in: {SCHEMA_DIR}", file=sys.stdout)
    print("-" * 60, file=sys.stdout)

    all_errors, files_checked = run_validation(CATALOG_DIR)

    if all_errors:
        for message in all_errors:
            print(message, file=sys.stderr)
        print("-" * 60, file=sys.stdout)
        print(
            f"Result: FAILED — {len(all_errors)} error(s) across {files_checked} file(s)",
            file=sys.stdout,
        )
        sys.exit(1)

    print(f"Result: PASSED — {files_checked} file(s) validated with 0 errors", file=sys.stdout)
    sys.exit(0)


if __name__ == "__main__":
    main()