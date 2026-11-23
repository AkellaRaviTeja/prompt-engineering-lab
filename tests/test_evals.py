"""The promptfoo suite: schema-constrained extraction and a calibrated judge.

Regression tests for the review of 21 November 2026: the extraction suite stripped code fences
with a regex instead of using chapter 08's schema-constrained path, and the no-speculation rubric
was graded by qwen3:1.7b, one of the models under test.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

from lantern.testing import Scripted, say

ROOT = Path(__file__).resolve().parents[1]
EVALS = ROOT / "evals"
sys.path.insert(0, str(EVALS / "judge"))

import calibrate  # noqa: E402
import judge  # noqa: E402

CONFIG = yaml.safe_load((EVALS / "promptfooconfig.yaml").read_text())
TESTS = {n: yaml.safe_load((EVALS / "tests" / n).read_text())
         for n in ("extraction.yaml", "classification.yaml", "rules.yaml")}


def test_extraction_has_no_fence_stripping_transform():
    assert TESTS["extraction.yaml"], "no extraction tests"
    for t in TESTS["extraction.yaml"]:
        assert "transform" not in json.dumps(t), f"{t['description']} still strips fences"


def test_every_prompt_runs_through_lantern_with_the_schema_for_extraction():
    for name in ("promptfooconfig.yaml", "promptfooconfig.hosted.yaml"):
        cfg = yaml.safe_load((EVALS / name).read_text())
        assert cfg["providers"], f"{name}: no providers"
        for p in cfg["providers"]:
            assert p["id"] == "file://providers/lantern_provider.py", f"{name}: {p['id']}"
            assert "prompts" not in p, f"{name}: a provider-level prompts filter drops tests"
            ref = p["config"]["schemas"]["extract-invoice"]
            schema = json.loads((EVALS / ref[len("file://"):]).read_text())
            assert set(schema["required"]) == {"invoice_id", "vendor", "date", "total"}
    labels = [p["label"] for p in CONFIG["providers"]]
    assert labels == ["qwen3-1.7b", "qwen3-0.6b"], "both models run every suite, once each"


def test_provider_sends_the_schema_to_lantern_chat(monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "lantern_provider", EVALS / "providers" / "lantern_provider.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    model = Scripted([say('{"invoice_id": "NW-0419", "vendor": "Northwind", '
                          '"date": "2026-03-02", "total": 94000.0}', prompt=300, out=30)])
    monkeypatch.setattr(mod, "chat", model)
    out = mod.call_api(json.dumps([{"role": "user", "content": "INVOICE NW-0419"}]),
                       {"config": {"model": "qwen3:1.7b",
                                   "schemas": {"extract-invoice": "file://schemas/invoice.json"}}},
                       {"prompt": {"label": "extract-invoice"}})
    sent = model.requests[0]
    assert sent["format"]["required"] == ["invoice_id", "vendor", "date", "total"]
    assert sent["prompt_version"] == "extract-invoice@v1"
    assert json.loads(out["output"])["total"] == 94000.0
    assert out["tokenUsage"]["total"] == 330


def test_no_rubric_is_graded_by_a_model_under_test():
    under_test = {p["config"]["model"] for p in CONFIG["providers"]}
    assert judge.JUDGE_MODEL not in under_test
    for t in TESTS["rules.yaml"]:
        for a in t["assert"]:
            assert a["type"] != "llm-rubric", "use the calibrated judge, not an inline rubric"
            if a.get("metric") == "no_speculation":
                assert a["value"] == "file://judge/assert_no_speculation.py"


def test_kappa_and_rates():
    perfect = calibrate.score([(True, True)] * 6 + [(False, False)] * 6)
    assert perfect["agreement"] == 1 and perfect["kappa"] == pytest.approx(1.0)
    # a judge that passes everything agrees half the time and has zero kappa
    lenient = calibrate.score([(True, True)] * 6 + [(False, True)] * 6)
    assert lenient["agreement"] == 0.5 and lenient["kappa"] == pytest.approx(0.0)
    assert lenient["true_fail_rate"] == 0.0


def test_labels_are_balanced_and_hard():
    labels = [json.loads(x) for x in (EVALS / "judge" / "labels.jsonl").read_text().splitlines()]
    passes = sum(x["label"] == "pass" for x in labels)
    assert len(labels) >= 20 and passes == len(labels) - passes


def test_judge_fails_closed_on_a_cut_off_verdict():
    passed, reason = judge.judge("Malhotra", "Who?", chat=Scripted([say('{"reason": "Mal')]))
    assert passed is False and "not valid JSON" in reason


def test_assertion_refuses_an_uncalibrated_judge(monkeypatch):
    import assert_no_speculation as a

    monkeypatch.setattr(a, "calibration", lambda: None)
    out = a.get_assert("Not in evidence.", {"vars": {"question": "Who?"}})
    assert out["pass"] is False and "not calibrated" in out["reason"]
    monkeypatch.setattr(a, "calibration", lambda: {"judge_model": "qwen3:4b", "kappa": 0.3})
    assert a.get_assert("x", {"vars": {"question": "Who?"}})["pass"] is False
