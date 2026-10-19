"""T2: live check through Hermes' real web_search path, without an LLM.

Run with the Python interpreter of a Hermes installation (isolated mode), e.g. Hermes Desktop on Windows:

    <hermes python> -I scripts/live_check.py PROFILE [--break exa[,parallel,...]] [--pace 7.5] [QUERY ...]

PROFILE   Hermes profile with the plugin installed, web.search_backend: search-chain and
          web.keyless_rescue: false. Its .env provides the keys. "default" is the Hermes home itself.
--break   replace the key of these stages with an invalid value inside this process, so the stage answers
          with an error (usually HTTP 401) and the next stage has to serve; for searxng and degoog the address
          is replaced with one where nothing listens, so the stage fails with a transport error.
          A stage without a key or address in the profile is switched on this way, too.
--pace    wait after each query in seconds (default 7.5: below 8 requests/min per provider).

Hermes is found under %LOCALAPPDATA%/hermes, i.e. Hermes Desktop on Windows (override with HERMES_ROOT).
Prints one line per query: the plugin's log line, the number of results and their size. No result texts.
"""

import argparse
import json
import logging
import os
import sys
import time

ROOT = os.environ.get("HERMES_ROOT") or os.path.join(os.environ.get("LOCALAPPDATA", ""), "hermes")
QUERIES = [
    "python asyncio timeout context manager",
    "caddy reverse proxy websocket",
    "postgresql latest stable release",
]
SETTINGS = {
    "exa": "EXA_API_KEY",
    "parallel": "PARALLEL_API_KEY",
    "brave": "BRAVE_SEARCH_API_KEY",
    "nimble": "NIMBLE_API_KEY",
    "tavily": "TAVILY_API_KEY",
    "youcom": "YDC_API_KEY",
    "searxng": "SEARXNG_URL",
    "degoog": "DEGOOG_URL",
    "firecrawl": "FIRECRAWL_API_KEY",
}
BROKEN = {"SEARXNG_URL": "http://127.0.0.1:9", "DEGOOG_URL": "http://127.0.0.1:9"}  # nothing listens on port 9
OTHER = ("SEARCH_CHAIN_ORDER", "SEARCH_CHAIN_EXA_HIGHLIGHT_CHARS", "SEARCH_CHAIN_PARALLEL_API")


def hermes_env(profile):
    """Load Hermes for one profile; keys and settings only from the profile's .env, not from the shell."""
    home = ROOT if profile == "default" else os.path.join(ROOT, "profiles", profile)
    os.environ["HERMES_HOME"] = home
    for k in [k for k in os.environ if k.endswith("_API_KEY") or k in (*SETTINGS.values(), *OTHER)]:
        os.environ.pop(k)
    sys.path.insert(0, os.path.join(ROOT, "hermes-agent"))
    import hermes_bootstrap  # noqa: F401
    from hermes_cli.env_loader import load_hermes_dotenv

    load_hermes_dotenv(hermes_home=home)


class Collect(logging.Handler):
    """Collects the plugin's log lines of the current call."""

    def __init__(self):
        super().__init__(logging.INFO)
        self.lines = []

    def emit(self, record):
        if record.getMessage().startswith("search-chain: "):
            self.lines.append(record.getMessage())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("profile")
    parser.add_argument("--break", dest="broken", default="")
    parser.add_argument("--pace", type=float, default=7.5)
    parser.add_argument("queries", nargs="*")
    args = parser.parse_args()
    broken = [stage for stage in args.broken.split(",") if stage]
    if unknown := [stage for stage in broken if stage not in SETTINGS]:
        parser.error(f"--break: unknown stage {unknown[0]!r}, choose from {', '.join(SETTINGS)}")
    if not 0 <= args.pace < 3600:
        parser.error("--pace must be a number of seconds from 0 to below 3600")
    sys.stdout.reconfigure(encoding="utf-8")
    hermes_env(args.profile)
    for stage in broken:
        setting = SETTINGS[stage]
        os.environ[setting] = BROKEN.get(setting, "invalid-key-for-live-check")

    # Written against Hermes 0.21.6: these are internal names of Hermes and may move with an update.
    from agent.web_search_registry import get_provider
    from tools.web_tools import _ensure_web_plugins_loaded, _get_search_backend, _load_web_config, web_search_tool

    _ensure_web_plugins_loaded()
    if _get_search_backend() != "search-chain":
        sys.exit(f"search backend is {_get_search_backend()!r}, not 'search-chain'")
    if not get_provider("search-chain"):
        sys.exit("plugin not loaded (plugins.enabled?)")
    if _load_web_config().get("keyless_rescue", True) is not False:
        sys.exit("set web.keyless_rescue: false")

    collect = Collect()
    logging.getLogger().addHandler(collect)
    logging.getLogger().setLevel(min(logging.getLogger().level or logging.INFO, logging.INFO))

    counts = dict.fromkeys(SETTINGS, 0)
    for query in args.queries or QUERIES:
        collect.lines = []
        start = time.time()
        raw = web_search_tool(query, 5)
        duration = round(time.time() - start, 1)
        try:
            data = json.loads(raw)
        except ValueError:
            data = {}
        rows = (data.get("data") or {}).get("web") or []
        # the plugin's INFO line (L1); the WARNING lines of S5 and L2 are left out
        info = [line for line in collect.lines if "paused for" not in line and "call failed" not in line]
        steps = info[-1].split(": ", 1)[1] if info else "(no log line: served from Hermes' cache?)"
        for stage in SETTINGS:
            if f"{stage}=" in steps and not any(
                f"{stage}={skip}" in steps for skip in ("no_key", "no_url", "bad_url", "paused")
            ):
                counts[stage] += 1
        print(f"{duration:>5} s  {steps:<60} rows={len(rows)} chars={len(raw):>6}  "
              f"{(data.get('error') or '')[:90]}", flush=True)  # fmt: skip
        time.sleep(args.pace)
    print("requests per provider:", counts)


if __name__ == "__main__":
    main()
