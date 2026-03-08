import pytest

from conductor.core.ports.adapter_port import AdapterPort
from conductor.core.ports.agent_port import AgentPort
from conductor.core.ports.llm_port import LLMPort


def test_agent_port_cannot_be_instantiated():
    with pytest.raises(TypeError):
        AgentPort()  # type: ignore[abstract]


def test_adapter_port_cannot_be_instantiated():
    with pytest.raises(TypeError):
        AdapterPort()  # type: ignore[abstract]


def test_llm_port_cannot_be_instantiated():
    with pytest.raises(TypeError):
        LLMPort()  # type: ignore[abstract]
