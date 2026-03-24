"""Tests for YamlProjectRegistry."""

import textwrap

import pytest

from conductor.adapters.project.yaml_registry import YamlProjectRegistry
from conductor.core.domain.task import ConductorProject


@pytest.fixture
def registry_file(tmp_path):
    content = textwrap.dedent("""\
        projects:
          - id: alpha
            name: Alpha
            repo_url: git@github.com:org/alpha.git
            aliases:
              - a
              - alpha app
            integrations:
              linear_project_id: lin-uuid-alpha

          - id: beta
            name: Beta
            repo_url: git@github.com:org/beta.git
            aliases: []
            integrations:
              linear_project_id: lin-uuid-beta

          - id: gamma
            name: Gamma
            repo_url: git@github.com:org/gamma.git
    """)
    p = tmp_path / "projects.yaml"
    p.write_text(content)
    return str(p)


def test_get_all_returns_all_projects(registry_file):
    reg = YamlProjectRegistry(registry_file)
    projects = reg.get_all()
    assert len(projects) == 3
    assert [p.id for p in projects] == ["alpha", "beta", "gamma"]


def test_get_by_id_found(registry_file):
    reg = YamlProjectRegistry(registry_file)
    project = reg.get_by_id("alpha")
    assert isinstance(project, ConductorProject)
    assert project.name == "Alpha"
    assert project.repo_url == "git@github.com:org/alpha.git"
    assert project.aliases == ["a", "alpha app"]


def test_get_by_id_not_found(registry_file):
    reg = YamlProjectRegistry(registry_file)
    assert reg.get_by_id("nonexistent") is None


def test_get_by_integration_id_found(registry_file):
    reg = YamlProjectRegistry(registry_file)
    project = reg.get_by_integration_id("linear", "lin-uuid-alpha")
    assert project is not None
    assert project.id == "alpha"


def test_get_by_integration_id_not_found(registry_file):
    reg = YamlProjectRegistry(registry_file)
    assert reg.get_by_integration_id("linear", "unknown-uuid") is None


def test_get_by_integration_id_wrong_provider(registry_file):
    reg = YamlProjectRegistry(registry_file)
    assert reg.get_by_integration_id("github", "lin-uuid-alpha") is None


def test_project_without_integration_not_in_lookup(registry_file):
    """gamma has no integrations block — should not appear in integration lookup."""
    reg = YamlProjectRegistry(registry_file)
    assert reg.get_by_id("gamma") is not None
    assert reg.get_by_integration_id("linear", "") is None


def test_empty_file(tmp_path):
    p = tmp_path / "empty.yaml"
    p.write_text("projects: []\n")
    reg = YamlProjectRegistry(str(p))
    assert reg.get_all() == []


def test_get_all_returns_copy(registry_file):
    """Mutating the returned list must not affect the registry internals."""
    reg = YamlProjectRegistry(registry_file)
    projects = reg.get_all()
    projects.clear()
    assert len(reg.get_all()) == 3
