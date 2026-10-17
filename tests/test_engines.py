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


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "file:///etc/passwd",
        "data:text/html,x",
        "ftp://a.example/",
        "//a.example/",
        " https://a.example/",
        {"host": "x"},
        5,
        ["https://a.example/"],
        None,
    ],
)
def test_rows_without_a_web_url_are_dropped(url):
    """S4: only a string that starts with http:// or https:// counts as a URL."""
    items = [{"url": url, "title": "dropped"}, {"url": "HTTPS://A.example/", "title": "kept"}]
    out = call(engines.exa, reply({"results": items}), "q", 5, "k")
    assert out == {"rows": [{"url": "HTTPS://A.example/", "title": "kept", "description": "", "position": 1}]}


def test_http_urls_are_kept_in_any_letter_case():
    """S4: both schemes count, in any letter case; the URL is passed on as sent."""
    urls = ["http://a.example/", "HTTP://B.example/", "Https://c.example/"]
    out = call(engines.exa, reply({"results": [{"url": u} for u in urls]}), "q", 5, "k")
    assert [row["url"] for row in out["rows"]] == urls


def test_title_and_description_that_are_no_text_become_empty():
    web = [{"url": "https://a.example/", "title": 7, "description": {"d": 1}}]
    out = call(engines.firecrawl, reply({"success": True, "data": {"web": web}}), "q", 5, "k")
    assert out == {"rows": [{"url": "https://a.example/", "title": "", "description": "", "position": 1}]}
    item = {"url": "https://a.example/", "title": {"a": 1}, "highlights": "no list"}
    out = call(engines.exa, reply({"results": [item]}), "q", 5, "k")
    assert out == {"rows": [{"url": "https://a.example/", "title": "", "description": "", "position": 1}]}


def test_long_title_and_description_are_cut():
    """S4: title 300 characters; description 16,000, from Firecrawl 3,000 (A3)."""
    url, long = "https://a.example/", "x" * 100_000
    exa = call(engines.exa, reply({"results": [{"url": url, "title": long, "highlights": [long]}]}), "q", 5, "k")
    par = call(
        engines.parallel, reply({"results": [{"url": url, "title": long, "excerpts": [long, long]}]}), "q", 5, "k"
    )
    web = [
        {"url": url, "title": long, "description": long},
        {"url": url, "title": "t" * 300, "description": "d" * 3000},
    ]
    fire = call(engines.firecrawl, reply({"success": True, "data": {"web": web}}), "q", 5, "k")
    assert [len(out["rows"][0]["title"]) for out in (exa, par, fire)] == [300, 300, 300]
    assert [len(out["rows"][0]["description"]) for out in (exa, par, fire)] == [16000, 16000, 3000]
    assert fire["rows"][1] == {"url": url, "title": "t" * 300, "description": "d" * 3000, "position": 2}  # at the bound


@pytest.mark.parametrize(("chars", "highlights"), [(300, {"maxCharacters": 300}), (0, True)])
def test_exa_highlight_setting(chars, highlights):
    seen, handler = capture({"results": []})
    assert call(engines.exa, handler, "q", 5, "k", chars) == {"rows": []}
    assert seen["body"]["contents"] == {"highlights": highlights}


# --- A2 Parallel ----------------------------------------------------------------------------------


PARALLEL_BETA = (
    (),
    "https://api.parallel.ai/v1beta/search",
    "search-extract-2025-10-10",
    {"search_queries": ["what is x"], "objective": "what is x", "mode": "agentic", "max_results": 10},
)
PARALLEL_V1 = (
    (True,),
    "https://api.parallel.ai/v1/search",
    None,
    {
        "objective": "what is x",
        "search_queries": ["what is x"],
        "mode": "advanced",
        "advanced_settings": {"max_results": 10},
    },
)


@pytest.mark.parametrize(("extra", "url", "beta_header", "body"), [PARALLEL_BETA, PARALLEL_V1], ids=["beta", "v1"])
def test_parallel_request_and_rows(extra, url, beta_header, body):
    seen, handler = capture({"results": [{"url": "https://a.example/", "title": "A", "excerpts": ["x", "y"]}]})
    out = call(engines.parallel, handler, "what is x", 10, "par-key", *extra)
    assert seen["url"] == url
    assert seen["headers"]["x-api-key"] == "par-key"
    assert seen["headers"].get("parallel-beta") == beta_header
    assert seen["body"] == body
    assert out == {"rows": [{"url": "https://a.example/", "title": "A", "description": "x y", "position": 1}]}


def test_parallel_caps_results_at_20():
    seen, handler = capture({"results": []})
    call(engines.parallel, handler, "q", 50, "k")
    assert seen["body"]["max_results"] == 20
    call(engines.parallel, handler, "q", 50, "k", True)
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


@pytest.mark.parametrize(
    ("body", "detail"),
    [
        ({"success": False, "error": "Payment Required: no credits"}, "Payment Required: no credits"),
        ({"success": False, "error": {"message": "Rate limit"}}, "Rate limit"),
        ({"success": False, "error": "bad key fc-secret-123"}, "bad key [key]"),
    ],
)
def test_firecrawl_2xx_failure_keeps_its_reason(body, detail):
    """A3: success false with a reason names it; a 2xx status starts no pause (K5)."""
    out = call(engines.firecrawl, reply(body), "q", 5, "fc-secret-123")
    assert out == {"error": f"Firecrawl: {detail}", "code": "rejected", "status": None}


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
@pytest.mark.parametrize("code", [199, 300, 302, 400])
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
def test_api_error_json_without_a_known_field(fn, name):
    """A4: without tag, error or message the response text is the detail."""
    out = call(fn, reply({"requestId": "r1", "status": "busy"}, 429), "q", 5, "k")
    assert out == {"error": f'{name}: HTTP 429 {{"requestId":"r1","status":"busy"}}', "code": "http_429", "status": 429}


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


@pytest.mark.parametrize(("fn", "name"), ENGINES)
def test_error_text_is_one_printable_line(fn, name):
    """A4: a reply cannot add lines or control characters to the log."""
    reason = "NO_CREDITS\nERROR forged line\r\n\tx\x1b[31my\x00z\u2028w"
    out = call(fn, reply({"error": reason}, 402), "q", 5, "k")
    assert out == {
        "error": f"{name}: HTTP 402 NO_CREDITS ERROR forged line x [31my z w",
        "code": "http_402",
        "status": 402,
    }
    out = call(fn, lambda request: httpx.Response(500, text="  a\r\nb\tc  "), "q", 5, "k")
    assert out["error"] == f"{name}: HTTP 500 a b c"


def test_only_a_value_of_8_characters_or_more_is_masked():
    """S3: a shorter value is not taken for a key, so it cannot garble the text."""
    out = call(engines.firecrawl, lambda request: httpx.Response(200, text="no json"), "q", 5, "f")
    assert out["error"] == "Firecrawl: malformed reply"
    out = call(engines.exa, reply({"error": "bad key 1234567"}, 401), "q", 5, "1234567")
    assert out["error"] == "Exa: HTTP 401 bad key 1234567"
    out = call(engines.exa, reply({"error": "bad key 12345678"}, 401), "q", 5, "12345678")
    assert out["error"] == "Exa: HTTP 401 bad key [key]"


def test_key_is_masked_in_any_case_and_percent_encoded():
    """S3: as in extract-chain."""
    text = "keys EXA-SE/CRET+X and exa-SE%2FCRET%2Bx and exa-se%2fcret%2bx rejected"
    out = call(engines.exa, reply({"error": text}, 401), "q", 5, "exa-SE/CRET+x")
    assert out["error"] == "Exa: HTTP 401 keys [key] and [key] and [key] rejected"


def test_key_is_masked_before_the_text_is_shortened(monkeypatch):
    """A4: masking sees the whole reply, so no part of a key is left where the cleaned-up text ends."""
    monkeypatch.setattr(engines, "ERROR_SCAN", 30)
    key = "SECRET-KEY-0123456789"
    out = call(engines.exa, reply({"error": "x" * 15 + key}, 401), "q", 5, key)
    assert out["error"] == "Exa: HTTP 401 " + "x" * 15 + "[key]"
    out = call(engines.exa, reply({"error": "y" * 100}, 401), "q", 5, key)
    assert out["error"] == "Exa: HTTP 401 " + "y" * 21  # only the first 30 characters are looked at


@pytest.mark.parametrize(("fn", "name"), ENGINES)
def test_reply_the_parser_gives_up_on(fn, name):
    """A4, K5: a body nested too deeply to parse keeps the status of an error reply; as a 2xx it is malformed."""
    deep = "[" * 200_000
    out = call(fn, lambda request: httpx.Response(402, text=deep), "q", 5, "k")
    assert (out["code"], out["status"]) == ("http_402", 402)
    out = call(fn, lambda request: httpx.Response(200, text=deep), "q", 5, "k")
    assert out == {"error": f"{name}: malformed reply", "code": "malformed", "status": None}


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


@pytest.mark.parametrize(("fn", "name"), ENGINES)
@pytest.mark.parametrize(("query", "key"), [("q", "key-with\u200bzero-width-space"), ("q\ud800", "k")])
def test_request_that_cannot_be_built_is_no_malformed_reply(fn, name, query, key):
    """A4: nothing was sent, so this is no reply at all; the exception class names the cause."""
    sent = []

    def handler(request):
        sent.append(request)
        return httpx.Response(200, json={})

    out = call(fn, handler, query, 5, key)
    assert sent == []
    assert out == {"error": f"{name}: UnicodeEncodeError", "code": "UnicodeEncodeError", "status": None}
