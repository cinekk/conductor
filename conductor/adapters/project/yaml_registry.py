"""YAML-backed implementation of ProjectRegistryPort.

Loads project definitions from a YAML file at startup. Path is configurable
via Settings.projects_file (env var: PROJECTS_FILE).

Expected file format — see projects.yaml for the annotated template.
"""

import yaml

from conductor.core.domain.task import ConductorProject
from conductor.core.ports.project_registry_port import ProjectRegistryPort


class YamlProjectRegistry(ProjectRegistryPort):
    """Reads projects.yaml once at init and provides O(1) lookups."""

    def __init__(self, path: str) -> None:
        self._projects: list[ConductorProject] = []
        self._by_id: dict[str, ConductorProject] = {}
        # key: (provider, integration_id) — e.g. ("linear", "lin-uuid-alpha")
        self._by_integration: dict[tuple[str, str], ConductorProject] = {}
        self._load(path)

    def _load(self, path: str) -> None:
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        for entry in data.get("projects", []):
            project = ConductorProject(
                id=entry["id"],
                name=entry["name"],
                repo_url=entry["repo_url"],
                aliases=entry.get("aliases", []),
            )
            self._projects.append(project)
            self._by_id[project.id] = project
            for key, value in (entry.get("integrations") or {}).items():
                # key format: "<provider>_project_id" → provider = key split on "_project_id"
                if key.endswith("_project_id") and value:
                    provider = key[: -len("_project_id")]
                    self._by_integration[(provider, str(value))] = project

    def get_by_id(self, project_id: str) -> ConductorProject | None:
        return self._by_id.get(project_id)

    def get_by_integration_id(self, provider: str, integration_id: str) -> ConductorProject | None:
        return self._by_integration.get((provider, integration_id))

    def get_all(self) -> list[ConductorProject]:
        return list(self._projects)
