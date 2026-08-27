# 🚀 Coding-Wettbewerb-Plattform

Eine Flask-basierte Webanwendung für Coding-Challenges, Hackathons und Programmier-Wettbewerbe an Schulen — läuft komplett lokal im eigenen Netzwerk, **ganz ohne Internetzugriff**.

![Status](https://img.shields.io/badge/Status-Active-success)
![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.x-green.svg)
![Bootstrap](https://img.shields.io/badge/Bootstrap-5-purple.svg)

## 🌟 Features

### Für Teilnehmer
*   **Team-Registrierung & Login**: Sichere Anmeldung mit Teamnamen und Passwort.
*   **Dashboard**: Übersicht über aktive Challenges und Aufgaben mit Fortschrittsanzeige.
*   **Datei-Uploads je nach Aufgabe**: Processing (`.pde`), Scratch (`.sb`/`.sb3`), Python (`.py`), Java (`.java`), MakeCode/Calliope (`.hex`/`.mkcd`).
*   **Hinweise pro Aufgabe**: Admins können während des Events optionale Tipps freischalten, falls ein Team nicht weiterkommt.
*   **Live Scoreboard**: Echtzeit-Ranking mit Punkten pro Aufgabe und Gesamtpunktzahl.
*   **QR-Code auf der Startseite**: zum schnellen Beitreten per Smartphone, z. B. wenn die Seite beamt wird.
*   **Responsive Design**: für Desktop, Tablet und Smartphone optimiert.

### Für Administratoren
*   **Admin-Dashboard**: Zentrale Verwaltung aller Challenges.
*   **Challenge-Management**: Erstellen, Pausieren und Beenden von Challenges.
*   **Aufgaben-Konfiguration**:
    *   Erstellen von Aufgaben mit detaillierten Beschreibungen.
    *   **Markdown Support**: Aufgabenbeschreibungen werden mit Markdown formatiert.
    *   **Dateiformat-Wahl**: Festlegen des erlaubten Dateityps pro Aufgabe.
    *   Optionale Hinweise, die während des Events sichtbar/unsichtbar geschaltet werden können.
*   **Review-System**:
    *   Anzeige eingereichter Lösungen inklusive **Aufgabenbeschreibung**.
    *   **In-Browser Code Preview**: Code direkt im Browser lesen.
    *   Download-Option für lokale Tests.
    *   Bewertung mit Punkten (automatisch auf 0–Max. begrenzt) und Feedback.
    *   **Abgabe löschen**: Möglichkeit, fehlerhafte Abgaben komplett zu entfernen, damit Teams neu einreichen können.
*   **Team-Verwaltung**: Übersicht und Management registrierter Teams.
*   **Einstellungen**: Name und Beschreibung der Veranstaltung frei anpassbar, ohne Code zu ändern.

## 🛠 Technologien

*   **Backend**: Python, Flask, SQLAlchemy (SQLite), waitress (Produktiv-WSGI-Server).
*   **Frontend**: HTML5, CSS3, Bootstrap 5, Markdown-Editor (EasyMDE) — alle Assets liegen lokal im Repo (`static/vendor/`), keine CDN-Abhängigkeit, funktioniert komplett offline.
*   **Sicherheit**:
    *   Passwort-Hashing (Werkzeug Security).
    *   CSRF Protection (Flask-WTF).
    *   Rate-Limiting auf Login-Routen (Flask-Limiter).
    *   Secure Filename Handling.
    *   Kein Debug-Modus im Normalbetrieb (nur über `FLASK_DEBUG=true` für lokale Entwicklung).
*   **Architektur**: Modularer Aufbau mit Flask Blueprints und Application Factory Pattern.

## 🚀 Installation & Setup

Voraussetzung: Python 3.9 oder höher.

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

## 📂 Projektstruktur

```
challenge_plattform/
├── app.py                # Einstiegspunkt
├── config.py              # Konfiguration
├── extensions.py          # Datenbank & Extensions
├── models.py               # Datenbankmodelle
├── requirements.txt       # Abhängigkeiten
├── migrate_db.py          # Historisches Migrationsskript (Spalten-Migrationen laufen inzwischen automatisch beim Start)
├── .env.example            # Vorlage für die eigene .env
├── blueprints/             # Modulare Routen
│   ├── admin.py
│   ├── auth.py
│   ├── challenge.py
│   └── public.py
├── static/
│   ├── vendor/              # Lokal eingebundene Frontend-Bibliotheken (Bootstrap, EasyMDE, Font Awesome)
│   └── ...                  # eigenes CSS, Bilder
├── templates/               # HTML Templates
├── uploads/                 # Hochgeladene Abgaben (wird erstellt)
└── data/                    # SQLite Datenbank (wird erstellt)
```

## 🙏 Herkunft & Mitwirkende

Dieses Projekt basiert auf der ursprünglichen Version von [frankjuchim](https://github.com/frankjuchim/challenge_plattform). Ein großer Teil der hier beschriebenen Weiterentwicklung (Sicherheits-Härtung, Offline-Fähigkeit, neue Funktionen, Übersetzungen) wurde mit Unterstützung von KI (Claude Code) umgesetzt.

## 📝 Lizenz

Dieses Projekt wurde für eine Weiterbildungsmaßnahme Informatik für Lehrkräfte erstellt.
