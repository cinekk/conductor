"""Tests for file-based PromptRegistry."""

import textwrap
from pathlib import Path

import pytest

from conductor.prompts import PromptNotFoundError, PromptRegistry


@pytest.fixture()
def template_dir(tmp_path: Path) -> Path:
    """Create a temporary prompt_templates directory with a few test files."""
    d = tmp_path / "prompt_templates"
    d.mkdir()
    (d / "dev-agent@1.txt").write_text("Hello v1: {spec}", encoding="utf-8")
    (d / "dev-agent@2.txt").write_text("Hello v2: {spec}", encoding="utf-8")
    (d / "qa-agent@1.txt").write_text("QA prompt", encoding="utf-8")
    return d


def test_get_latest_returns_highest_version(template_dir: Path):
    registry = PromptRegistry(template_dir)
    assert registry.get("dev-agent", spec="foo") == "Hello v2: foo"


def test_get_specific_version(template_dir: Path):
    registry = PromptRegistry(template_dir)
    assert registry.get("dev-agent", version=1, spec="bar") == "Hello v1: bar"


def test_get_no_kwargs_returns_raw_template(template_dir: Path):
    registry = PromptRegistry(template_dir)
    assert registry.get("qa-agent") == "QA prompt"


def test_unknown_name_raises(template_dir: Path):
    registry = PromptRegistry(template_dir)
    with pytest.raises(PromptNotFoundError, match="deployer"):
        registry.get("deployer")


def test_unknown_version_raises(template_dir: Path):
    registry = PromptRegistry(template_dir)
    with pytest.raises(PromptNotFoundError, match="99"):
        registry.get("dev-agent", version=99)


def test_available_returns_all_versions(template_dir: Path):
    registry = PromptRegistry(template_dir)
    available = registry.available()
    assert available["dev-agent"] == [1, 2]
    assert available["qa-agent"] == [1]


def test_empty_directory_returns_empty_available(tmp_path: Path):
    registry = PromptRegistry(tmp_path / "empty")
    assert registry.available() == {}


def test_missing_directory_does_not_raise(tmp_path: Path):
    # Non-existent dir should be handled gracefully
    registry = PromptRegistry(tmp_path / "nonexistent")
    assert registry.available() == {}


def test_ignores_files_without_version_pattern(tmp_path: Path):
    d = tmp_path / "templates"
    d.mkdir()
    (d / "README.md").write_text("ignore me", encoding="utf-8")
    (d / "dev-agent@1.txt").write_text("hi", encoding="utf-8")
    registry = PromptRegistry(d)
    assert list(registry.available().keys()) == ["dev-agent"]


def test_real_templates_are_loadable():
    """Smoke-test the real prompt_templates/ directory ships valid templates."""
    registry = PromptRegistry()
    available = registry.available()
    assert "developer-agent" in available
    assert "qa-agent" in available
    # Templates compile with expected variables
    prompt = registry.get("developer-agent", spec="Implement feature X", repo_path="/tmp/repo")
    assert "Implement feature X" in prompt
    assert "/tmp/repo" in prompt
