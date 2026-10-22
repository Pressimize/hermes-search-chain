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
BRAVE, NIMBLE, TAVILY, YOUCOM = "api.search.brave.com", "sdk.nimbleway.com", "api.tavily.com", "ydc-index.io"
SEARX, DEGOOG = "searx.test", "degoog.test"
# the stages between Parallel and Firecrawl, when only the three keys of conftest.KEYS are set
MID = "brave=no_key nimble=no_key tavily=no_key youcom=no_key searxng=no_url degoog=no_url"


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


def brave_ok(request):
    return httpx.Response(200, json={"web": {"results": [{"url": "https://b.example/", "title": "B"}]}})


def results_ok(title):
    return lambda request: httpx.Response(200, json={"results": [{"url": f"https://{title}.example/", "title": title}]})


NIMBLE_OK, TAVILY_OK, SEARX_OK, DEGOOG_OK = (results_ok(title) for title in "NTSD")


def youcom_ok(request):
    return httpx.Response(200, json={"results": {"web": [{"url": "https://y.example/", "title": "Y"}]}})


class Api:
    """MockTransport handler for all nine services; records requests."""

    def __init__(
        self,
        exa=exa_ok,
        parallel=parallel_ok,
        firecrawl=firecrawl_ok,
        brave=brave_ok,
        nimble=NIMBLE_OK,
        tavily=TAVILY_OK,
        youcom=youcom_ok,
        searxng=SEARX_OK,
        degoog=DEGOOG_OK,
    ):
        self.handlers = {EXA: exa, PARALLEL: parallel, FIRECRAWL: firecrawl, BRAVE: brave, NIMBLE: nimble}
        self.handlers.update({TAVILY: tavily, YOUCOM: youcom, SEARX: searxng, DEGOOG: degoog})
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
    assert [e["name"] for e in manifest["optional_env"]] == [
        "BRAVE_SEARCH_API_KEY",
        "NIMBLE_API_KEY",
        "TAVILY_API_KEY",
        "YDC_API_KEY",
        "SEARXNG_URL",
        "DEGOOG_URL",
        provider.ORDER_SETTING,
        provider.HIGHLIGHT_SETTING,
        provider.PARALLEL_SETTING,
    ]
    assert all(e.get("secret") is True for e in manifest["optional_env"][:6])  # keys, and addresses (A13)
    assert not any(e.get("secret") for e in manifest["optional_env"][6:])
    settings = [e["name"] for e in manifest["requires_env"] + manifest["optional_env"]]
    assert all(setting in settings for _, _, setting, _, _ in provider.STAGES)
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
    assert p.display_name == "Search chain"
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
    """K1, A1-A3: Exa, Parallel and Firecrawl are asked the query as given (the other stages: test_engines.py)."""
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
    assert lines(logs) == [f"search-chain: exa=http_500 parallel=empty {MID} firecrawl=ok"]


def test_missing_key_skips_the_stage_without_request(env, logs):
    del env["EXA_API_KEY"]
    env["PARALLEL_API_KEY"] = ""
    api = Api()
    assert served_by(chain(api).search("q")) == "F"
    assert api.hosts() == [FIRECRAWL]
    assert lines(logs) == [f"search-chain: exa=no_key parallel=no_key {MID} firecrawl=ok"]


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
            f"exa=http_402 parallel=timeout {MID} firecrawl=http_500",
        ),
        (
            {"exa": status(500), "parallel": empty, "firecrawl": timeout},  # an empty reply among failures
            "Exa: HTTP 500 nope; Parallel: no results; Firecrawl: timeout",
            f"exa=http_500 parallel=empty {MID} firecrawl=timeout",
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
    assert chain(api).search("q") == {"success": False, "error": "search-chain: no stage configured"}  # K6
    assert api.hosts() == []
    assert lines(logs) == [f"search-chain: exa=no_key parallel=no_key {MID} firecrawl=no_key"]


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
        "Parallel: HTTP 429 slow down (paused for another 1 min)",  # K6: Firecrawl without key is not named
    }
    assert api.hosts() == [EXA, PARALLEL]  # the second call sent nothing
    assert lines(logs)[-1] == f"search-chain: exa=paused parallel=paused {MID} firecrawl=no_key"


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
    assert p.search("q")["error"] == f"search-chain: Exa: HTTP 402 NO_MORE_CREDITS (paused for another {left})"


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

    monkeypatch.setattr(provider, "STAGES", (("exa", "Exa", "EXA_API_KEY", boom, "key"),))
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
    assert lines(logs) == [f"search-chain: exa=ConnectError parallel=no_key {MID} firecrawl=no_key"]


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


# --- K1 nine stages, K8 order setting -------------------------------------------------------------

ALL = [EXA, PARALLEL, BRAVE, NIMBLE, TAVILY, YOUCOM, SEARX, DEGOOG, FIRECRAWL]
NAMES = ["exa", "parallel", "brave", "nimble", "tavily", "youcom", "searxng", "degoog", "firecrawl"]


def youcom_empty(request):
    return httpx.Response(200, json={"results": {"web": []}})


def nothing(name):
    """A valid reply without hits, in the shape of this stage."""
    return youcom_empty if name == "youcom" else empty


def none_serve():
    return Api(**{name: nothing(name) for name in NAMES})


def test_default_order_asks_all_nine_stages(all_stages, logs):
    api = none_serve()
    result = chain(api).search("q")
    assert api.hosts() == ALL
    assert lines(logs) == ["search-chain: " + " ".join(f"{name}=empty" for name in NAMES)]
    assert result["error"] == "search-chain: " + "; ".join(
        f"{name}: no results"
        for name in ("Exa", "Parallel", "Brave", "Nimble", "Tavily", "You.com", "SearXNG", "Degoog", "Firecrawl")
    )


@pytest.mark.parametrize("serving", range(9))
def test_each_stage_serves_when_the_ones_before_find_nothing(all_stages, serving):
    api = Api(**{name: nothing(name) for name in NAMES[:serving]})
    assert chain(api).search("q")["success"] is True
    assert api.hosts() == ALL[: serving + 1]


def test_order_setting_picks_and_orders_stages(all_stages, logs):
    all_stages["SEARCH_CHAIN_ORDER"] = " SearXNG , exa,firecrawl,"
    api = none_serve()
    result = chain(api).search("q")
    assert api.hosts() == [SEARX, EXA, FIRECRAWL]  # stages with a key but not named are not asked
    assert lines(logs) == ["search-chain: searxng=empty exa=empty firecrawl=empty"]
    assert result["error"] == "search-chain: SearXNG: no results; Exa: no results; Firecrawl: no results"
    assert lines(logs, logging.WARNING) == []  # an empty entry is dropped without a warning


@pytest.mark.parametrize(
    ("value", "used"),
    [
        ("exa,bing,parallel", "exa,parallel"),
        ("exa,EXA,parallel", "exa,parallel"),
        ("bing", ",".join(NAMES)),
        (",", ",".join(NAMES)),
    ],
)
def test_unknown_or_repeated_names_are_dropped_with_one_warning(all_stages, logs, value, used):
    all_stages["SEARCH_CHAIN_ORDER"] = value
    api = none_serve()
    p = chain(api)
    p.search("q")
    p.is_available()
    p.search("q")
    assert api.hosts() == 2 * [dict(zip(NAMES, ALL, strict=True))[name] for name in used.split(",")]
    assert lines(logs, logging.WARNING) == [
        f"search-chain: SEARCH_CHAIN_ORDER has unknown or repeated names; using {used}"
    ]


@pytest.mark.parametrize("value", [None, "", "  "])
def test_unset_order_is_the_default_without_a_warning(all_stages, logs, value):
    if value is not None:
        all_stages["SEARCH_CHAIN_ORDER"] = value
    api = none_serve()
    chain(api).search("q")
    assert api.hosts() == ALL
    assert lines(logs, logging.WARNING) == []


def test_order_without_a_configured_stage(env, logs):
    """K8: a valid order whose stages have no key does not fall back to the default."""
    env["SEARCH_CHAIN_ORDER"] = "brave,searxng"
    api = Api()
    p = chain(api)
    assert p.is_available() is False  # Exa, Parallel and Firecrawl have keys, but are not in the order
    assert p.search("q") == {"success": False, "error": "search-chain: no stage configured"}
    assert api.hosts() == []
    assert lines(logs) == ["search-chain: brave=no_key searxng=no_url"]


def test_is_available_counts_an_address(env):
    env.clear()
    assert SearchChainProvider().is_available() is False
    env["DEGOOG_URL"] = "/"  # nothing left after the slashes are cut
    assert SearchChainProvider().is_available() is False
    env["DEGOOG_URL"] = "http://degoog.test"
    assert SearchChainProvider().is_available() is True


def test_unconfigured_stages_are_left_out_of_the_error(env):
    """K6: only stages that were asked or are paused are named."""
    api = Api(exa=status(500), parallel=empty, firecrawl=timeout)
    error = "search-chain: Exa: HTTP 500 nope; Parallel: no results; Firecrawl: timeout"
    assert chain(api).search("q")["error"] == error


@pytest.mark.parametrize("code", [432, 433])
def test_tavily_quota_codes_pause_for_a_day(env, logs, code):
    env["SEARCH_CHAIN_ORDER"] = "tavily,firecrawl"
    env["TAVILY_API_KEY"] = "tavily-SECRET"
    clock = Clock()
    api = Api(tavily=status(code, {"detail": {"error": "limit"}}))
    p = chain(api, clock)
    assert served_by(p.search("q")) == "F"
    assert lines(logs, logging.WARNING) == [f"search-chain: tavily paused for 86400 s (HTTP {code} limit)"]
    clock.now += 86399
    p.search("q")
    assert api.hosts() == [TAVILY, FIRECRAWL, FIRECRAWL]


def test_pause_belongs_to_the_address(env):
    """K5, A13: a self-hosted stage pauses per address; trailing slashes do not make another address."""
    env.clear()
    env.update(SEARCH_CHAIN_ORDER="searxng", SEARXNG_URL="http://user:pw@searx.test/")
    api = Api(searxng=status(429))
    p = chain(api)
    p.search("q")
    env["SEARXNG_URL"] = "http://user:pw@searx.test//"
    p.search("q")
    assert api.hosts() == [SEARX]  # same instance: paused
    assert "searx.test" not in repr(p._paused) and "pw" not in repr(p._paused)
    env["SEARXNG_URL"] = "http://other.searx.test"
    api.handlers["other.searx.test"] = status(429)
    p.search("q")
    assert api.hosts() == [SEARX, "other.searx.test"]


def test_bad_address_fails_its_stage_every_time_without_a_pause(env, logs):
    env["SEARXNG_URL"] = "searx.test"
    env["SEARCH_CHAIN_ORDER"] = "searxng,exa"
    api = Api()
    p = chain(api)
    for _ in range(2):
        assert served_by(p.search("q")) == "E"
    assert lines(logs) == ["search-chain: searxng=bad_url exa=ok"] * 2
    assert p._paused == {}
    env["EXA_API_KEY"] = ""
    assert p.search("q")["error"] == "search-chain: SearXNG: invalid URL setting"


def test_a_key_is_not_stripped_like_an_address(env):
    env["EXA_API_KEY"] = "exa-key/"
    api = Api()
    chain(api).search("q")
    assert api.requests[0].headers["x-api-key"] == "exa-key/"


def test_new_keys_never_in_result_or_log(all_stages, logs):
    def echo(request):
        key = request.headers.get("x-api-key") or request.headers.get("x-subscription-token")
        key = key or request.headers.get("authorization", "").removeprefix("Bearer ")
        return httpx.Response(402, json={"error": f"key {key} has no credits"})

    all_stages["SEARCH_CHAIN_ORDER"] = "brave,nimble,tavily,youcom"
    result = chain(Api(brave=echo, nimble=echo, tavily=echo, youcom=echo)).search("q")
    assert result["error"].count("[key]") == 4
    for name in ("brave", "nimble", "tavily", "ydc"):
        assert f"{name}-SECRET" not in json.dumps(result) and f"{name}-SECRET" not in logs.text


# --- gaps found by the mutation run of 0.2.0 ------------------------------------------------------


def test_pause_belongs_to_the_stage_as_well(env):
    """K5: two stages with the same address do not share a pause."""
    env.clear()
    env.update(SEARXNG_URL="http://same.test", DEGOOG_URL="http://same.test")
    seen = []

    def handler(request):
        seen.append(request.url.path)
        return httpx.Response(402, json={"error": "x"}) if request.url.path == "/search" else empty(request)

    chain(handler).search("q")
    assert seen == ["/search", "/api/search"]  # Degoog is asked although SearXNG at the same address is paused


def test_highlight_setting_needs_ascii_digits(env):
    env["SEARCH_CHAIN_EXA_HIGHLIGHT_CHARS"] = "٣٠٠"  # 300 in Arabic-Indic digits
    api = Api()
    chain(api).search("q")
    assert json.loads(api.requests[0].content)["contents"] == {"highlights": {"maxCharacters": 600}}


def test_different_bad_orders_warn_only_once(all_stages, logs):
    for value in ("foo", "bar"):
        all_stages["SEARCH_CHAIN_ORDER"] = value
        chain(none_serve()).search("q")
    assert len(lines(logs, logging.WARNING)) == 1
