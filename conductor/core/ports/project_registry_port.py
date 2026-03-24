from abc import ABC, abstractmethod

from conductor.core.domain.task import ConductorProject


class ProjectRegistryPort(ABC):
    """Contract for project registry backends.

    Implementations load project metadata (id, name, repo_url, aliases, integrations)
    and expose lookup methods used by adapters during task construction.
    """

    @abstractmethod
    def get_by_id(self, project_id: str) -> ConductorProject | None:
        """Return the project with the given internal id, or None."""
        ...

    @abstractmethod
    def get_by_integration_id(self, provider: str, integration_id: str) -> ConductorProject | None:
        """Reverse-lookup by an integration-specific ID.

        Args:
            provider: Integration name, e.g. ``"linear"``, ``"github"``.
            integration_id: The external ID stored under
                ``integrations.<provider>_project_id`` in projects.yaml.
        """
        ...

    @abstractmethod
    def get_all(self) -> list[ConductorProject]:
        """Return all registered projects."""
        ...
