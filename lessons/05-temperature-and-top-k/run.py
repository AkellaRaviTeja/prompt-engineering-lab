"""Chapter 05: temperature, top-k and top-p, on a real next-token distribution."""

import math
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sampling import (  # noqa: E402
    first_token_distribution,
    normalise,
    northwind_messages,
    top_k,
    top_p,
    with_temperature,
)

from lantern import case, chat  # noqa: E402
from lantern.ui import (  # noqa: E402
    Table,
    chapter,
    console,
    evidence,
    finding,
    note,
    reply,
    save_shot,
    step,
    your_turn,
)

chapter("05", "Two kinds of question", """
Okafor has pinned a single word to the board above his desk: NORTHWIND. "I need ideas," he
says. "Every way a company with no ships could earn ninety thousand a month." Varma, from the
doorway: "And I need one plate number, read correctly, from a camera log. Not ideas. One
answer." Same workstation, same model. The difference is a dial.
""")


def bar(p: float, width: int = 30) -> str:
    return "#" * round(p * width)


step("1. What the model actually produces: a probability for every next token")
r = chat(northwind_messages(), temperature=1.0, top_k=40, top_p=1.0, logprobs=20, max_tokens=1)
dist = first_token_distribution(r)
note("Prompt ends with the assistant already saying 'Northwind is most likely a'. "
     "We ask for one token and its 20 most likely alternatives.")
t = Table(title="Next token after 'Northwind is most likely a' (qwen3:1.7b, raw)")
t.add_column("token")
t.add_column("probability", justify="right")
t.add_column("")
for tok, lp in dist[:10]:
    t.add_row(repr(tok), f"{math.exp(lp):.3f}", bar(math.exp(lp)))
console.print(t)

r_cold = chat(northwind_messages(), temperature=0.2, top_k=40, top_p=1.0, logprobs=20,
              max_tokens=1)
p_raw = math.exp(dist[0][1])
p_cold = math.exp(first_token_distribution(r_cold)[0][1])
p_scaled = dict(with_temperature(dist, 0.2))[dist[0][0]]
note(f"Asked again at temperature 0.2, Ollama reports {dist[0][0]!r} at {p_cold:.3f} "
     f"(it was {p_raw:.3f} at T=1). If temperature were applied to these numbers it would be "
     f"{p_scaled:.3f}. So the log-probabilities are the model's raw scores; the sampler applies "
     "temperature afterwards. (If the two raw numbers differ a little, that is server state, "
     "not temperature. Chapter 06 shows why.)")

step("2. Temperature reshapes the distribution")
temps = [0.2, 0.7, 1.0, 1.5]
shaped = {T: dict(with_temperature(dist, T)) for T in temps}
t = Table(title="Same scores, four temperatures")
t.add_column("token")
for T in temps:
    t.add_column(f"T={T}", justify="right")
for tok, _ in dist[:8]:
    t.add_row(repr(tok), *(f"{shaped[T][tok]:.3f}" for T in temps))
console.print(t)
note("Low T: the favourite takes almost everything. High T: the long tail gets a real chance.")

step("3. Top-k and top-p cut the tail before the draw")
probs = normalise([(tok, math.exp(lp)) for tok, lp in dist])
k3 = top_k(probs, 3)
p90 = top_p(probs, 0.9)
console.print(f"top_k=3 keeps {len(k3)} tokens: " + ", ".join(repr(x) for x, _ in k3))
console.print(f"top_p=0.9 keeps {len(p90)} tokens: " + ", ".join(repr(x) for x, _ in p90))
note("top_k is a fixed count. top_p adapts: few tokens when the model is sure, "
     "many when it is not.")

step("4. Drawing for real: eight runs at three temperatures")
for T in (0.2, 1.0, 1.5):
    words = []
    for seed in range(1, 9):
        out = chat(northwind_messages(), temperature=T, top_k=40, top_p=1.0, seed=seed,
                   max_tokens=3)
        words.append(out.text.split()[0] if out.text.split() else "(empty)")
    counts = Counter(words)
    console.print(f"T={T:<4} {len(counts)} distinct first words: "
                  + ", ".join(f"{w} x{c}" for w, c in counts.most_common()))

step("5. Varma's question: read the plate. Low temperature.")
camera = case.read("gate-camera-log.csv")
vehicles = [ln for ln in case.read("site-facts.md").splitlines() if "plate" in ln]
evidence("gate-camera-log.csv (23:47) and site-facts.md (vehicles)",
         [ln for ln in camera.splitlines() if "23:47" in ln][0] + "\n\n" + "\n".join(vehicles))
plate_q = ("The gate camera recorded a partial plate 'KB 7?4 ?LR', where ? is an unreadable "
           "character. Which registered vehicle matches it? Reply with the plate and the owner "
           "only.\n\n<vehicles>\n" + "\n".join(vehicles) + "\n</vehicles>")
cold = chat(plate_q, temperature=0, max_tokens=40)
reply("T=0", cold.text)
for seed in (3, 11):
    hot = chat(plate_q, temperature=1.8, top_k=100, top_p=1.0, seed=seed, max_tokens=40)
    reply(f"T=1.8, seed {seed}", hot.text, style="yellow")

step("6. Okafor's question: brainstorm leads. High temperature.")
leads_q = ("Northwind Freight Ltd: paid 62,500 then 71,200 then 94,000 by Halcyon Maritime, no "
           "ships, no staff, PO box and bank account in Port Sabran, no VAT number. List three "
           "short, distinct hypotheses an investigator should check. One line each.")
for T, seed in ((0.2, 1), (0.2, 2), (1.3, 1), (1.3, 2)):
    out = chat(leads_q, temperature=T, seed=seed, max_tokens=160)
    reply(f"T={T}, seed {seed}", out.text, style="green" if T < 1 else "yellow")
note("At T=0.2 the two seeds give near identical lists. At T=1.3 they diverge: "
     "different leads, and more nonsense to filter.")

your_turn(
    "05",
    check=[
        "In the step 1 table, how much does the top token get, and how close is the second? "
        "Follow that token across the step 2 columns.",
        "In step 4, count the distinct first words at each temperature. Where does the count jump?",
        "In step 5, do all three replies give the same plate and owner? Check them against the "
        "vehicles in case/site-facts.md.",
    ],
    exercises=[
        "No edit: open docs/explorer/index.html in a browser. Set T = 0.05, draw 100 tokens, then "
        "T = 2. How many distinct tokens appear?",
        "In the explorer, set top_p = 0.5 on the Northwind distribution. How many tokens survive? "
        "Then switch to the plate distribution.",
        "In run.py, in `leads_q`, change 'List three short, distinct hypotheses' to 'List ten "
        "distinct hypotheses' and raise max_tokens=160 to 400. Compare T=0.2 with your earlier "
        "T=1.3 lists.",
        "In run.py, step 4, change top_k=40 to top_k=1. Why is every answer at T=1.5 now the same?",
    ],
)

finding("""
The camera's partial plate KB 7?4 ?LR matches one registered vehicle in the Gate 2 car park:
KB 714 FLR, a grey saloon belonging to Raj Malhotra. It left at 23:47 and came back at 23:59.

Okafor reads the brainstormed leads, crosses out the ones that only rephrase "fraud", and
circles one he wrote himself: invoices timed to someone's travel. "Ideas are cheap," Varma
says. "Readings are not. Know which one you are asking for."
""")
save_shot("05-temperature-and-top-k")
