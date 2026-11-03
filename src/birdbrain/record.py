"""Record a BirdBrain playroom run with Microduck Lab's recorder (video, contact sheet, events).

    birdbrain-record playroom --brain d0=birdbrain --seconds 120 --seed 1 --out /tmp/bb-rec

Registers the `birdbrain` brain kind, then hands the command line to the
lab's `record-world`. Set BIRDBRAIN_PROVIDER=bedrock for the cloud brain.
"""

from birdbrain.lab import register


def main() -> None:
    register()
    from microduck_local.record_world import main as record_world
    record_world()


if __name__ == "__main__":
    main()
