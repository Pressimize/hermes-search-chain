import json
import logging
import tomllib
from pathlib import Path

import httpx
import pytest
import yaml

import search_chain
from search_chain import provider
from search_chain.provider import SearchChainProvider

EXA, PARALLEL, FIRECRAWL = "api.exa.ai", "api.parallel.ai", "api.firecrawl.dev"


def exa_ok(request):
    return httpx.Response(200, json={"results": [{"url": "https://exa.example/", "title": "E", "highlights": ["e"]}]})


def parallel_ok(request):
    return httpx.Response(200, json={"results": [{"url": "https://par.example/", "title": "P", "excerpts": ["p"]}]})


def firecrawl_ok(request):
    web = [{"url": "https://fc.example/", "title": "F", "description": "f"}]
    return httpx.Response(200, json={"success": True, "data": {"web": web}})


def status(code, body=None):
    return lambda request: httpx.Response(code, json=body or {"error": "nope"})


def empty(request):
    return httpx.Response(200, json={"success": True, "results": [], "data": {"web": []}})


def timeout(request):
    raise httpx.ReadTimeout("slow", request=request)


class Api:
    """MockTransport handler for all three services; records requests."""

    def __init__(self, exa=exa_ok, parallel=parallel_ok, firecrawl=firecrawl_ok):
        self.handlers = {EXA: exa, PARALLEL: parallel, FIRECRAWL: firecrawl}
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        return self.handlers[request.url.host](request)

    def hosts(self):
        return [r.url.host for r in self.requests]


class Clock:
    now = 1000.0

    def __call__(self):
        return self.now


def chain(api, clock=None):
    return SearchChainProvider(httpx.MockTransport(api), clock or Clock())


def served_by(result):
    assert result["success"] is True
    return result["data"]["web"][0]["title"]


@pytest.fixture
def logs(caplog):
    caplog.set_level(logging.INFO, logger="search_chain.provider")
    return caplog


def lines(logs, level=logging.INFO):
    return [r.getMessage() for r in logs.records if r.levelno == level]


# --- S1, S2 ---------------------------------------------------------------------------------------


def test_manifest_and_register():
    manifest = yaml.safe_load((Path(search_chain.__file__).parent / "plugin.yaml").read_text(encoding="utf-8"))
    assert manifest["name"] == "search-chain" and manifest["kind"] == "backend"
    assert manifest["requires_hermes"] == ">=0.21"
    assert manifest["provides_web_providers"] == ["search-chain"]
    assert [e["name"] for e in manifest["requires_env"]] == ["EXA_API_KEY", "PARALLEL_API_KEY", "FIRECRAWL_API_KEY"]
    assert all(e["secret"] is True for e in manifest["requires_env"])
    assert [e["name"] for e in manifest["optional_env"]] == [provider.HIGHLIGHT_SETTING, provider.PARALLEL_SETTING]
    assert not (Path(search_chain.__file__).parent / "pyproject.toml").exists()  # I3

    registered = []

    class Ctx:
        def register_web_search_provider(self, obj):
            registered.append(obj)

    search_chain.register(Ctx())
    assert len(registered) == 1 and isinstance(registered[0], SearchChainProvider)


def test_plugin_and_project_versions_agree():
    manifest = yaml.safe_load((Path(search_chain.__file__).parent / "plugin.yaml").read_text(encoding="utf-8"))
    project = tomllib.loads((Path(search_chain.__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8"))
    assert manifest["version"] == project["project"]["version"]


def test_properties(env):
    p = SearchChainProvider()
    assert p.name == "search-chain"
    assert p.display_name == "Search chain (Exa, Parallel, Firecrawl)"
    assert p.supports_search() is True and p.supports_extract() is False


def test_is_available_needs_one_key(env):
    p = SearchChainProvider()
    assert p.is_available() is True
    env.clear()
    assert p.is_available() is False
    env["FIRECRAWL_API_KEY"] = "fc"
    assert p.is_available() is True
    env.update(EXA_API_KEY=RuntimeError("no scope"), PARALLEL_API_KEY=RuntimeError("no scope"), FIRECRAWL_API_KEY="")
    assert p.is_available() is False  # S3: a raising lookup counts as unset


# --- S4, K1-K4, K7 --------------------------------------------------------------------------------


def test_exa_serves_and_nothing_else_is_asked(env, logs):
    api = Api()
    result = chain(api).search("q", 10)
    assert result == {
        "success": True,
        "data": {"web": [{"url": "https://exa.example/", "title": "E", "description": "e", "position": 1}]},
    }
    assert json.dumps(result).index('"url"') < json.dumps(result).index('"title"')  # S4: key order reaches the model
    assert api.hosts() == [EXA]
    assert json.loads(api.requests[0].content)["numResults"] == 10  # A6
    assert lines(logs) == ["search-chain: exa=ok"]


def test_query_reaches_every_stage(env):
    """K1, A1-A3: each stage is asked the query as given."""
    api = Api(exa=empty, parallel=empty, firecrawl=empty)
    chain(api).search("what is x")
    exa, parallel, firecrawl = (json.loads(request.content) for request in api.requests)
    assert (exa["query"], parallel["objective"], parallel["search_queries"], firecrawl["query"]) == (
        "what is x",
        "what is x",
        ["what is x"],
        "what is x",
    )


def test_default_limit_is_5(env):
    api = Api()
    chain(api).search("q")
    assert json.loads(api.requests[0].content)["numResults"] == 5


@pytest.mark.parametrize("failure", [status(500), status(402), status(401), timeout, empty])
def test_exa_failure_moves_on_to_parallel(env, failure):
    api = Api(exa=failure)
    assert served_by(chain(api).search("q")) == "P"
    assert api.hosts() == [EXA, PARALLEL]


def test_exa_and_parallel_failure_moves_on_to_firecrawl(env, logs):
    api = Api(exa=status(500), parallel=empty)
    assert served_by(chain(api).search("q")) == "F"
    assert api.hosts() == [EXA, PARALLEL, FIRECRAWL]  # K7: one request each
    assert lines(logs) == ["search-chain: exa=http_500 parallel=empty firecrawl=ok"]


def test_missing_key_skips_the_stage_without_request(env, logs):
    del env["EXA_API_KEY"]
    env["PARALLEL_API_KEY"] = ""
    api = Api()
    assert served_by(chain(api).search("q")) == "F"
    assert api.hosts() == [FIRECRAWL]
    assert lines(logs) == ["search-chain: exa=no_key parallel=no_key firecrawl=ok"]


# --- K6 -------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("stages", "error", "line"),
    [
        (
            {
                "exa": status(402, {"tag": "NO_MORE_CREDITS"}),
                "parallel": timeout,
                "firecrawl": status(500, {"error": "boom"}),
            },
            "Exa: HTTP 402 NO_MORE_CREDITS; Parallel: timeout; Firecrawl: HTTP 500 boom",
            "exa=http_402 parallel=timeout firecrawl=http_500",
        ),
        (
            {"exa": status(500), "parallel": empty, "firecrawl": timeout},  # an empty reply among failures
            "Exa: HTTP 500 nope; Parallel: no results; Firecrawl: timeout",
            "exa=http_500 parallel=empty firecrawl=timeout",
        ),
    ],
    ids=["failures", "failure-empty-failure"],
)
def test_all_stages_fail(env, logs, stages, error, line):
    result = chain(Api(**stages)).search("q")
    assert result == {"success": False, "error": f"search-chain: {error}"}
    assert lines(logs) == [f"search-chain: {line}"]


def test_no_results_anywhere_is_a_failure(env):
    api = Api(exa=empty, parallel=empty, firecrawl=empty)
    assert chain(api).search("q") == {
        "success": False,
        "error": "search-chain: Exa: no results; Parallel: no results; Firecrawl: no results",
    }


def test_no_keys_at_all(env, logs):
    env.clear()
    api = Api()
    assert chain(api).search("q") == {
        "success": False,
        "error": "search-chain: Exa: no API key; Parallel: no API key; Firecrawl: no API key",
    }
    assert api.hosts() == []
    assert lines(logs) == ["search-chain: exa=no_key parallel=no_key firecrawl=no_key"]


# --- K5 pauses ------------------------------------------------------------------------------------


@pytest.mark.parametrize(("code", "seconds"), [(402, 86400), (429, 60)])
def test_pause_after_quota_and_rate_limit(env, logs, code, seconds):
    clock = Clock()
    api = Api(exa=status(code, {"tag": "TAG"}))
    p = chain(api, clock)
    assert served_by(p.search("q")) == "P"
    assert lines(logs, logging.WARNING) == [f"search-chain: exa paused for {seconds} s (HTTP {code} TAG)"]  # L2

    clock.now += seconds - 1
    assert served_by(p.search("q")) == "P"
    assert api.hosts() == [EXA, PARALLEL, PARALLEL]  # paused: no request to Exa
    assert lines(logs)[-1] == "search-chain: exa=paused parallel=ok"

    clock.now += 1  # pause over: Exa is asked again
    api.handlers[EXA] = exa_ok
    assert served_by(p.search("q")) == "E"
    assert api.hosts() == [EXA, PARALLEL, PARALLEL, EXA]


@pytest.mark.parametrize("failure", [status(401), status(403), status(500), timeout, empty])
def test_no_pause_after_other_failures(env, logs, failure):
    api = Api(exa=failure)
    p = chain(api)
    p.search("q")
    p.search("q")
    assert api.hosts() == [EXA, PARALLEL, EXA, PARALLEL]
    assert lines(logs, logging.WARNING) == []


def test_stage_without_a_pause_is_asked_at_any_clock_value(env):
    """K5: only a quota or rate-limit reply pauses a stage, whatever the clock reads."""
    clock = Clock()
    clock.now = 0.0
    api = Api()
    assert served_by(chain(api, clock).search("q")) == "E"
    assert api.hosts() == [EXA]


def test_pause_belongs_to_the_key(env):
    api = Api(exa=status(402))
    p = chain(api)
    p.search("q")
    env["EXA_API_KEY"] = "another-key"  # e.g. another profile in the same process, or a corrected key
    p.search("q")
    assert api.hosts() == [EXA, PARALLEL, EXA, PARALLEL]


def test_key_that_cannot_be_encoded_fails_only_its_stage(env, logs):
    """A4, K4: a key with a lone surrogate (undecodable bytes in the environment) does not stop the chain."""
    env["EXA_API_KEY"] = "k\ud800y12345"
    api = Api(exa=status(402))
    assert served_by(chain(api).search("q")) == "P"
    assert lines(logs)[-1].endswith(" parallel=ok")


def test_pause_table_holds_no_key(env):
    """K5: the table is keyed by a digest of the key."""
    p = chain(Api(exa=status(402), parallel=status(429)))
    p.search("q")
    assert len(p._paused) == 2
    assert not any(str(key) in repr(p._paused) for key in env.values())


def test_pause_warning_is_one_line(env, logs):
    """A4, L2: a reason with line breaks cannot forge a log line."""
    api = Api(exa=status(402, {"tag": "NO_CREDITS\nERROR forged line"}), parallel=empty, firecrawl=empty)
    result = chain(api).search("q")
    assert result["error"].startswith("search-chain: Exa: HTTP 402 NO_CREDITS ERROR forged line; Parallel: no results")
    assert lines(logs, logging.WARNING) == [
        "search-chain: exa paused for 86400 s (HTTP 402 NO_CREDITS ERROR forged line)"
    ]
    assert not any("\n" in record.getMessage() for record in logs.records)


def test_pause_warning_names_the_whole_reason(env, logs):
    """L2: a reason that itself contains ": " is logged in full."""
    chain(Api(exa=status(402, {"error": "Payment Required: Insufficient credits"}))).search("q")
    assert lines(logs, logging.WARNING) == [
        "search-chain: exa paused for 86400 s (HTTP 402 Payment Required: Insufficient credits)"
    ]


def test_all_stages_paused_or_without_key(env, logs):
    del env["FIRECRAWL_API_KEY"]
    clock = Clock()
    api = Api(exa=status(402, {"tag": "NO_MORE_CREDITS"}), parallel=status(429, {"message": "slow down"}))
    p = chain(api, clock)
    p.search("q")
    clock.now += 30
    result = p.search("q")
    assert result == {
        "success": False,
        "error": "search-chain: Exa: HTTP 402 NO_MORE_CREDITS (paused for another 24 h); "
        "Parallel: HTTP 429 slow down (paused for another 1 min); Firecrawl: no API key",
    }
    assert api.hosts() == [EXA, PARALLEL]  # the second call sent nothing
    assert lines(logs)[-1] == "search-chain: exa=paused parallel=paused firecrawl=no_key"


@pytest.mark.parametrize(
    ("after", "left"),
    [
        (0, "24 h"),
        (3600, "23 h"),
        (77400, "3 h"),  # 2.5 h left
        (79200, "2 h"),
        (81000, "2 h"),  # 1.5 h left
        (81001, "1 h"),
        (82799, "1 h"),
        (82800, "1 h"),  # exactly one hour left
        (82801, "60 min"),
        (86340, "1 min"),
        (86399, "1 min"),
    ],
)
def test_remaining_pause_in_the_error_text(env, after, left):
    del env["PARALLEL_API_KEY"], env["FIRECRAWL_API_KEY"]
    clock = Clock()
    p = chain(Api(exa=status(402, {"tag": "NO_MORE_CREDITS"})), clock)
    p.search("q")
    clock.now += after
    assert p.search("q")["error"].startswith(
        f"search-chain: Exa: HTTP 402 NO_MORE_CREDITS (paused for another {left});"
    )


# --- A1 setting -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "highlights"),
    [
        (None, {"maxCharacters": 600}),
        ("", {"maxCharacters": 600}),
        ("300", {"maxCharacters": 300}),
        (" 1200 ", {"maxCharacters": 1200}),
        ("0", True),
        ("999999", {"maxCharacters": 999999}),
        ("1000000", {"maxCharacters": 600}),
        ("9" * 5000, {"maxCharacters": 600}),
        ("-5", {"maxCharacters": 600}),
        ("5.5", {"maxCharacters": 600}),
        ("abc", {"maxCharacters": 600}),
        ("²", {"maxCharacters": 600}),
        (RuntimeError("no scope"), {"maxCharacters": 600}),
    ],
)
def test_exa_highlight_setting(env, value, highlights):
    if value is not None:
        env["SEARCH_CHAIN_EXA_HIGHLIGHT_CHARS"] = value
    api = Api()
    chain(api).search("q")
    assert json.loads(api.requests[0].content)["contents"] == {"highlights": highlights}


# --- A2 setting -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "path"),
    [
        (None, "/v1beta/search"),
        ("", "/v1beta/search"),
        ("beta", "/v1beta/search"),
        ("v2", "/v1beta/search"),
        ("v1", "/v1/search"),
        (" V1 ", "/v1/search"),
        (RuntimeError("no scope"), "/v1beta/search"),
    ],
)
def test_parallel_api_setting(env, value, path):
    if value is not None:
        env["SEARCH_CHAIN_PARALLEL_API"] = value
    del env["EXA_API_KEY"]
    api = Api()
    assert served_by(chain(api).search("q")) == "P"
    assert api.requests[0].url.path == path
    assert ("parallel-beta" in api.requests[0].headers) == (path == "/v1beta/search")


# --- S3, S5, S6, A5 -------------------------------------------------------------------------------


def test_key_never_in_result_or_log(env, logs):
    def echo(request):
        key = request.headers.get("x-api-key") or request.headers["authorization"].removeprefix("Bearer ")
        return httpx.Response(402, json={"error": f"key {key} has no credits"})

    result = chain(Api(exa=echo, parallel=echo, firecrawl=echo)).search("q")
    assert result["error"].count("[key]") == 3
    for secret in ("exa-SECRET", "par-SECRET", "fc-SECRET"):
        assert secret not in json.dumps(result) and secret not in logs.text


def test_query_not_in_log(env, logs):
    chain(Api(exa=status(402))).search("a very private question")
    assert "private" not in logs.text


def test_unexpected_exception_becomes_a_failure(env, logs, monkeypatch):
    def boom(client, query, limit, key):
        raise RuntimeError("bug with exa-SECRET")

    monkeypatch.setattr(provider, "STAGES", (("exa", "Exa", "EXA_API_KEY", boom),))
    assert chain(Api()).search("q") == {"success": False, "error": "search-chain: RuntimeError"}
    assert lines(logs, logging.WARNING) == ["search-chain: call failed: RuntimeError"]
    assert lines(logs) == ["search-chain: no stage ran"]  # L1
    assert "exa-SECRET" not in logs.text


def test_interrupt_before_the_first_stage(env, logs, monkeypatch):
    monkeypatch.setattr(provider, "is_interrupted", lambda: True)
    api = Api()
    assert chain(api).search("q") == {"success": False, "error": "Interrupted"}
    assert api.hosts() == []
    assert lines(logs) == ["search-chain: exa=interrupted"]


def test_interrupt_between_stages(env, logs, monkeypatch):
    api = Api(exa=status(500))
    monkeypatch.setattr(provider, "is_interrupted", lambda: bool(api.requests))
    assert chain(api).search("q") == {"success": False, "error": "Interrupted"}
    assert api.hosts() == [EXA]
    assert lines(logs) == ["search-chain: exa=http_500 parallel=interrupted"]


def test_proxy_variables_are_honoured(env, logs, monkeypatch):
    """A5: without an injected transport the request goes to the proxy; nothing listens there."""
    for name in ("ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy", "https_proxy"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    del env["PARALLEL_API_KEY"], env["FIRECRAWL_API_KEY"]
    result = SearchChainProvider().search("q")
    assert result["error"].startswith("search-chain: Exa: ConnectError")
    assert lines(logs) == ["search-chain: exa=ConnectError parallel=no_key firecrawl=no_key"]


# --- A6 limit, S4 query ---------------------------------------------------------------------------


@pytest.mark.parametrize(("asked", "sent"), [(0, 1), (-5, 1), (5, 5), (20, 20), (50, 20), (100, 20)])
def test_limit_is_kept_between_1_and_20(env, asked, sent):
    """A6: Hermes asks for up to 100 results; no stage is asked for more than 20."""
    api = Api(exa=empty, parallel=empty, firecrawl=empty)
    chain(api).search("q", asked)
    exa, parallel, firecrawl = (json.loads(request.content) for request in api.requests)
    assert (exa["numResults"], parallel["max_results"], firecrawl["limit"]) == (sent, sent, sent)


@pytest.mark.parametrize("query", [None, "", "   \n", 5])
def test_empty_query_asks_no_service(env, logs, query):
    api = Api()
    assert chain(api).search(query) == {"success": False, "error": "search-chain: empty query"}
    assert api.requests == []
    assert lines(logs) == ["search-chain: empty_query"]
    assert lines(logs, logging.WARNING) == []
