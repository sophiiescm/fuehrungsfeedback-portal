"""Lasttest: gleichzeitige Umfrage-Teilnahmen direkt gegen LimeSurvey
(Token-Link -> alle Gruppen beantworten -> Absenden).

Vorbereitung: laufende Runde + Token-Export (siehe docs/INSTALLATION.md):
  psql ... -A -F, -c "select rt.limesurvey_sid, p.limesurvey_token from participation p
                      join round_target rt on rt.id=p.round_target_id where p.status='offen'" > loadtest/tokens.csv
Start (300 gleichzeitige Nutzer, jeder Token nur einmal -> Einmal-Teilnahme):
  pip install locust
  locust -f loadtest/locustfile.py --headless -u 300 -r 30 -t 3m -H http://localhost:8080
Hinweis: verbraucht die Tokens (die Umfragen sind danach ausgefuellt).
"""

import csv
import queue
import re
from pathlib import Path

from locust import HttpUser, between, task

TOKENS: "queue.Queue[tuple[str, str]]" = queue.Queue()
for row in csv.reader(open(Path(__file__).with_name("tokens.csv"), encoding="utf-8")):
    if len(row) == 2:
        TOKENS.put((row[0], row[1]))

INPUT = re.compile(r"<input[^>]*>", re.I)
ATTR = re.compile(r'(\w[\w-]*)="([^"]*)"')


def parse_form(html: str) -> dict:
    """Baut den POST wie der Browser: Hidden-Felder (ohne JS-Spiegel), je Radio-Gruppe
    Wert 3, Freitext, sowie fieldnames/relevance*/lastgroup (von LimeSurvey verlangt)."""
    data, answers = {}, {}
    for tag in INPUT.findall(html):
        a = dict(ATTR.findall(tag))
        name, typ = a.get("name"), a.get("type", "text")
        if not name or name.startswith("java"):
            continue
        if typ == "hidden":
            data[name] = a.get("value", "")
        elif typ == "radio":
            answers[name] = "3"
    for name in re.findall(r'<textarea[^>]*name="([^"]+)"', html, re.I):
        answers[name] = "Lasttest-Antwort"
    if answers:
        data["fieldnames"] = "|".join(answers)
        for name in answers:
            data[f"relevance{name.rsplit('X', 1)[1]}"] = "1"
        data[f"relevanceG{max(0, int(data.get('thisstep', 1)) - 1)}"] = "1"
        data["lastgroup"] = next(iter(answers)).rsplit("X", 1)[0]
        data.update(answers)
    return data


class Participant(HttpUser):
    wait_time = between(0.5, 2)

    @task
    def participate(self):
        try:
            sid, token = TOKENS.get_nowait()
        except queue.Empty:
            self.environment.runner.quit()
            return
        self.client.cookies.clear()  # jede Person eine eigene Session
        r = self.client.get(f"/index.php/survey/index/sid/{sid}/token/{token}/lang/de", name="Umfrage oeffnen")
        for _ in range(12):  # Start + max. Gruppenseiten
            form = parse_form(r.text)
            if "completed-text" in r.text:
                return
            form["move"] = "movesubmit" if 'value="movesubmit"' in r.text else "movenext"
            r = self.client.post(f"/index.php/{sid}", data=form, name="Seite absenden")
            if r.status_code != 200:
                return
