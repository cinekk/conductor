import httpx


class LinearAPIError(Exception):
    """Raised when the Linear GraphQL API returns errors."""

    def __init__(self, errors: list) -> None:  # type: ignore[type-arg]
        super().__init__(str(errors))
        self.errors = errors


class LinearClient:
    """Thin async httpx wrapper for the Linear GraphQL API.

    Handles transport only — no business logic. All mutations/queries are
    expressed as raw GraphQL strings so they're easy to audit and update.
    """

    ENDPOINT = "https://api.linear.app/graphql"

    def __init__(self, api_key: str) -> None:
        self._headers = {"Authorization": api_key, "Content-Type": "application/json"}

    async def add_comment(self, issue_id: str, body: str) -> None:
        """Post a comment on a Linear issue."""
        mutation = """
        mutation AddComment($issueId: String!, $body: String!) {
            commentCreate(input: {issueId: $issueId, body: $body}) {
                success
            }
        }
        """
        await self._execute(mutation, {"issueId": issue_id, "body": body})

    async def update_state(self, issue_id: str, state_id: str) -> None:
        """Update the workflow state of a Linear issue."""
        mutation = """
        mutation UpdateState($issueId: String!, $stateId: String!) {
            issueUpdate(id: $issueId, input: {stateId: $stateId}) {
                success
            }
        }
        """
        await self._execute(mutation, {"issueId": issue_id, "stateId": state_id})

    async def get_workflow_states(self, team_id: str) -> list[dict]:  # type: ignore[type-arg]
        """Return all workflow states for a team: [{id, name, type}, ...]."""
        query = """
        query States($teamId: String!) {
            team(id: $teamId) {
                states { nodes { id name type } }
            }
        }
        """
        data = await self._execute(query, {"teamId": team_id})
        return data["team"]["states"]["nodes"]  # type: ignore[no-any-return]

    async def _execute(self, query: str, variables: dict) -> dict:  # type: ignore[type-arg]
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                self.ENDPOINT,
                headers=self._headers,
                json={"query": query, "variables": variables},
            )
            resp.raise_for_status()
            body = resp.json()
            if "errors" in body:
                raise LinearAPIError(body["errors"])
            return body.get("data", {})  # type: ignore[no-any-return]
