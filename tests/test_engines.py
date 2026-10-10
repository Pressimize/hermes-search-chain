import json

import httpx
import pytest

from search_chain import engines

ENGINES = [(engines.exa, "Exa"), (engines.parallel, "Parallel"), (engines.firecrawl, "Firecrawl")]


def call(fn, handler, *args):
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        return fn(client, *args)


def capture(reply):
    seen = {}

    def handler(request):
        seen["url"], seen["headers"], seen["body"] = str(request.url), request.headers, json.loads(request.content)
        return httpx.Response(200, json=reply)

    return seen, handler


def reply(body, status=200):
    return lambda request: httpx.Response(status, json=body)


# --- A1 Exa ---------------------------------------------------------------------------------------


def test_exa_request_and_rows():
    seen, handler = capture(
        {
            "results": [
                {"url": "https://a.example/", "title": "A", "highlights": ["one", "two"], "score": 0.5},
                {"url": "https://b.example/", "title": None},
            ],
            "costDollars": {"total": 0.007},
        }
    )
    out = call(engines.exa, handler, "what is x", 10, "exa-key")
    assert seen["url"] == "https://api.exa.ai/search"
    assert seen["headers"]["x-api-key"] == "exa-key"
    assert seen["body"] == {
        "query": "what is x",
        "numResults": 10,
        "contents": {"highlights": {"maxCharacters": 600}},
    }
    assert out == {
        "rows": [
            {"url": "https://a.example/", "title": "A", "description": "one two", "position": 1},
            {"url": "https://b.example/", "title": "", "description": "", "position": 2},
        ]
    }
    assert list(out["rows"][0]) == ["url", "title", "description", "position"]  # S4: key order


def test_rows_without_url_are_dropped_and_only_text_parts_joined():
    body = {
        "results": [
            {"title": "no url"},
            {"url": "", "title": "empty url"},
            {"url": "https://a.example/", "title": "A", "highlights": ["one", None, 2, "two"]},
        ]
    }
    out = call(engines.exa, reply(body), "q", 5, "k")
    assert out == {"rows": [{"url": "https://a.example/", "title": "A", "description": "one two", "position": 1}]}
    assert call(engines.exa, reply({"results": [{}]}), "q", 5, "k") == {"rows": []}


@pytest.mark.parametrize(("chars", "highlights"), [(300, {"maxCharacters": 300}), (0, True)])
def test_exa_highlight_setting(chars, highlights):
    seen, handler = capture({"results": []})
    assert call(engines.exa, handler, "q", 5, "k", chars) == {"rows": []}
    assert seen["body"]["contents"] == {"highlights": highlights}


# --- A2 Parallel ----------------------------------------------------------------------------------


def test_parallel_request_and_rows():
    seen, handler = capture({"results": [{"url": "https://a.example/", "title": "A", "excerpts": ["x", "y"]}]})
    out = call(engines.parallel, handler, "what is x", 10, "par-key")
    assert seen["url"] == "https://api.parallel.ai/v1/search"
    assert seen["headers"]["x-api-key"] == "par-key"
    assert seen["body"] == {
        "objective": "what is x",
        "search_queries": ["what is x"],
        "mode": "advanced",
        "advanced_settings": {"max_results": 10},
    }
    assert out == {"rows": [{"url": "https://a.example/", "title": "A", "description": "x y", "position": 1}]}


def test_parallel_caps_results_at_20():
    seen, handler = capture({"results": []})
    call(engines.parallel, handler, "q", 50, "k")
    assert seen["body"]["advanced_settings"] == {"max_results": 20}


# --- A3 Firecrawl ---------------------------------------------------------------------------------


def test_firecrawl_request_and_rows():
    seen, handler = capture(
        {"success": True, "data": {"web": [{"url": "https://a.example/", "title": "A", "description": "D"}]}}
    )
    out = call(engines.firecrawl, handler, "what is x", 10, "fc-key")
    assert seen["url"] == "https://api.firecrawl.dev/v2/search"
    assert seen["headers"]["authorization"] == "Bearer fc-key"
    assert seen["body"] == {"query": "what is x", "limit": 10}
    assert out == {"rows": [{"url": "https://a.example/", "title": "A", "description": "D", "position": 1}]}


def test_firecrawl_without_web_results_is_empty():
    assert call(engines.firecrawl, reply({"success": True, "data": {"news": []}}), "q", 5, "k") == {"rows": []}


@pytest.mark.parametrize("body", [{"success": False, "data": {"web": []}}, {"success": True, "data": []}, {}])
def test_firecrawl_unexpected_reply(body):
    out = call(engines.firecrawl, reply(body), "q", 5, "k")
    assert out == {"error": "Firecrawl: malformed reply", "code": "malformed", "status": None}


# --- A4 errors ------------------------------------------------------------------------------------


@pytest.mark.parametrize(("fn", "name"), ENGINES)
@pytest.mark.parametrize(
    ("body", "detail"),
    [
        ({"requestId": "r1", "error": "No more credits", "tag": "NO_MORE_CREDITS"}, "NO_MORE_CREDITS"),
        (
            {"success": False, "error": "Payment Required: Insufficient credits"},
            "Payment Required: Insufficient credits",
        ),
        ({"error": {"message": "Insufficient credits", "type": "billing"}}, "Insufficient credits"),
        ({"message": "quota exceeded"}, "quota exceeded"),
    ],
)
def test_api_error_detail(fn, name, body, detail):
    out = call(fn, reply(body, 402), "q", 5, "k")
    assert out == {"error": f"{name}: HTTP 402 {detail}", "code": "http_402", "status": 402}


@pytest.mark.parametrize(("fn", "name"), ENGINES)
@pytest.mark.parametrize("code", [199, 302, 400])
def test_only_2xx_is_a_reply(fn, name, code):
    body = {
        "success": True,
        "results": [{"url": "https://a.example/"}],
        "data": {"web": [{"url": "https://a.example/"}]},
    }
    out = call(fn, reply({**body, "error": "moved"}, code), "q", 5, "k")
    assert out == {"error": f"{name}: HTTP {code} moved", "code": f"http_{code}", "status": code}


@pytest.mark.parametrize(("fn", "name"), ENGINES)
def test_api_error_plain_text(fn, name):
    out = call(fn, lambda request: httpx.Response(503, text=" upstream down \n"), "q", 5, "k")
    assert out == {"error": f"{name}: HTTP 503 upstream down", "code": "http_503", "status": 503}


@pytest.mark.parametrize(("fn", "name"), ENGINES)
def test_timeout_and_transport_error(fn, name):
    def slow(request):
        raise httpx.ReadTimeout("slow", request=request)

    def down(request):
        raise httpx.ConnectError("down", request=request)

    assert call(fn, slow, "q", 5, "k") == {"error": f"{name}: timeout", "code": "timeout", "status": None}
    assert call(fn, down, "q", 5, "k") == {"error": f"{name}: ConnectError", "code": "ConnectError", "status": None}


@pytest.mark.parametrize(("fn", "name"), ENGINES)
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="<html>not json</html>"),
        httpx.Response(200, json=["a", "list"]),
        httpx.Response(200, json={"success": True, "results": "text", "data": {"web": "text"}}),
        httpx.Response(200, json={"success": True, "results": ["text"], "data": {"web": ["text"]}}),
    ],
)
def test_malformed_reply(fn, name, response):
    out = call(fn, lambda request: response, "q", 5, "k")
    assert out == {"error": f"{name}: malformed reply", "code": "malformed", "status": None}


@pytest.mark.parametrize(("fn", "name"), ENGINES)
def test_error_text_is_cut_and_key_masked(fn, name):
    out = call(fn, reply({"error": "bad key SECRET-KEY " + "x" * 500}, 401), "q", 5, "SECRET-KEY")
    assert "SECRET-KEY" not in out["error"]
    assert out["error"].startswith(f"{name}: HTTP 401 bad key [key] x")
    assert len(out["error"]) == len(f"{name}: ") + 200


# --- A0 -------------------------------------------------------------------------------------------


def test_timeouts_are_passed_to_httpx():
    seen = {}

    def handler(request):
        seen[request.url.host] = request.extensions["timeout"]
        return httpx.Response(500)

    for fn, _ in ENGINES:
        call(fn, handler, "q", 5, "k")
    assert {host: t["read"] for host, t in seen.items()} == {
        "api.exa.ai": 10.0,
        "api.parallel.ai": 15.0,
        "api.firecrawl.dev": 15.0,
    }
