from cloneclient.domain.diagnostics import build_diagnostics


def test_build_diagnostics_keeps_order() -> None:
    report = build_diagnostics({"B": "2", "A": "1"})

    assert report == "B: 2\nA: 1"


def test_build_diagnostics_handles_empty_mapping() -> None:
    assert build_diagnostics({}) == ""
