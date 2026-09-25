#!/usr/bin/env python3
"""Seed-Skript (Organisation): erzeugt eine fiktive SAP-CSV-Exportdatei fuer
das Portal, passend zum Format in CLAUDE.md ("SAP-Schnittstelle").

Erzeugt gemaess CLAUDE.md ("Qualitaet" -> "Seed-Skript"):
- 1.900 fiktive Personen
- 8 Fachbereiche
- 5-6 Hierarchieebenen
- ca. 5% Teams mit < 3 Personen (fuer die Einladungsschwelle relevant)
- ca. 30% ohne E-Mail (fuer Personalnummer+Code-Anmeldung / Kiosk-Modus)

Die historischen Runden mit simulierten Antworten (fuer Trend/Benchmark)
werden ergaenzt, sobald die Runden-/Umfrage-Datenmodelle existieren
(Phase 3-5) -- siehe docs/ENTSCHEIDUNGEN.md.

Nur fiktive Daten (Namen, E-Mails, Personalnummern frei erfunden).

Verwendung:
    python seed/generate_org_csv.py [--seed 42] [--out seed/output/org.csv]
Danach ueber die Admin-UI ("Benutzerverwaltung & Organisation" -> "SAP-Import")
oder POST /organisation/import/apply importieren.
"""

from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass
from pathlib import Path

FACHBEREICHE = [
    "Vertrieb",
    "Produktion",
    "IT",
    "Personal",
    "Finanzen",
    "Logistik",
    "Marketing",
    "Kundenservice",
]

STANDORTE = ["Berlin", "Hamburg", "München", "Köln", "Stuttgart", "Leipzig"]

VORNAMEN = [
    "Anna", "Ben", "Clara", "David", "Emma", "Felix", "Greta", "Hannes",
    "Ida", "Jonas", "Klara", "Leon", "Mia", "Noah", "Olivia", "Paul",
    "Quirin", "Rosa", "Sofia", "Tom", "Uma", "Vincent", "Wanda", "Xenia",
    "Yusuf", "Zoe", "Aaron", "Bettina", "Christoph", "Diana",
]
NACHNAMEN = [
    "Müller", "Schmidt", "Schneider", "Fischer", "Weber", "Meyer", "Wagner",
    "Becker", "Schulz", "Hoffmann", "Koch", "Bauer", "Richter", "Klein",
    "Wolf", "Schröder", "Neumann", "Schwarz", "Zimmermann", "Braun",
    "Krüger", "Hofmann", "Hartmann", "Lange", "Schmitt", "Werner",
]


@dataclass
class SeedPerson:
    personalnummer: str
    vorname: str
    nachname: str
    email: str | None
    org_einheit: str
    fachbereich: str
    manager_personalnummer: str | None
    standort: str
    aktiv: bool = True


def _build_fachbereich_tree(
    fachbereich: str, count: int, rng: random.Random, next_id: "IdCounter", max_level: int
) -> list[SeedPerson]:
    """Baut eine Hierarchie mit `count` Personen und `max_level` Ebenen fuer
    einen Fachbereich.

    Level-Groessen werden vorab geometrisch geplant (Level 1 = Fachbereichsleitung
    mit 1 Person, jede weitere Ebene waechst um denselben Faktor), damit die
    Teamgroessen ueber alle Ebenen hinweg gleichmaessig um die Zielgroesse
    (CLAUDE.md-Schwelle >= 3) liegen. Auf der letzten (groessten) Ebene bekommen
    gezielt ein paar Team-Leitungen nur 1-2 Unterstellte, damit ein kleiner,
    realistischer Anteil an Teams unter der Einladungsschwelle bleibt.
    """
    ratio = _solve_growth_ratio(count, max_level)
    level_sizes = [max(1, round(ratio**i)) for i in range(max_level)]
    level_sizes[0] = 1  # Fachbereichsleitung ist immer genau 1 Person
    # Rundungsdifferenz auf die groesste (letzte) Ebene ausgleichen, damit die
    # Summe exakt `count` ergibt, ohne das Wachstumsverhaeltnis zu verzerren.
    level_sizes[-1] += count - sum(level_sizes)

    people: list[SeedPerson] = []
    leader_id = next_id.next()
    people.append(_random_person(leader_id, None, fachbereich, fachbereich, rng))

    # Level-2-Ankerpunkt bestimmt die org_einheit-Gruppierung ("Team <Ankerperson>")
    current_level: list[tuple[str, str]] = [(leader_id, leader_id)]  # (personalnummer, level2_anchor)

    for lvl_idx in range(1, max_level):  # erzeugt Ebene lvl_idx + 1
        size_this_level = level_sizes[lvl_idx]
        parents = current_level
        is_last_transition = lvl_idx == max_level - 1

        counts = [0] * len(parents)
        small_indices: set[int] = set()
        if is_last_transition and len(parents) > 1:
            n_small = max(1, round(len(parents) * 0.02))
            small_indices = set(rng.sample(range(len(parents)), min(n_small, len(parents) - 1)))
            for i in small_indices:
                counts[i] = rng.choice([1, 2])

        remaining_for_level = size_this_level - sum(counts)
        normal_indices = [i for i in range(len(parents)) if i not in small_indices]
        pool = normal_indices or list(range(len(parents)))
        if remaining_for_level > 0:
            base, extra = divmod(remaining_for_level, len(pool))
            for j, i in enumerate(pool):
                counts[i] += base + (1 if j < extra else 0)

        next_level: list[tuple[str, str]] = []
        for (parent_id, level2_anchor), n_children in zip(parents, counts, strict=True):
            for _ in range(n_children):
                child_id = next_id.next()
                child_anchor = child_id if lvl_idx == 1 else level2_anchor
                org_einheit = fachbereich if lvl_idx == 1 else f"{fachbereich} – Team {child_anchor}"
                people.append(_random_person(child_id, parent_id, fachbereich, org_einheit, rng))
                next_level.append((child_id, child_anchor))
        current_level = next_level

    return people


def _solve_growth_ratio(count: int, n_levels: int) -> float:
    """Loest r in der geometrischen Reihe 1 + r + r^2 + ... + r^(n-1) = count
    per Bisektion (kein geschlossener Ausdruck fuer beliebiges n)."""
    if n_levels <= 1:
        return 1.0
    lo, hi = 1.0001, float(count)
    for _ in range(100):
        mid = (lo + hi) / 2
        total = (mid**n_levels - 1) / (mid - 1)
        if total < count:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


class IdCounter:
    def __init__(self) -> None:
        self._n = 0

    def next(self) -> str:
        self._n += 1
        return f"P{self._n:05d}"


def _random_person(pnr: str, manager: str | None, fachbereich: str, org_einheit: str, rng: random.Random) -> SeedPerson:
    return SeedPerson(
        personalnummer=pnr,
        vorname=rng.choice(VORNAMEN),
        nachname=rng.choice(NACHNAMEN),
        email=None,  # wird nach Aufbau der vollstaendigen Struktur vergeben (siehe assign_emails)
        org_einheit=org_einheit,
        fachbereich=fachbereich,
        manager_personalnummer=manager,
        standort=rng.choice(STANDORTE),
    )


def _assign_emails(people: list[SeedPerson], rng: random.Random, target_no_email_ratio: float = 0.30) -> None:
    """~30% ohne E-Mail (CLAUDE.md). Wer Unterstellte hat, bekommt immer eine
    E-Mail (muss Reports erhalten koennen); die Quote wird daher unter den
    Team-Mitgliedern ohne eigene Unterstellte so skaliert, dass sie
    unternehmensweit ca. 30% ergibt."""
    managers = {p.manager_personalnummer for p in people if p.manager_personalnummer}
    leaves = [p for p in people if p.personalnummer not in managers]

    target_total_no_email = int(len(people) * target_no_email_ratio)
    ratio_among_leaves = min(1.0, target_total_no_email / max(1, len(leaves)))

    for p in people:
        is_leaf = p.personalnummer not in managers
        gets_no_email = is_leaf and rng.random() < ratio_among_leaves
        p.email = None if gets_no_email else _make_email(p)


def _make_email(p: SeedPerson) -> str:
    return f"{p.vorname.lower()}.{p.nachname.lower()}.{p.personalnummer.lower()}@example.test"


def generate(total: int, rng: random.Random) -> list[SeedPerson]:
    base_size = total // len(FACHBEREICHE)
    remainder = total % len(FACHBEREICHE)
    sizes = [base_size + (1 if i < remainder else 0) for i in range(len(FACHBEREICHE))]

    # Ein Wachstumsfaktor, der eine 6-stufige Hierarchie bei ~240 Personen pro
    # Fachbereich exakt trifft, liegt sehr nah an 3 -- zu nah an der
    # Einladungsschwelle, um "ca. 5%" kleine Teams von "meistens zu klein" zu
    # unterscheiden. Daher bekommen nur 2 der 8 Fachbereiche 6 Ebenen (fuer die
    # geforderte Bandbreite "5-6 Hierarchieebenen"), die uebrigen 5 Ebenen mit
    # spuerbar groesserem, sichererem Wachstumsfaktor (~3.9).
    level_counts = [6, 6] + [5] * (len(FACHBEREICHE) - 2)
    rng.shuffle(level_counts)

    next_id = IdCounter()
    all_people: list[SeedPerson] = []
    for fachbereich, size, max_level in zip(FACHBEREICHE, sizes, level_counts, strict=True):
        all_people.extend(_build_fachbereich_tree(fachbereich, size, rng, next_id, max_level))

    _assign_emails(all_people, rng)
    return all_people


def write_csv(people: list[SeedPerson], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(
            [
                "personalnummer", "vorname", "nachname", "email", "org_einheit",
                "fachbereich", "manager_personalnummer", "standort", "aktiv",
            ]
        )
        for p in people:
            writer.writerow(
                [
                    p.personalnummer, p.vorname, p.nachname, p.email or "",
                    p.org_einheit, p.fachbereich, p.manager_personalnummer or "",
                    p.standort, "1" if p.aktiv else "0",
                ]
            )


def print_stats(people: list[SeedPerson]) -> None:
    managers = {p.manager_personalnummer for p in people if p.manager_personalnummer}
    team_sizes: dict[str, int] = {}
    for p in people:
        if p.manager_personalnummer:
            team_sizes[p.manager_personalnummer] = team_sizes.get(p.manager_personalnummer, 0) + 1

    small_teams = sum(1 for size in team_sizes.values() if size < 3)
    no_email = sum(1 for p in people if p.email is None)

    def depth(pnr: str, by_pnr: dict[str, SeedPerson], cache: dict[str, int]) -> int:
        if pnr in cache:
            return cache[pnr]
        person = by_pnr[pnr]
        d = 1 if not person.manager_personalnummer else 1 + depth(person.manager_personalnummer, by_pnr, cache)
        cache[pnr] = d
        return d

    by_pnr = {p.personalnummer: p for p in people}
    cache: dict[str, int] = {}
    max_depth = max(depth(p.personalnummer, by_pnr, cache) for p in people)

    print(f"Personen gesamt:      {len(people)}")
    print(f"Fachbereiche:         {len(FACHBEREICHE)}")
    print(f"Max. Hierarchietiefe: {max_depth}")
    print(f"Teams (mit >=1 MA):   {len(team_sizes)}")
    print(f"  davon < 3 Personen: {small_teams} ({small_teams / max(1, len(team_sizes)):.1%})")
    print(f"Ohne E-Mail:          {no_email} ({no_email / len(people):.1%})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42, help="Zufalls-Seed fuer Reproduzierbarkeit")
    parser.add_argument("--total", type=int, default=1900, help="Anzahl Personen")
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "output" / "org.csv")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    people = generate(args.total, rng)
    write_csv(people, args.out)
    print(f"Geschrieben: {args.out}\n")
    print_stats(people)


if __name__ == "__main__":
    main()
