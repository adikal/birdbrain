"""Milestone 5 report (ledger E-019): skills written by the cloud brain, and what they did.

    .venv/bin/python scripts/skills_report.py control.jsonl authoring.jsonl --lives data/lifetimes/<tag>

Prints, for the authoring arm's lives (memory directories): every skill written, the
situation it was written for, its trial counts against its parent, and its status; then,
pooled over lives, success and falls of written skills against their parents in the same
situations; then toys in the basket and falls per room, authoring minus control, paired
by life (rooms `--late` on). `--runs data/runs` recounts pick decisions from the event logs,
including those run as a written variant of pick (rows before the E-019 review missed them).
"""

import argparse
import json
from pathlib import Path
from statistics import fmean

from birdbrain.evaluation import paired, report


def rows(path: str) -> list[dict]:
    out = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    for r in out:
        r.setdefault("episode", r["room_seed"] % 100)
    return out


def pick_decisions(events: Path) -> tuple[int, int]:
    """Pick decisions and those that did not end done, from a run's events: each OUTCOME
    paired with its DECISION, whose `variant_of` names the skill a written one replaced."""
    decided: dict[float, str] = {}
    n = failed = 0
    for line in events.read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        if e["type"] == "DECISION":
            decided[e["payload"]["t0"]] = e["payload"].get("variant_of") or e["payload"]["skill"]
        elif e["type"] == "OUTCOME" and decided.get(e["payload"]["t0"]) == "pick":
            n += 1
            failed += e["payload"]["status"] != "done"
    return n, failed


def situation(authoring: Path, control: Path, kept_only: bool = False) -> None:
    """For each situation a skill was written for: success there (expected effect held
    and no fall) after the room it was written in, in the authoring life (whichever skill
    ran) against the control life (same rooms, the original skill), paired by life."""
    diffs, falls = [], []
    #: Per life, every outcome in any of its situations, each counted once (situations of one
    #: life overlap, and a condition can be asked about twice): the independent unit.
    life_success, life_falls = [], []
    by_parent: dict[tuple[str, str, str], list[float]] = {}           # first trial per life and condition
    print("\n" + ("kept skills only, in their situation after they were kept" if kept_only else
                  "in each written skill's situation, after it was written") + ", authoring life against control life:")

    def selected(outcomes: list, t: dict) -> list[int]:
        return [i for i, o in enumerate(outcomes)
                if o.get("episode") is not None
                and o["episode"] > ((t.get("decided") or 0) if kept_only else (t.get("opened") or 0))
                and o["features"].get(t["feature"]) == t["value"]
                and (o["skill"] == t["parent"] or o.get("variant_of") == t["parent"])]

    def rate(outcomes: list, sel: list[int]) -> tuple[float, float, int]:
        rows_ = [outcomes[i] for i in sel]
        return (sum(o["held"] and not o["fell"] for o in rows_) / len(rows_) if rows_ else float("nan"),
                sum(o["fell"] for o in rows_) / len(rows_) if rows_ else float("nan"), len(rows_))

    for life in sorted(authoring.glob("life-*")):
        raw = json.loads((life / "authored.json").read_text(encoding="utf-8"))
        mine = json.loads((life / "outcomes.json").read_text(encoding="utf-8"))
        theirs = json.loads((control / life.name / "outcomes.json").read_text(encoding="utf-8"))
        union_a, union_c, seen = set(), set(), set()
        for t in raw["trials"]:
            if kept_only and t["status"] != "kept":
                continue
            sa, sc = selected(mine, t), selected(theirs, t)
            (ra, fa, na), (rc, fc, nc) = rate(mine, sa), rate(theirs, sc)
            print(f"  {life.name} {t['parent']} when {t['feature']} {t['value']}: authoring {ra:.0%} of {na}, "
                  f"control {rc:.0%} of {nc}")
            if na and nc:
                diffs.append(ra - rc)
                falls.append(fa - fc)
                union_a |= set(sa)
                union_c |= set(sc)
                key = (t["parent"], t["feature"], t["value"])
                if key not in seen:
                    seen.add(key)
                    by_parent.setdefault(key, []).append(ra - rc)
        if union_a and union_c:
            (ra, fa, _), (rc, fc, _) = rate(mine, sorted(union_a)), rate(theirs, sorted(union_c))
            life_success.append(ra - rc)
            life_falls.append(fa - fc)
    from birdbrain.evaluation import sign_flip_p, t975
    for label, d, unit in (("success", diffs, "situations"), ("fall rate", falls, "situations"),
                           ("success per life (outcomes pooled, each once)", life_success, "lives"),
                           ("fall rate per life", life_falls, "lives"),
                           *((f"success, {p} when {f} {v} (first request per life)", d, "lives")
                             for (p, f, v), d in sorted(by_parent.items()) if len(d) > 2)):
        if len(d) > 1:
            m = fmean(d)
            sd = (sum((x - m) ** 2 for x in d) / (len(d) - 1)) ** 0.5
            half = t975(len(d) - 1) * sd / len(d) ** 0.5
            print(f"  {label}, authoring minus control: {m:+.3f} [95% CI {m - half:+.3f}, {m + half:+.3f}], "
                  f"{sum(x > 0 for x in d)} of {len(d)} {unit} higher, sign-flip p = {sign_flip_p(d):.3f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("control")
    ap.add_argument("authoring")
    ap.add_argument("--lives", required=True, help="memory root of the authoring arm")
    ap.add_argument("--control-lives", default=None, help="memory root of the control arm (same lives and rooms)")
    ap.add_argument("--late", type=int, default=6)
    ap.add_argument("--runs", default=None,
                    help="event logs (data/runs): recount pick decisions from them, including those run as a "
                         "written variant of pick (rows written before the E-019 review missed those)")
    args = ap.parse_args()
    live = {"written": [0.0, 0.0, 0.0], "parent": [0.0, 0.0, 0.0]}
    kept = {"written": [0.0, 0.0, 0.0], "parent": [0.0, 0.0, 0.0]}
    statuses: dict[str, int] = {}
    requests = written = tokens = lives_with_kept = 0
    life_diffs = []
    for life in sorted(Path(args.lives).glob("life-*")):
        raw = json.loads((life / "authored.json").read_text(encoding="utf-8"))
        requests += len(raw["log"])
        written += sum(e["status"] == "trial" for e in raw["log"])
        tokens += raw["tokens"]
        lives_with_kept += any(t["status"] == "kept" for t in raw["trials"])
        for e in raw["log"]:
            if e["status"] != "trial":
                print(f"{life.name}: request for {e['skill']} when {e['condition']} -> {e['status']} {e.get('problem', '')}")
        w_life, p_life = [0.0, 0.0], [0.0, 0.0]
        for t in raw["trials"]:
            statuses[t["status"]] = statuses.get(t["status"], 0) + 1
            # E-019 kept a parent prior in `counts` and the trial's own outcomes in `live`;
            # from E-020 on, `counts` holds only the trial's outcomes.
            live_counts = t.get("live", t["counts"])
            lw, lp = live_counts.get(t["child"], [0, 0, 0]), live_counts.get(t["parent"], [0, 0, 0])
            print(f"{life.name}: {t['child']} for {t['parent']} when {t['feature']} {t['value']} "
                  f"(after room {t.get('opened')}) -> {t['status']}; during the trial: written {lw}, parent {lp} "
                  f"[successes, trials, falls]")
            for arm, c in (("written", lw), ("parent", lp)):
                live[arm] = [x + y for x, y in zip(live[arm], c, strict=True)]
                if t["status"] == "kept":
                    kept[arm] = [x + y for x, y in zip(kept[arm], c, strict=True)]
            w_life = [w_life[0] + lw[0], w_life[1] + lw[1]]
            p_life = [p_life[0] + lp[0], p_life[1] + lp[1]]
        if w_life[1] and p_life[1]:
            life_diffs.append(w_life[0] / w_life[1] - p_life[0] / p_life[1])
    n_lives = len(list(Path(args.lives).glob("life-*")))
    print(f"\nrequests {requests}, skills written {written}, trials by status {statuses}, "
          f"lives with a kept skill {lives_with_kept} of {n_lives}, authoring tokens {tokens}")
    for label, table in (("all trials", live), ("kept skills", kept)):
        for arm, (s, n, f) in table.items():
            if n:
                print(f"  {label}, {arm:<7}: {s:g} of {n:g} succeeded ({s / n:.0%}), {f:g} falls ({f / n:.1%})")
    if life_diffs:
        m = fmean(life_diffs)
        sd = (sum((d - m) ** 2 for d in life_diffs) / max(len(life_diffs) - 1, 1)) ** 0.5
        from birdbrain.evaluation import t975
        half = t975(len(life_diffs) - 1) * sd / len(life_diffs) ** 0.5 if len(life_diffs) > 1 else float("nan")
        print(f"  success, written minus parent during trials, per life: {m:+.3f} [95% CI {m - half:+.3f}, "
              f"{m + half:+.3f}], n = {len(life_diffs)} lives, higher in {sum(d > 0 for d in life_diffs)}")
    if args.control_lives:
        situation(Path(args.lives), Path(args.control_lives))
        situation(Path(args.lives), Path(args.control_lives), kept_only=True)
    a, b = rows(args.control), rows(args.authoring)
    if args.runs:
        for r in a + b:
            r["pickDecisions"], r["pickDecisionsFailed"] = pick_decisions(Path(args.runs) / r["run_id"] / "events.jsonl")

    def per_life(rs: list[dict], metric: str) -> dict:
        return {s: {"seed": s, metric: fmean(r[metric] for r in rs if r["seed"] == s and r["episode"] >= args.late)}
                for s in sorted({r["seed"] for r in rs})}

    print(f"\nrooms {args.late} on, authoring minus control, paired by life:")
    for metric in ("inBasket", "falls", "pickDecisions", "pickDecisionsFailed"):
        print("  " + report(paired(per_life(a, metric), per_life(b, metric), metric)))


if __name__ == "__main__":
    main()
