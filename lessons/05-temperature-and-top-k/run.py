"""Chapter 05: temperature, top-k and top-p, on a real next-token distribution."""

import math
import random
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import sampling  # noqa: E402
from sampling import (  # noqa: E402
    captured_distribution,
    first_token_distribution,
    normalise,
    northwind_messages,
)

from lantern import case, chat, learn  # noqa: E402
from lantern.config import tier  # noqa: E402
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


# With --mine, the sampler is yours: practice/exercise.py (with_temperature, top_k, top_p,
# sampler_chain, draw). Without it, the lesson's own sampling.py.
MINE = learn.mine()
S = MINE or sampling
HOSTED = tier() == "hosted"


def bar(p: float, width: int = 30) -> str:
    return "#" * round(p * width)


def names_plate(text: str) -> bool:
    return "KB 714 FLR" in re.sub(r"\s+", " ", text.upper())


step("1. What the model actually produces: a probability for every next token")
if HOSTED:
    note("Claude returns no log-probabilities (`logprobs` is reported as not supported), so a "
         "hosted run cannot show its own distribution. Steps 2 and 3 use the qwen3:1.7b "
         "distribution captured by `make charts` (docs/explorer/data.js) instead.")
    dist = captured_distribution("northwind")
else:
    r = chat(northwind_messages(), temperature=1.0, top_k=40, top_p=1.0, logprobs=20,
             max_tokens=1)
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

p_raw = math.exp(dist[0][1])
p_scaled = dict(S.with_temperature(dist, 0.2))[dist[0][0]]
if HOSTED:
    note("Skipped on the hosted tier: comparing raw log-probabilities at two temperatures needs "
         "log-probabilities, and Claude takes no temperature either.")
else:
    r_cold = chat(northwind_messages(), temperature=0.2, top_k=40, top_p=1.0, logprobs=20,
                  max_tokens=1)
    p_cold = math.exp(first_token_distribution(r_cold)[0][1])
    note(f"Asked again at temperature 0.2, Ollama reports {dist[0][0]!r} at {p_cold:.3f} "
         f"(it was {p_raw:.3f} at T=1). If temperature were applied to these numbers it would "
         f"be {p_scaled:.3f}. So the log-probabilities are the model's raw scores; the sampler "
         "applies temperature afterwards. (If the two raw numbers differ a little, that is server "
         "state, not temperature. Chapter 06 shows why.)")

p_fav = learn.predict(
    f"At T = 0.2, what share of the probability will the favourite, {dist[0][0]!r}, get?",
    ["under 50%", "50% to 80%", "over 80%"],
)
step("2. Temperature reshapes the distribution")
temps = [0.2, 0.7, 1.0, 1.5]
shaped = {T: dict(S.with_temperature(dist, T)) for T in temps}
t = Table(title="Same scores, four temperatures")
t.add_column("token")
for T in temps:
    t.add_column(f"T={T}", justify="right")
for tok, _ in dist[:8]:
    t.add_row(repr(tok), *(f"{shaped[T][tok]:.3f}" for T in temps))
console.print(t)
note("Low T: the favourite takes almost everything. High T: the long tail gets a real chance.")
fav_t02 = shaped[0.2][dist[0][0]]
learn.reveal(p_fav, answer=learn.bucket(fav_t02, [0.5, 0.8]),
             why=f"Dividing log-probabilities by 0.2 multiplies the gaps between them by five, "
                 f"so {p_raw:.2f} raw becomes {fav_t02:.2f}. Temperature never changes the "
                 "order of the tokens, only how far apart they are.")

TOP_K, TOP_P = 3, 0.9
p_kept = learn.predict(
    f"top_k={TOP_K} keeps {TOP_K} tokens. How many will top_p={TOP_P} keep?",
    ["1 or 2", "3 to 5", "6 or more"],
)
step("3. Top-k and top-p cut the tail before the draw")
probs = normalise([(tok, math.exp(lp)) for tok, lp in dist])
k3 = S.top_k(probs, TOP_K)
p90 = S.top_p(probs, TOP_P)
console.print(f"top_k={TOP_K} keeps {len(k3)} tokens: " + ", ".join(repr(x) for x, _ in k3))
console.print(f"top_p={TOP_P} keeps {len(p90)} tokens: " + ", ".join(repr(x) for x, _ in p90))
note("top_k is a fixed count. top_p adapts: few tokens when the model is sure, "
     "many when it is not.")
learn.reveal(p_kept, answer=learn.bucket(len(p90), [2, 5]),
             why=f"No token here is dominant: the favourite has {p_raw:.2f}, so it takes "
                 f"{len(p90)} tokens to reach {TOP_P:.0%} of the probability. On the plate "
                 "question, where one token has nearly all of it, top_p keeps one.")
# The whole chain, then 1,000 seeded draws from it: the sampler, run offline.
chain = S.sampler_chain(dist, temperature=1.0, k=40, p=TOP_P)
reference = sampling.sampler_chain(dist, temperature=1.0, k=40, p=TOP_P)
ref = {t: w for t, w in reference if w > 0}
got = {t: w for t, w in chain if w > 0}
chain_matches = got.keys() == ref.keys() and all(abs(got[t] - ref[t]) < 1e-9 for t in ref)
rng = random.Random(5)
draws = Counter(S.draw(chain, rng) for _ in range(1000))
sim_tok, sim_n = draws.most_common(1)[0]
console.print(f"1,000 seeded draws through the chain (T=1.0, top_k=40, top_p={TOP_P}): "
              f"{len(draws)} distinct tokens, {sim_tok!r} {sim_n / 10:.1f}% of the time.")

p_words = learn.predict("Eight seeds at T = 1.5: how many distinct first words?",
                        ["1", "2 or 3", "4 or more"])
step("4. Drawing for real: eight runs at three temperatures")
if HOSTED:
    note("Claude takes no temperature, top_k, top_p or seed (each is reported, not sent). On the "
         "hosted tier the three rows below are the same request eight times, so any variety "
         "comes from the provider's own sampling, not from the dial.")
distinct: dict[float, int] = {}
for T in (0.2, 1.0, 1.5):
    words = []
    for seed in range(1, 9):
        out = chat(northwind_messages(), temperature=T, top_k=40, top_p=1.0, seed=seed,
                   max_tokens=3)
        words.append(out.text.split()[0] if out.text.split() else "(empty)")
    counts = Counter(words)
    distinct[T] = len(counts)
    console.print(f"T={T:<4} {len(counts)} distinct first words: "
                  + ", ".join(f"{w} x{c}" for w, c in counts.most_common()))

learn.reveal(p_words, answer=learn.bucket(distinct[1.5], [1, 3]),
             why=f"At T = 0.2 the eight seeds gave {distinct[0.2]} distinct word(s); at T = 1.5, "
                 f"{distinct[1.5]}. Heat flattens the distribution, so the seed's random number "
                 "lands in the tail more often.")

p_plate = learn.predict("At T = 1.8, how many of the two hot replies will still name KB 714 FLR?",
                        ["both", "one", "neither"])
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
hot_reads = 0
for seed in (3, 11):
    hot = chat(plate_q, temperature=1.8, top_k=100, top_p=1.0, seed=seed, max_tokens=40)
    hot_reads += names_plate(hot.text)
    reply(f"T=1.8, seed {seed}", hot.text, style="yellow")
learn.reveal(p_plate, answer=2 - hot_reads,
             why="The plate has one answer and the model is close to certain of each token, so "
                 "even a flat temperature has almost nothing in the tail to pick. Temperature "
                 "makes a model random only where it was unsure.")

step("6. Okafor's question: brainstorm leads. High temperature.")
leads_q = ("Northwind Freight Ltd: paid 62,500 then 71,200 then 94,000 by Halcyon Maritime, no "
           "ships, no staff, PO box and bank account in Port Sabran, no VAT number. List three "
           "short, distinct hypotheses an investigator should check. One line each.")
for T, seed in ((0.2, 1), (0.2, 2), (1.3, 1), (1.3, 2)):
    out = chat(leads_q, temperature=T, seed=seed, max_tokens=160)
    reply(f"T={T}, seed {seed}", out.text, style="green" if T < 1 else "yellow")
note("At T=0.2 the two seeds give similar lists. At T=1.3 they diverge: "
     "different leads, and more nonsense to filter.")

learn.record(
    live_distribution=not HOSTED,
    top_token_raw=round(p_raw, 4),
    favourite_t02=round(fav_t02, 4),
    top_k_kept=len(k3),
    top_p_kept=len(p90),
    chain_matches=chain_matches,
    sim_distinct=len(draws),
    sim_top_share=round(sim_n / 1000, 3),
    distinct_t02=distinct[0.2],
    distinct_t10=distinct[1.0],
    distinct_t15=distinct[1.5],
    plate_t0=names_plate(cold.text),
    plate_hot_reads=hot_reads,
    mine=bool(MINE),
)

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
