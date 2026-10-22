"""Stand-in for Hermes' ``agent.web_search_provider`` so the plugin imports without Hermes installed."""

import abc
import sys
import types

import pytest

ENV: dict[str, object] = {}


class WebSearchProvider(abc.ABC):
    """Stand-in for the Hermes base class with the same abstract members (``name``, ``is_available``)."""

    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @property
    def display_name(self) -> str:
        return self.name

    @abc.abstractmethod
    def is_available(self) -> bool: ...

    def supports_search(self) -> bool:
        return True

    def supports_extract(self) -> bool:
        return False


def get_provider_env(name: str) -> str:
    value = ENV.get(name, "")
    if isinstance(value, Exception):
        raise value
    return str(value).strip()


_module = types.ModuleType("agent.web_search_provider")
_module.WebSearchProvider = WebSearchProvider
_module.get_provider_env = get_provider_env
sys.modules.setdefault("agent", types.ModuleType("agent"))
sys.modules["agent.web_search_provider"] = _module

KEYS = {"EXA_API_KEY": "exa-SECRET", "PARALLEL_API_KEY": "par-SECRET", "FIRECRAWL_API_KEY": "fc-SECRET"}
MORE = {
    "BRAVE_SEARCH_API_KEY": "brave-SECRET",
    "NIMBLE_API_KEY": "nimble-SECRET",
    "TAVILY_API_KEY": "tavily-SECRET",
    "YDC_API_KEY": "ydc-SECRET",
    "SEARXNG_URL": "http://searx.test",
    "DEGOOG_URL": "http://degoog.test",
}


@pytest.fixture
def env():
    """The keys of Exa, Parallel and Firecrawl set (KEYS); tests may delete or replace entries."""
    ENV.clear()
    ENV.update(KEYS)
    yield ENV
    ENV.clear()


@pytest.fixture
def all_stages(env):
    """Keys and addresses for all nine stages."""
    env.update(MORE)
    return env


@pytest.fixture(autouse=True)
def fresh_warnings():
    """K8: the order warning is once per process; every test starts without it."""
    from search_chain import provider

    provider._warned.clear()
    yield
    provider._warned.clear()
