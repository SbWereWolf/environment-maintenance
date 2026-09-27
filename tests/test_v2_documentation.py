from pathlib import Path


def test_readme_documents_the_complete_v2_operator_contract():
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    for token in (
        "environment-maintenance/catalog/v2",
        "catalog.json",
        "satisfied",
        "missing",
        "invalid",
        "unavailable",
        "install",
        "repair",
        "execution_bound_seconds",
        "max_output_bytes",
        "check",
        "dry-run",
        "ai-poise",
    ):
        assert token in readme


def test_shipped_example_is_one_catalog_v2_directory():
    root = Path(__file__).resolve().parents[1]
    manifest = root / "examples" / "catalog-v2" / "catalog.json"
    assert manifest.is_file()
    text = manifest.read_text(encoding="utf-8")
    assert "environment-maintenance/catalog/v2" in text
