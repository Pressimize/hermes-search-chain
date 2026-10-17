import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "recompute.py"


def run(capsys):
    spec = importlib.util.spec_from_file_location("recompute", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main()
    return capsys.readouterr().out


def test_run2_characters_of_a_column_that_ran_only_on_the_extra_block(capsys):
    """Firecrawl ran only on the extra block in run 2; evaluation.md gives its 3,900 characters from there."""
    line = next(line for line in run(capsys).splitlines() if line.strip().startswith("firecrawl ") and "16" in line)
    assert "None" not in line
    assert line.endswith("3925.0 chars (extra block)")


def test_run2_characters_of_the_other_columns_stay_on_the_main_set(capsys):
    out = run(capsys)
    exa = next(line for line in out.splitlines() if line.strip().startswith("exa ") and " 73 " in line)
    assert exa.endswith("12002.5 chars")
