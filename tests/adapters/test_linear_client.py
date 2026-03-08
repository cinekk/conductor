import json

import httpx
import pytest

from conductor.adapters.linear.client import LinearAPIError, LinearClient


def make_client() -> LinearClient:
    return LinearClient(api_key="test-key")


def mock_transport(response_body: dict, status_code: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=response_body)

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_add_comment_sends_correct_request():
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"data": {"commentCreate": {"success": True}}})

    client = make_client()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client._http = http  # type: ignore[attr-defined]

        async def patched_execute(query: str, variables: dict) -> dict:  # type: ignore[type-arg]
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
                resp = await c.post(
                    LinearClient.ENDPOINT,
                    headers=client._headers,
                    json={"query": query, "variables": variables},
                )
                return resp.json().get("data", {})

        client._execute = patched_execute  # type: ignore[method-assign]
        await client.add_comment("issue-123", "hello from agent")

    assert len(captured) == 1
    body = json.loads(captured[0].content)
    assert body["variables"]["issueId"] == "issue-123"
    assert body["variables"]["body"] == "hello from agent"


@pytest.mark.asyncio
async def test_graphql_errors_raise_linear_api_error():
    error_response = {"errors": [{"message": "Not found"}]}

    async def bad_execute(query: str, variables: dict) -> dict:  # type: ignore[type-arg]
        raise LinearAPIError(error_response["errors"])

    client = make_client()
    client._execute = bad_execute  # type: ignore[method-assign]

    with pytest.raises(LinearAPIError, match="Not found"):
        await client.add_comment("x", "y")


@pytest.mark.asyncio
async def test_execute_raises_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": "forbidden"})

    client = make_client()

    async def patched_execute(query: str, variables: dict) -> dict:  # type: ignore[type-arg]
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            resp = await c.post(LinearClient.ENDPOINT, headers=client._headers, json={})
            resp.raise_for_status()
            return {}

    client._execute = patched_execute  # type: ignore[method-assign]

    with pytest.raises(httpx.HTTPStatusError):
        await client.add_comment("x", "y")


@pytest.mark.asyncio
async def test_get_workflow_states_returns_nodes():
    states = [{"id": "s1", "name": "Todo", "type": "unstarted"}]

    async def patched_execute(query: str, variables: dict) -> dict:  # type: ignore[type-arg]
        return {"team": {"states": {"nodes": states}}}

    client = make_client()
    client._execute = patched_execute  # type: ignore[method-assign]

    result = await client.get_workflow_states("team-1")
    assert result == states
