"""Record one replay per milestone for the dashboard, each titled by what it shows.

    .venv/bin/python scripts/showcase.py [--bedrock] [--only M3b]

Replays go to data/replays with head-camera images. Runs that start from a learned
life use a copy of its memory, so the original is not changed.
"""

import argparse
import shutil
import tempfile
from pathlib import Path

from birdbrain.run import run_one

LEARNED = Path("data/lifetimes")
SHOWCASE = [
    # (key, title, run_one options, memory to start from)
    ("M1", "Milestone 1 · task: tidy the room · local policy", {}, None),
    ("M2", "Milestone 2 · task: tidy the room · cloud brain (Bedrock)", {"provider": "bedrock"}, None),
    ("M3", "Milestone 3 · no task, needs only · messy room", {"needs": True}, None),
    ("M3-tidy", "Milestone 3 · no task, needs only · tidy room: rests and explores", {"needs": True, "room": "tidy"}, None),
    ("M3b-basket", "Milestone 3b · owner likes toys in the basket · after 10 rooms of learning",
     {"owner": "basket"}, "e017r2-counts-basket/life-112"),
    ("M3b-wall", "Milestone 3b · owner likes toys by the walls · after 10 rooms of learning",
     {"owner": "wall"}, "e017r2-counts-wall/life-112"),
    ("M3b-leave", "Milestone 3b · owner likes toys left alone · after 10 rooms of learning",
     {"owner": "leave"}, "e017r2-counts-leave/life-112"),
    ("M3b-none", "Milestone 3b · control: no owner · after 10 rooms", {"owner": "none"}, "e017r2-counts-none/life-112"),
    ("M5", "Milestone 5 · task, with skills the cloud brain wrote (w_…) · after 20 rooms",
     {}, "e019-auth/life-150"),
    ("W2", "World 2 · task · a fresh duck that knows nothing of the objects",
     {"world": "world2", "kinds": "all"}, None),
    ("W2-learned", "World 2 · task · after 20 rooms of learning which objects fail (E-025)",
     {"world": "world2", "kinds": "all"}, "e025-new-task/life-300"),
    ("W2-hers", "World 2 · owner who wants her blue things left alone · after 20 rooms (E-025)",
     {"world": "world2", "kinds": "all", "owner": "hers"}, "e025-new-hers/life-300"),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bedrock", action="store_true", help="also record the cloud-brain run (M2)")
    ap.add_argument("--only", default=None)
    ap.add_argument("--seed", type=int, default=3)
    args = ap.parse_args()
    scratch = Path(tempfile.mkdtemp(prefix="showcase-"))
    for key, title, options, learned in SHOWCASE:
        if (args.only and key != args.only) or (options.get("provider") == "bedrock" and not args.bedrock):
            continue
        memory = None
        if learned is not None:
            memory = scratch / key
            shutil.copytree(LEARNED / learned, memory)
        row = run_one(args.seed, tag=f"showcase-{key}", title=title, camera=True, runs_dir=Path("data/replays"),
                      memory_dir=memory, **options)
        print(f"{key}: {row['inBasket']}/{row['toys']} in basket · {title}", flush=True)
    shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    main()
