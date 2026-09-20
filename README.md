# 🚀 Coding-Wettbewerb-Plattform

Eine Flask-basierte Webanwendung für Coding-Challenges, Hackathons und Programmier-Wettbewerbe an Schulen — läuft komplett lokal im eigenen Netzwerk, **ganz ohne Internetzugriff**.

![Status](https://img.shields.io/badge/Status-Active-success)
![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
[![Tests](https://github.com/Obi-Wahn/challenge_plattform/actions/workflows/tests.yml/badge.svg)](https://github.com/Obi-Wahn/challenge_plattform/actions/workflows/tests.yml)
![Flask](https://img.shields.io/badge/Flask-3.x-green.svg)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5-purple.svg)

## 📸 So sieht es aus

| Steuerzentrale (Lehrkraft) | Teamansicht (Schülerinnen und Schüler) |
| --- | --- |
| ![Steuerzentrale](docs/bilder/steuerzentrale.png) | ![Teamansicht](docs/bilder/teamansicht.png) |

| Rangliste | Urkunde |
| --- | --- |
| ![Rangliste](docs/bilder/rangliste.png) | ![Urkunde](docs/bilder/urkunde.png) |

## 🌟 Features

### Für Teilnehmer
*   **Team-Registrierung & Login**: Sichere Anmeldung mit Teamnamen und Passwort.
*   **Wettbewerbsseite**: alle Aufgaben des laufenden Wettbewerbs mit Fortschrittsanzeige,
    eigenen Punkten und dem Feedback der Lehrkraft.
*   **Datei-Uploads je nach Aufgabe**: Processing (`.pde`), Scratch (`.sb`/`.sb3`), Python (`.py`), Java (`.java`), MakeCode/Calliope (`.hex`/`.mkcd`).
*   **Hinweise pro Aufgabe**: Admins können während des Events optionale Tipps freischalten, falls ein Team nicht weiterkommt.
*   **Rangliste**: Punkte pro Aufgabe und Gesamtstand, lädt sich alle 30 Sekunden selbst neu –
    so kann sie während des Wettbewerbs am Beamer stehen bleiben.
*   **Countdown-Seite**: zeigt, wann es losgeht oder wie viel Zeit noch bleibt –
    ebenfalls zum Projizieren gedacht.
*   **Siegerehrung**: Podium der besten drei, das sich Platz für Platz aufdecken lässt
    (Leertaste oder Knopf) – für den Abschluss vor der Klasse.
*   **Korrektur nach Freigabe**: Gibt die Lehrkraft eine Abgabe frei, darf das Team sie
    genau einmal ersetzen.
*   **Eigene Urkunde als PDF**: Sobald der Wettbewerb beendet ist, kann jedes Team seine
    Urkunde selbst herunterladen.
*   **QR-Code auf der Startseite**: zum schnellen Beitreten per Smartphone, z. B. wenn die Seite beamt wird.
*   **Responsive Design**: für Desktop, Tablet und Smartphone optimiert.

### Für Administratoren
*   **Steuerzentrale**: zeigt den aktuellen Wettbewerb mit Zustand, Teams, Aufgaben und
    offenen Bewertungen; die Kacheln sind nach Vorbereitung, Während des Wettbewerbs
    und Zum Abschluss sortiert.
*   **Wettbewerbs-Seite**: alles zu einem Wettbewerb an einem Ort – Aufgaben, Teams,
    Bewertungen, Countdown, Rangliste, Siegerehrung und Urkunden.
*   **Wettbewerb beenden**: ein Knopf sperrt die Abgaben und macht den Weg frei für
    Rangliste, Siegerehrung und Urkunden. „Wieder öffnen“ macht das rückgängig.
*   **Wettbewerbs-Verwaltung**: Erstellen, Aktivieren, Pausieren und Beenden.
*   **Teams gehören zu ihrem Wettbewerb**: derselbe Teamname darf in mehreren Wettbewerben
    vorkommen; beim Anlegen eines neuen Wettbewerbs lassen sich die alten Teams übernehmen.
*   **Aufgaben-Konfiguration**:
    *   Erstellen von Aufgaben mit detaillierten Beschreibungen.
    *   **Markdown Support**: Aufgabenbeschreibungen werden mit Markdown formatiert.
    *   **Dateiformat-Wahl**: Festlegen des erlaubten Dateityps pro Aufgabe.
    *   Optionale Hinweise, die während des Events sichtbar/unsichtbar geschaltet werden können.
    *   **Sichern und Wiederverwenden**: Aufgaben lassen sich als JSON-Datei herunterladen –
        einzeln oder alle zusammen – und in einen anderen Wettbewerb einlesen. Die Datei enthält nur die Aufgaben –
        keine Abgaben und keine Punkte – und lässt sich in jedem Texteditor bearbeiten
        oder an Kolleginnen und Kollegen weitergeben.
*   **Review-System**:
    *   Anzeige eingereichter Lösungen inklusive **Aufgabenbeschreibung**.
    *   **In-Browser Code Preview**: Code direkt im Browser lesen.
    *   Download-Option für lokale Tests.
    *   Bewertung mit Punkten (automatisch auf 0–Max. begrenzt) und Feedback.
    *   **Korrektur freigeben**: Eine Abgabe für das Team wieder öffnen; es darf dann genau
        einmal neu hochladen. Die bisherige Bewertung wird dabei zurückgesetzt, die Abgabe
        landet wieder in der Warteschlange.
    *   **Abgabe löschen**: Möglichkeit, fehlerhafte Abgaben komplett zu entfernen, damit Teams neu einreichen können.
*   **Team-Verwaltung**: Übersicht der Teams des aktuellen Wettbewerbs, inklusive
    Passwort-Reset, falls ein Team sein Passwort vergisst.
*   **Urkunden**: Druckansicht und PDF für alle Teams, dazu eine Urkunde einzeln.
    Unter die Unterschriftslinie lässt sich ein Name eintragen – wahlweise in einer
    von drei Handschriften (Caveat, Dancing Script, Great Vibes) oder in Druckschrift.
    Ohne Eintrag steht dort wie bisher „Unterschrift“ zum Unterschreiben von Hand.
*   **Einstellungen**: Name und Beschreibung der Veranstaltung frei anpassbar, ohne Code zu ändern.

## 🛠 Technologien

*   **Backend**: Python, Flask, SQLAlchemy (SQLite), waitress (Produktiv-WSGI-Server).
*   **Frontend**: HTML5, CSS3, Bootstrap 5, Markdown-Editor (EasyMDE) — alle Assets liegen lokal im Repo (`static/vendor/`), keine CDN-Abhängigkeit, funktioniert komplett offline.
*   **PDF**: fpdf2 für die Urkunden. Die Handschriften unter `static/vendor/fonts/` stehen
    unter der SIL Open Font License (Lizenztexte liegen daneben) und sind mit im Repo,
    damit die Urkunden auch ohne Internet entstehen.
*   **Sicherheit**:
    *   Passwort-Hashing (Werkzeug Security).
    *   CSRF Protection (Flask-WTF).
    *   Rate-Limiting auf Login-Routen (Flask-Limiter).
    *   Secure Filename Handling.
    *   Kein Debug-Modus im Normalbetrieb (nur über `FLASK_DEBUG=true` für lokale Entwicklung).
*   **Architektur**: Modularer Aufbau mit Flask Blueprints und Application Factory Pattern.

## 🚀 Installation & Setup

Voraussetzung: Python 3.10 oder höher (fpdf2, das die Urkunden erzeugt, verlangt diese Version).

1.  **Repository klonen**
    ```bash
    git clone https://github.com/Obi-Wahn/challenge_plattform.git
    cd challenge_plattform
    ```

2.  **Virtuelle Umgebung erstellen und aktivieren**
    ```bash
    python -m venv venv
    
    # Mac/Linux:
    source venv/bin/activate
    
    # Windows:
    venv\Scripts\activate
    ```

3.  **Abhängigkeiten installieren**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Konfiguration**
    Erstelle eine `.env` Datei im Hauptverzeichnis (siehe `.env.example`):
    ```ini
    SECRET_KEY=dein-geheimer-schluessel
    ADMIN_PASSWORD=dein-sicheres-passwort
    FLASK_DEBUG=false
    ```
    `SECRET_KEY` und `ADMIN_PASSWORD` sind Pflicht — ohne echte Werte startet die Anwendung nicht. `FLASK_DEBUG` sollte in einem Netzwerk mit mehreren Nutzern (z. B. der Schul-LAN) immer auf `false` bleiben; der eingebaute Debugger erlaubt sonst beliebige Code-Ausführung auf dem Server.

5.  **Datenbank vorbereiten**
    Beim ersten Start wird die Datenbank automatisch erstellt. Neu hinzugekommene Spalten (z. B. für die Hinweise-Funktion) werden bei bestehenden Datenbanken beim Start ebenfalls automatisch ergänzt, ohne Datenverlust.

6.  **Anwendung starten**
    ```bash
    python app.py
    ```
    Die Konsole zeigt beim Start die genaue Adresse an, unter der die Anwendung erreichbar ist — sowohl lokal (`http://localhost:8000`) als auch die Netzwerk-Adresse für andere Geräte im selben Netz.

## 📖 Nutzung

1.  **Admin-Zugang**:
    *   Rufe `/admin` auf (Link auch im Footer der Seite).
    *   Login mit dem in der `.env` definierten Passwort (`ADMIN_PASSWORD`).
    *   Passe unter **Einstellungen** bei Bedarf Name und Beschreibung der Veranstaltung an.
    *   Lege einen neuen Wettbewerb an.
    *   Füge Aufgaben hinzu, wähle Punkte, erlaubtes Dateiformat und optional einen Hinweis.
    *   Aktiviere den Wettbewerb.

    *   **Schnellstart:** Unter `beispiele/` liegen fertige Aufgabensätze für
        Scratch und Calliope. Auf der Aufgaben-Seite mit **⬆️ Datei einlesen**
        laden – dann steht ein kompletter Wettbewerb, den man nach Belieben
        anpassen kann.

2.  **Teilnehmer**:
    *   Registrieren sich auf der Startseite (oder scannen den dort angezeigten QR-Code).
    *   Werden direkt zum aktiven Wettbewerb weitergeleitet.
    *   Können Lösungen im geforderten Format hochladen.

## 🔄 Frontend-Bibliotheken aktualisieren

Bootstrap, EasyMDE, Font Awesome und die Handschriften liegen als Dateien
unter `static/vendor/` im Repo – nur so funktioniert die Anwendung ohne
Internet. Der Preis dafür: Sie aktualisieren sich nicht von selbst. Welche
Fassungen dort liegen, steht in `static/vendor/versionen.json`.

Nachsehen, ob es neuere gibt (ändert nichts):

```bash
python werkzeuge/vendor_aktualisieren.py --pruefen
```

```
Bootstrap               5.3.8      aktuell
EasyMDE                2.21.0      aktuell
Font Awesome Free       6.7.2  ->  7.3.1     (neue Hauptversion - Darstellung vorher prüfen)
Caveat                  0.4.2      aktuell
```

Eine neue Fassung übernehmen:

```bash
python werkzeuge/vendor_aktualisieren.py --setzen bootstrap=5.3.8
pytest
python app.py     # und die Seiten einmal ansehen
```

Das Skript holt die Dateien aus der npm-Registry, prüft die Prüfsumme und
ersetzt nur das, was sich geändert hat. Es braucht Internet – also am
heimischen Rechner ausführen, nicht während eines Wettbewerbs. Bei einer
**neuen Hauptversion** (der ersten Zahl) lohnt der Blick in die Oberfläche
besonders: Dort ändern sich schon mal Klassennamen oder Symbole.

## 💾 Datenbank und Sicherungen

Alle Daten liegen in `data/challenge.db`. Diese Datei ist der Wettbewerb –
Teams, Aufgaben, Abgaben und Punkte. Sie gehört **nicht** ins Repository und
wird von `.gitignore` ausgeschlossen.

Bringt eine neue Version der Anwendung eine Änderung an der Datenbankstruktur
mit, wird diese beim Start automatisch ergänzt. **Vor der ersten solchen
Änderung legt die Anwendung eine Kopie an**, zum Beispiel:

```
data/challenge-vor-teams-2026-09-20-1430.db
```

Beim Start steht dann eine Zeile wie „Datenbank vor der Änderung gesichert: …"
im Fenster. Die Kopie entsteht nur, wenn wirklich etwas geändert wird – bei
allen folgenden Starts passiert nichts mehr. Geht das Sichern schief (etwa
weil die Festplatte voll ist), bricht der Start ab, statt ungesichert
umzubauen.

**Wofür die Kopie gut ist:** Falls ein Umbau zwar durchläuft, aber nicht das
Gewünschte tut, kommt man damit an den Stand davor heran. Zum Rückgängigmachen
die aktuelle Datei zur Seite legen und die Kopie nach `data/challenge.db`
umbenennen. Alte Kopien kann man löschen, sobald klar ist, dass alles passt.

**Wofür sie nicht gut ist:** Sie ersetzt keine regelmäßige Sicherung. Sie liegt
im selben Ordner – geht die Festplatte kaputt oder wird das Verzeichnis
gelöscht, ist sie mit weg. Vor einem echten Wettbewerb lohnt es sich, `data/`
zusätzlich auf einen USB-Stick zu kopieren.

## ✅ Tests

Das Projekt bringt automatische Tests mit. Sie prüfen den ganzen Ablauf – vom
Anmelden eines Teams über Abgabe, Bewertung und Rangliste bis zu Urkunden,
Aufgaben-Export und den Datenbank-Änderungen beim Start. Nach jeder Änderung am
Code lohnt sich ein Durchlauf, besonders vor einem echten Wettbewerb.

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

Die Tests laufen gegen eine eigene Datenbank in einem temporären Verzeichnis.
`data/challenge.db` wird dabei nie angefasst – ein Testlauf kann also keine
echten Wettbewerbsdaten beschädigen.

Zusätzlich prüft `ruff` den Code auf echte Fehler – unbenutzte Importe,
unbekannte Namen, Tippfehler in Variablen. Stil und Formatierung bleiben
absichtlich ungeprüft:

```bash
ruff check .
```

Beides läuft auch automatisch: Bei jedem Push und jedem Pull Request führt
GitHub dieselben zwei Befehle aus, auf Python 3.10 und 3.13. Am Pull Request
steht dann ein grünes Häkchen oder ein rotes Kreuz – man muss also nicht
daran denken, selbst zu testen. Die Einstellungen dazu stehen in
`.github/workflows/tests.yml`.

Einzelne Bereiche lassen sich gezielt prüfen:

```bash
pytest tests/test_submissions.py       # nur die Abgaben
pytest -k "urkunde"                    # alles rund um Urkunden
pytest -v                              # mit Namen jedes einzelnen Tests
```

| Datei | prüft |
| --- | --- |
| `test_challenge_status.py` | geplant / läuft / pausiert / beendet, Countdown-Zeiten |
| `test_teams.py` | Registrierung, Anmeldung, Bindung ans Wettbewerb, Team-Verwaltung |
| `test_submissions.py` | Abgabe, Korrektur nach Freigabe, Bewertung |
| `test_scoring.py` | Rangliste und Podium, auch bei Gleichstand |
| `test_admin.py` | Steuerzentrale, Wettbewerbs-Seite, Beenden, Aktivieren |
| `test_certificates.py` | Urkunden-PDF, Unterschrift, Download durch die Teams |
| `test_task_exchange.py` | Aufgaben sichern und wiederverwenden |
| `test_migrations.py` | Datenbank aus einer älteren Version weiterbenutzen |
| `test_security.py` | CSRF, Passwörter, Uploads, Rate-Limit |
| `test_vendor.py` | Versionsliste und `static/vendor/` bleiben deckungsgleich |

## 📂 Projektstruktur

```
challenge_plattform/
├── app.py                # Einstiegspunkt
├── config.py              # Konfiguration
├── extensions.py          # Datenbank & Extensions
├── models.py               # Datenbankmodelle
├── scoring.py             # Rangliste und Podium
├── certificates.py        # Urkunden als PDF
├── task_exchange.py       # Aufgaben sichern und einlesen
├── requirements.txt       # Abhängigkeiten
├── requirements-dev.txt   # zusätzlich zum Testen
├── pytest.ini             # Test-Einstellungen
├── ruff.toml              # Einstellungen der Fehlerprüfung
├── .github/workflows/     # Tests laufen automatisch bei jedem Push
├── .env.example            # Vorlage für die eigene .env
├── blueprints/             # Modulare Routen
│   ├── admin.py
│   ├── auth.py
│   ├── challenge.py
│   └── public.py
├── static/
│   ├── vendor/              # Lokal eingebundene Frontend-Bibliotheken (Bootstrap, EasyMDE, Font Awesome)
│   │   ├── fonts/           # Handschriften für die Unterschrift auf den Urkunden (OFL)
│   │   └── versionen.json   # welche Fassungen hier liegen
│   └── ...                  # eigenes CSS, Bilder
├── templates/               # HTML Templates
├── tests/                   # automatische Tests (pytest)
├── beispiele/               # fertige Aufgabensätze zum Einlesen
├── werkzeuge/               # Hilfsskripte (Bibliotheken aktualisieren)
├── docs/bilder/             # Screenshots für diese README
├── uploads/                 # Hochgeladene Abgaben (wird erstellt)
└── data/                    # SQLite Datenbank und ihre Sicherungen (werden erstellt)
```

## 🙏 Herkunft & Mitwirkende

Dieses Projekt basiert auf der ursprünglichen Version von [frankjuchim](https://github.com/frankjuchim/challenge_plattform). Ein großer Teil der hier beschriebenen Weiterentwicklung (Sicherheits-Härtung, Offline-Fähigkeit, neue Funktionen, Übersetzungen) wurde mit Unterstützung von KI (Claude Code) umgesetzt.

## 📝 Lizenz

Dieses Projekt wurde für eine Weiterbildungsmaßnahme Informatik für Lehrkräfte erstellt.
