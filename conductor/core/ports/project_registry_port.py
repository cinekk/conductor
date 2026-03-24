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
    def get_by_linear_project_id(self, linear_project_id: str) -> ConductorProject | None:
        """Reverse-lookup by Linear project UUID stored in integrations.linear_project_id."""
        ...

    @abstractmethod
    def get_all(self) -> list[ConductorProject]:
        """Return all registered projects."""
        ...
