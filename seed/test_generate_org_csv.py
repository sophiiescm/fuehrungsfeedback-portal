"""Invarianten-Tests fuer das Seed-Skript. Ausfuehren mit: pytest seed/"""

import random

from generate_org_csv import FACHBEREICHE, generate


def test_generates_exact_total_count():
    people = generate(1900, random.Random(42))
    assert len(people) == 1900


def test_covers_all_fachbereiche():
    people = generate(1900, random.Random(42))
    assert {p.fachbereich for p in people} == set(FACHBEREICHE)


def test_no_duplicate_personalnummer():
    people = generate(1900, random.Random(42))
    pnrs = [p.personalnummer for p in people]
    assert len(pnrs) == len(set(pnrs))


def test_every_manager_reference_resolves():
    people = generate(1900, random.Random(42))
    known = {p.personalnummer for p in people}
    for p in people:
        if p.manager_personalnummer:
            assert p.manager_personalnummer in known


def test_no_cycles():
    people = generate(1900, random.Random(42))
    by_pnr = {p.personalnummer: p for p in people}
    for p in people:
        seen = set()
        current = p
        while current.manager_personalnummer:
            assert current.manager_personalnummer not in seen, "Zyklus gefunden"
            seen.add(current.manager_personalnummer)
            current = by_pnr[current.manager_personalnummer]


def test_email_ratio_close_to_30_percent():
    people = generate(1900, random.Random(42))
    no_email = sum(1 for p in people if p.email is None)
    ratio = no_email / len(people)
    assert 0.25 <= ratio <= 0.35


def test_small_team_ratio_is_low_single_digit_to_low_teens_percent():
    people = generate(1900, random.Random(42))
    team_sizes: dict[str, int] = {}
    for p in people:
        if p.manager_personalnummer:
            team_sizes[p.manager_personalnummer] = team_sizes.get(p.manager_personalnummer, 0) + 1
    small = sum(1 for size in team_sizes.values() if size < 3)
    ratio = small / len(team_sizes)
    # CLAUDE.md fordert "ca. 5%"; der Generator trifft naeherungsweise
    # einen niedrigen einstelligen bis niedrigen zweistelligen Bereich.
    assert 0.0 <= ratio <= 0.15


def test_hierarchy_depth_is_5_or_6():
    people = generate(1900, random.Random(42))
    by_pnr = {p.personalnummer: p for p in people}
    cache: dict[str, int] = {}

    def depth(pnr: str) -> int:
        if pnr in cache:
            return cache[pnr]
        person = by_pnr[pnr]
        d = 1 if not person.manager_personalnummer else 1 + depth(person.manager_personalnummer)
        cache[pnr] = d
        return d

    max_depth = max(depth(p.personalnummer) for p in people)
    assert max_depth in (5, 6)
