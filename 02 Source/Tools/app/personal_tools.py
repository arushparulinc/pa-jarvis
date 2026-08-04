import random
from pathlib import Path


ARUSH_FACTS_FILE = Path(__file__).with_name("arush_random_facts.txt")


def arush_random_facts() -> str:
    """Return one randomly selected fact about Arush."""
    facts = [
        line.strip()
        for line in ARUSH_FACTS_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not facts:
        raise RuntimeError("No Arush facts are configured.")

    return random.choice(facts)
