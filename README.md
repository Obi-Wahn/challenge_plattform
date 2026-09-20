# 🚀 Coding-Wettbewerb-Plattform

Eine Flask-basierte Webanwendung für Coding-Challenges, Hackathons und Programmier-Wettbewerbe an Schulen — läuft komplett lokal im eigenen Netzwerk, **ganz ohne Internetzugriff**.

![Status](https://img.shields.io/badge/Status-Active-success)
![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
[![Tests](https://github.com/Obi-Wahn/challenge_plattform/actions/workflows/tests.yml/badge.svg)](https://github.com/Obi-Wahn/challenge_plattform/actions/workflows/tests.yml)
![Flask](https://img.shields.io/badge/Flask-3.x-green.svg)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5-purple.svg)

## 🌟 Features

### Für Teilnehmer
*   **Team-Registrierung & Login**: Sichere Anmeldung mit Teamnamen und Passwort.
*   **Dashboard**: Übersicht über aktive Challenges und Aufgaben mit Fortschrittsanzeige.
*   **Datei-Uploads je nach Aufgabe**: Processing (`.pde`), Scratch (`.sb`/`.sb3`), Python (`.py`), Java (`.java`), MakeCode/Calliope (`.hex`/`.mkcd`).
*   **Hinweise pro Aufgabe**: Admins können während des Events optionale Tipps freischalten, falls ein Team nicht weiterkommt.
*   **Live Scoreboard**: Echtzeit-Ranking mit Punkten pro Aufgabe und Gesamtpunktzahl.
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
*   **Challenge-Management**: Erstellen, Aktivieren, Pausieren und Beenden von Wettbewerben.
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
    *   Erstelle eine neue Challenge.
    *   Füge Aufgaben hinzu, wähle Punkte, erlaubtes Dateiformat und optional einen Hinweis.
    *   Aktiviere die Challenge.

2.  **Teilnehmer**:
    *   Registrieren sich auf der Startseite (oder scannen den dort angezeigten QR-Code).
    *   Werden direkt zur aktiven Challenge weitergeleitet.
    *   Können Lösungen im geforderten Format hochladen.

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

## 📂 Projektstruktur

```
challenge_plattform/
├── app.py                # Einstiegspunkt
├── config.py              # Konfiguration
├── extensions.py          # Datenbank & Extensions
├── models.py               # Datenbankmodelle
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
│   │   └── fonts/           # Handschriften für die Unterschrift auf den Urkunden (OFL)
│   └── ...                  # eigenes CSS, Bilder
├── templates/               # HTML Templates
├── tests/                   # automatische Tests (pytest)
├── uploads/                 # Hochgeladene Abgaben (wird erstellt)
└── data/                    # SQLite Datenbank (wird erstellt)
```

## 🙏 Herkunft & Mitwirkende

Dieses Projekt basiert auf der ursprünglichen Version von [frankjuchim](https://github.com/frankjuchim/challenge_plattform). Ein großer Teil der hier beschriebenen Weiterentwicklung (Sicherheits-Härtung, Offline-Fähigkeit, neue Funktionen, Übersetzungen) wurde mit Unterstützung von KI (Claude Code) umgesetzt.

## 📝 Lizenz

Dieses Projekt wurde für eine Weiterbildungsmaßnahme Informatik für Lehrkräfte erstellt.
