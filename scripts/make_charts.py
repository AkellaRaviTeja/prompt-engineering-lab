"""Build the charts for chapters 05 and 06 and the data for the sampling explorer.

Every number comes from a live run against the local model:
  docs/charts/05-temperature.png     one real distribution at four temperatures
  docs/charts/05-topk-topp.png       which tokens top_k and top_p keep
  docs/charts/06-distinct-answers.png  distinct answers across repeated runs
  docs/explorer/data.js              distributions embedded in the explorer page
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lessons" / "05-temperature-and-top-k"))

from sampling import (  # noqa: E402
    first_token_distribution,
    normalise,
    northwind_messages,
    top_k,
    top_p,
    with_temperature,
)

from lantern import case, chat  # noqa: E402

CHARTS = ROOT / "docs" / "charts"
INK, MUTED, ACCENT, CUT = "#1f2937", "#9ca3af", "#b45309", "#e5e7eb"


def label(tok: str) -> str:
    if tok.strip("_ ") == "" and "_" in tok:
        return "(blank line ____)"
    return repr(tok)[1:-1] or "(empty)"


def capture() -> dict[str, dict]:
    vehicles = [ln for ln in case.read("site-facts.md").splitlines() if "plate" in ln]
    plate = [
        {"role": "user", "content": "The gate camera read a partial plate 'KB 7?4 ?LR'. Which "
         "registered plate matches?\n" + "\n".join(vehicles)},
        {"role": "assistant", "content": "The matching plate is KB"},
    ]
    out = {}
    for key, title, msgs in (
        ("northwind", "Northwind is most likely a ...", northwind_messages()),
        ("plate", "The matching plate is KB ...", plate),
    ):
        r = chat(msgs, temperature=1.0, top_k=40, top_p=1.0, logprobs=20, max_tokens=1)
        out[key] = {"title": title, "model": r.model,
                    "tokens": [[t, lp] for t, lp in first_token_distribution(r)]}
    return out


def chart_temperature(dist) -> None:
    temps = [0.2, 0.7, 1.0, 1.5]
    fig, axes = plt.subplots(1, 4, figsize=(14, 4), sharey=True)
    toks = [t for t, _ in dist[:10]]
    for ax, T in zip(axes, temps, strict=True):
        probs = dict(with_temperature(dist, T))
        vals = [probs[t] for t in toks]
        ax.barh(range(len(toks)), vals, color=[ACCENT] + [INK] * (len(toks) - 1))
        ax.set_title(f"temperature {T}", color=INK)
        ax.set_xlim(0, 1)
        ax.set_yticks(range(len(toks)), [label(t) for t in toks])
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    axes[0].invert_yaxis()  # shared y axis: invert once, most likely token on top
    fig.suptitle("One real next-token distribution (qwen3:1.7b), reshaped by temperature",
                 color=INK)
    fig.tight_layout()
    fig.savefig(CHARTS / "05-temperature.png", dpi=130)
    plt.close(fig)


def chart_cutoffs(dist) -> None:
    probs = normalise([(t, math.exp(lp)) for t, lp in dist])[:12]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2), sharey=True)
    for ax, (name, kept) in zip(axes, (("top_k = 3", top_k(probs, 3)),
                                        ("top_p = 0.9", top_p(probs, 0.9))), strict=True):
        keep = {t for t, _ in kept}
        ax.barh(range(len(probs)), [p for _, p in probs],
                color=[ACCENT if t in keep else CUT for t, _ in probs],
                edgecolor=[INK if t in keep else MUTED for t, _ in probs])
        ax.set_yticks(range(len(probs)), [label(t) for t, _ in probs])
        ax.set_title(f"{name}: keeps {len(keep)} tokens (orange), drops the rest", color=INK)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    axes[0].invert_yaxis()
    fig.tight_layout()
    fig.savefig(CHARTS / "05-topk-topp.png", dpi=130)
    plt.close(fig)


def chart_distinct() -> None:
    temps = [0.0, 0.3, 0.7, 1.0, 1.5]
    runs = 8
    varied, fixed = [], []
    for T in temps:
        a = {chat(northwind_messages(), temperature=T, seed=s, max_tokens=4).text
             for s in range(1, runs + 1)}
        b = {chat(northwind_messages(), temperature=T, seed=7, max_tokens=4).text
             for _ in range(runs)}
        varied.append(len(a))
        fixed.append(len(b))
        print(f"  T={T}: {len(a)} distinct with new seeds, {len(b)} with seed 7")
    fig, ax = plt.subplots(figsize=(8, 4))
    x = range(len(temps))
    ax.bar([i - 0.2 for i in x], varied, width=0.4, color=ACCENT, label="new seed every run")
    ax.bar([i + 0.2 for i in x], fixed, width=0.4, color=INK, label="same seed (7) every run")
    ax.set_xticks(list(x), [f"T={t}" for t in temps])
    ax.set_ylabel(f"distinct answers in {runs} runs")
    ax.set_ylim(0, runs + 0.5)
    ax.legend(frameon=False)
    ax.set_title("Same prompt, repeated: temperature creates variety, a fixed seed removes it",
                 color=INK)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    fig.savefig(CHARTS / "06-distinct-answers.png", dpi=130)
    plt.close(fig)


def main() -> int:
    CHARTS.mkdir(parents=True, exist_ok=True)
    data = capture()
    js = "// Captured by scripts/make_charts.py from a live run. Do not edit by hand.\n"
    js += "window.DISTRIBUTIONS = " + json.dumps(data, indent=1) + ";\n"
    (ROOT / "docs" / "explorer" / "data.js").write_text(js, encoding="utf-8")
    dist = [(t, lp) for t, lp in data["northwind"]["tokens"]]
    chart_temperature(dist)
    chart_cutoffs(dist)
    chart_distinct()
    made = sorted(CHARTS.glob("0[56]-*.png"))
    print(f"charts: wrote {len(made)} charts and docs/explorer/data.js")
    return 0 if len(made) >= 3 else 1


if __name__ == "__main__":
    sys.exit(main())
