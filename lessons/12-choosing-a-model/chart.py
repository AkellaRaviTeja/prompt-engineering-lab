"""Draw the chapter 12 scorecard: accuracy against speed, bubble size is memory."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from lantern.config import ROOT  # noqa: E402


def draw(results: list[dict]) -> Path:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))
    names = [r["model"] for r in results]
    colours = ["#9aa5b1", "#d98e04", "#2b3a55"]

    ax1.bar(names, [r["accuracy"] * 100 for r in results], color=colours)
    ax1.set_ylim(0, 100)
    ax1.set_ylabel("classification accuracy (%)")
    ax1.set_title("Accuracy on 16 case messages")
    for i, r in enumerate(results):
        ax1.text(i, r["accuracy"] * 100 + 2, f"{r['accuracy']:.0%}", ha="center")

    for r, c in zip(results, colours, strict=True):
        ax2.scatter(r["tokens_per_s"], r["accuracy"] * 100, s=r["memory_gb"] * 400, color=c,
                    alpha=0.8)
        radius = (r["memory_gb"] * 400) ** 0.5 / 2
        ax2.annotate(f"{r['model']}\n{r['memory_gb']:.1f} GB", (r["tokens_per_s"],
                     r["accuracy"] * 100), textcoords="offset points",
                     xytext=(0, -radius - 22), ha="center", fontsize=8)
    ax2.set_xlabel("generation speed (tokens/s, CPU)")
    ax2.set_ylabel("accuracy (%)")
    ax2.set_ylim(0, 110)
    fastest = max(r["tokens_per_s"] for r in results)
    ax2.set_xlim(0, fastest * 1.2)
    ax2.set_title("The trade: faster or more accurate (bubble = memory)")
    fig.tight_layout()
    out = ROOT / "docs" / "charts" / "12-model-scorecard.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out
