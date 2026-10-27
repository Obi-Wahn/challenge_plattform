# 🛠 Entwicklung

Diese Seite ist für alle, die am Code arbeiten. Wer die Plattform nur
einsetzt, braucht sie nicht: Installation und Funktionen stehen in der
[README](../README.md), der Ablauf eines Wettbewerbs im
[Leitfaden](ADMIN_GUIDE.md).

- [Von Hand einrichten](#-von-hand-einrichten)
- [Vor einem Wettbewerb](#-vor-einem-wettbewerb)
- [Frontend-Bibliotheken aktualisieren](#-frontend-bibliotheken-aktualisieren)
- [Python-Pakete aktuell halten](#-python-pakete-aktuell-halten)
- [Tests](#-tests)
- [Projektstruktur](#-projektstruktur)

## 🧰 Von Hand einrichten

Ohne Startdatei, etwa um am Code zu arbeiten:

1.  **Virtuelle Umgebung erstellen und aktivieren**
    ```bash
    python -m venv .venv
    
    # Mac/Linux:
    source .venv/bin/activate
    
    # Windows:
    .venv\Scripts\activate
    ```

2.  **Abhängigkeiten installieren**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Konfiguration**
    Erstelle eine `.env` Datei im Hauptverzeichnis (siehe `.env.example`):
    ```ini
    SECRET_KEY=dein-geheimer-schluessel
    ADMIN_PASSWORD=dein-sicheres-passwort
    FLASK_DEBUG=false
    ```
    `SECRET_KEY` und `ADMIN_PASSWORD` sind Pflicht und müssen eigene Werte sein: Mit den Beispielwerten von hier oder aus `.env.example` startet die Anwendung nicht, denn wer den Schlüssel kennt, kommt ohne Passwort in die Steuerzentrale. Einen passenden Schlüssel gibt `python -c "import secrets; print(secrets.token_hex(32))"` aus. Ist er kürzer als 32 Zeichen, warnt die Anwendung beim Start. `FLASK_DEBUG` sollte in einem Netzwerk mit mehreren Nutzern (z. B. der Schul-LAN) immer auf `false` bleiben; der eingebaute Debugger erlaubt sonst beliebige Code-Ausführung auf dem Server.

4.  **Datenbank vorbereiten**
    Nichts zu tun: Beim ersten Start legt die Anwendung die Datenbank an. Bringt
    ein Update neue Spalten mit, ergänzt sie sie beim Start und sichert die
    Datenbank vorher, siehe [Daten und Sicherungen](../README.md#-daten-und-sicherungen).

5.  **Anwendung starten**
    ```bash
    python app.py
    ```
    Die Konsole zeigt beim Start die genaue Adresse an, unter der die Anwendung erreichbar ist — sowohl lokal (`http://localhost:8000`) als auch die Netzwerk-Adresse für andere Geräte im selben Netz.

    Lässt sich die Netzwerk-Adresse nicht ermitteln oder ist Port 8000 belegt,
    hilft ein Eintrag in der `.env`, siehe
    [Adresse und Port](../README.md#adresse-und-port) in der README.

## 📅 Vor einem Wettbewerb

Rechtzeitig vorher, nachdem die Plattform auf den neuen Stand gebracht ist
(siehe [Leitfaden](ADMIN_GUIDE.md#-rechtzeitig-vorher)):

**Tests laufen lassen:**
```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```
Wenn `pytest` durchläuft, funktionieren Registrierung, Anmeldung, Abgabe,
Bewertung, Rangliste und Urkunden.

**Auf Updates sehen:**
```bash
python werkzeuge/vendor_aktualisieren.py   # Frontend
python werkzeuge/pakete_pruefen.py         # Python-Pakete
```
Beide brauchen Internet und ändern nichts, sie zeigen nur an. Eine neue
Hauptversion kurz vor dem Wettbewerb **nicht** mehr einspielen – und wenn
doch etwas aktualisiert wird, dann eines nach dem anderen und danach
`pytest`.

## 🔄 Frontend-Bibliotheken aktualisieren

Bootstrap, EasyMDE, Font Awesome, scratchblocks und die Handschriften liegen als Dateien
unter `static/vendor/` im Repo – nur so funktioniert die Anwendung ohne
Internet. Der Preis dafür: Sie aktualisieren sich nicht von selbst. Welche
Fassungen dort liegen, steht in `static/vendor/versionen.json`.

Nachsehen, ob es neuere gibt (ändert nichts):

```bash
python werkzeuge/vendor_aktualisieren.py
```

```
  bootstrap                 5.3.8  ->  6.0.0     (neue Hauptversion - Darstellung vorher prüfen)
  easymde                  2.21.0      aktuell
  fontawesome-free          7.3.1      aktuell
  scratchblocks             3.7.1  ->  3.7.2     (neuere Fassung)
  caveat                    0.4.2      aktuell
  dancing-script            0.4.2      aktuell
  great-vibes               0.4.1      aktuell

Zum Übernehmen:
  python werkzeuge/vendor_aktualisieren.py --setzen bootstrap=6.0.0
```

Die neueren Fassungen hier sind ausgedacht; welche wirklich erscheinen, hängt
vom Tag ab.

`--setzen` trägt die Fassung in `versionen.json` ein und holt die Dateien
gleich. Die Namen in der linken Spalte sind genau die, die `--setzen` annimmt –
ohne Leerzeichen, damit sie sich auch in der PowerShell eintippen lassen.
Danach:

```bash
pytest
python app.py     # und die Seiten einmal ansehen
```

Fehlen Dateien unter `static/vendor/` oder sind sie beschädigt, holt
`python werkzeuge/vendor_aktualisieren.py --holen` genau die Fassungen aus
`versionen.json` neu.

Das Skript holt die Dateien aus der npm-Registry, prüft die Prüfsumme und
ersetzt nur das, was sich geändert hat. Es braucht Internet – also am
heimischen Rechner ausführen, nicht während eines Wettbewerbs. Bei einer
**neuen Hauptversion** (der ersten Zahl) lohnt der Blick in die Oberfläche
besonders: Dort ändern sich schon mal Klassennamen oder Symbole.

## 🐍 Python-Pakete aktuell halten

Die Pakete in `requirements.txt` sind auf feste Fassungen genagelt – so läuft
auf dem Schul-PC genau das, was hier getestet wurde. Genagelt ist alles, was
die Plattform selbst importiert, darunter SQLAlchemy und MarkupSafe;
`tests/test_pakete.py` passt darauf auf. Was diese Pakete ihrerseits brauchen,
etwa Jinja2 oder Pillow, wählt pip beim Installieren. Der Preis fürs Nageln:
Die Pakete aktualisieren sich nicht von selbst, und niemand sagt einem, wenn
eine Sicherheitskorrektur erschienen ist.

Nachsehen, ob es Neueres gibt (ändert nichts):

```bash
python werkzeuge/pakete_pruefen.py
```

```
  requirements.txt
    Flask                       3.1.3      aktuell
    Werkzeug                    3.1.8  ->  3.1.9
    Flask-Limiter               4.1.1  ->  5.0.0  (neue Hauptversion - Änderungsliste lesen)
    fpdf2                       2.8.8  ->  2.9.0  (nicht übernehmen: braucht Python >=3.12, die Anwendung setzt 3.11 voraus)
```

Gekürzt; welche Fassungen dort erscheinen, hängt vom Tag ab.

Eine Fassung übernehmen:

```bash
python werkzeuge/pakete_pruefen.py --setzen Werkzeug=3.1.9
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

**Eines nach dem anderen**, nicht alle auf einmal: Sonst lässt sich bei einem
fehlgeschlagenen Test nicht sagen, welches Paket ihn verursacht hat.

Verlangt eine neue Fassung ein neueres Python, als die Anwendung voraussetzt,
steht sie mit **„nicht übernehmen“** in der Liste und wird nicht vorgeschlagen;
auch `--setzen` lehnt sie ab. Am eigenen Rechner mit einem neueren Python liefe
sie zwar, auf einem Schul-PC mit dem ältesten erlaubten Python ließe sie sich
aber nicht installieren. Soll sie trotzdem her, muss erst die Grenze steigen –
in `app.py`, `starter.py`, dem Werkzeug, `ruff.toml`, der CI und in der
README; `tests/test_pakete.py` passt auf, dass alle dieselbe Zahl nennen.
Vorabfassungen (alpha, beta, rc) werden gar nicht erst vorgeschlagen.

Das Skript braucht Internet – also am heimischen Rechner ausführen, nicht
während eines Wettbewerbs.

## ✅ Tests

Das Projekt bringt automatische Tests mit. Sie prüfen den ganzen Ablauf – vom
Registrieren eines Teams über Abgabe, Bewertung und Rangliste bis zu Urkunden,
Aufgaben-Export und den Datenbank-Änderungen beim Start. Nach jeder Änderung am
Code lohnt sich ein Durchlauf, besonders vor einem echten Wettbewerb.

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

Die Tests laufen gegen eine eigene Datenbank in einem temporären Verzeichnis.
`data/challenge.db` wird dabei nie angefasst – ein Testlauf kann also keine
echten Wettbewerbsdaten beschädigen. Passwörter hashen die Tests mit einem
schnellen Verfahren statt mit scrypt, und die Testdatenbank wartet nicht, bis
die Platte jedes Schreiben bestätigt. So dauert ein Lauf rund eine halbe
Minute; die Anwendung selbst bleibt bei scrypt und schreibt wie immer.

Zusätzlich prüft `ruff` den Code auf echte Fehler – unbenutzte Importe,
unbekannte Namen, Tippfehler in Variablen. Stil und Formatierung bleiben
absichtlich ungeprüft:

```bash
ruff check .
```

Beides läuft auch automatisch: Bei jedem Push und jedem Pull Request führt
GitHub dieselben zwei Befehle aus, auf Python 3.11, 3.13, 3.14 und 3.15. Am Pull Request
steht dann ein grünes Häkchen oder ein rotes Kreuz – man muss also nicht
daran denken, selbst zu testen. Die Einstellungen dazu stehen in
`.github/workflows/tests.yml`.

Einzelne Bereiche lassen sich gezielt prüfen:

```bash
pytest tests/test_submissions.py       # nur die Abgaben
pytest -k "urkunde"                    # alles rund um Urkunden
pytest -v                              # mit Namen jedes einzelnen Tests
```

**Wettbewerb und Zeit**

| Datei | prüft |
| --- | --- |
| `test_challenge_status.py` | geplant / läuft / pausiert / beendet, Restzeiten |
| `test_dauer_und_pause.py` | Dauer in Minuten, „Jetzt starten“, Pause hält die Uhr an |
| `test_zeitleiste.py` | die Restzeit-Leiste auf Wettbewerbsseite und Rangliste |
| `test_rangliste_einfrieren.py` | die Rangliste vor Schluss einfrieren, von der Einstellung über Pause und Ende bis zum Auflösen |
| `test_podest_nach_ende.py` | nach dem Ende führt die Rangliste zum Siegerpodest, die ganze Rangliste über den Link darunter |
| `test_durchsage.py` | Durchsagen an alle Teams, vom Schalter im Formular bis auf Teamseite und Rangliste |
| `test_korrektur_ohne_freigabe.py` | Teams korrigieren ihre Abgabe selbst, vom Schalter im Formular über Teamseite und Bewertungsseite bis zur Sicherung |
| `test_aktualisierung.py` | die Teamseite holt sich den Stand von selbst |
| `test_veranstaltungsname.py` | eigener Name und Gruß je Wettbewerb, Urkunden für ältere Wettbewerbe |
| `test_aktiver_wettbewerb.py` | welcher Wettbewerb gilt, wird ausdrücklich gewählt – auch nach dem Löschen und Einlesen |

**Teams, Abgaben, Bewertung**

| Datei | prüft |
| --- | --- |
| `test_teams.py` | Registrierung, Anmeldung, Bindung an den Wettbewerb, Team-Verwaltung |
| `test_sitzung.py` | die Anmeldung gilt nicht mehr, wenn ihr Wettbewerb gelöscht ist |
| `test_submissions.py` | Abgabe, leere Datei, doppelt abgeschickte Abgabe, Korrektur nach Freigabe, Bewertung |
| `test_bewertungsseite.py` | die Bewertungsseite ordnet die Abgaben nach Aufgaben, lädt Code nach, statt ihn mitzuschicken, und wandelt jeden Aufgabentext nur einmal um |
| `test_bewertungszugang.py` | das Passwort nur zum Bewerten: einrichten, anmelden, was es darf und was nicht, abmelden beim Wechsel |
| `test_scratch_skripte.py` | die Skripte einer `.sb3` als Blöcke, auf Deutsch und robust gegen kaputte oder bearbeitete Dateien |
| `test_snap_skripte.py` | die Skripte eines Snap!-Projekts als Blöcke, an echten Exporten aus Snap! 12 (`tests/snap/`), dazu Open Roberta und bearbeitete Dateien |
| `test_skripte_teamseite.py` | ein Team sieht die Skripte seiner eigenen Abgabe, eine fremde bekommt es nicht zu sehen |
| `test_aufraeumen.py` | hochgeladene Dateien verschwinden mit ihrer Abgabe |
| `test_ablageort.py` | Abgaben werden auch nach einem Update in einen neuen Ordner gefunden und aufgeräumt |
| `test_scoring.py` | Rangliste und Podium, auch bei Gleichstand |
| `test_certificates.py` | Urkunden-PDF, Unterschrift, Namen der Teammitglieder, Download durch die Teams |
| `test_mitgliedernamen.py` | Namen eintragen, kontrollieren, freigeben |

**Seiten und Bedienung**

| Datei | prüft |
| --- | --- |
| `test_startseite.py` | QR-Code, abtippbare Adresse und Startseite ohne Scrollen |
| `test_navigation.py` | die obere Leiste, je nach Stand des Wettbewerbs, und der Zurück-Link oben auf den Admin-Seiten |
| `test_farbschema.py` | hell oder dunkel: der Umschalter in der Leiste, die Wahl bleibt im Browser; Editorleiste und Ranglistenpunkte bleiben im dunklen Modus lesbar |
| `test_zeichen.py` | bunte Zeichen tragen den Zusatz, der sie auch unter Windows bunt zeigt; Mülleimer und Pause bleiben überall Umriss |
| `test_fusszeile.py` | Name in der Fußzeile, Jury-Anmeldung, Link auf das Repository |
| `test_admin.py` | Steuerzentrale, Wettbewerbs-Seite, Beenden, Aktivieren |
| `test_fehlerseiten.py` | eigene deutsche Seiten für 400/403/404/413/429/500 |

**Betrieb und Werkzeuge**

| Datei | prüft |
| --- | --- |
| `test_starter.py` | die Schritte hinter den Startdateien, ohne echtes pip und git |
| `test_stand.py` | die Version beim Start, aus git oder aus der `stand.txt` eines ZIPs |
| `test_netzwerk.py` | die Adresse, unter der die Teams den Server erreichen |
| `test_protokoll.py` | `logs/anwendung.log` entsteht, hält die wichtigen Ereignisse fest und bleibt beim gewöhnlichen Betrieb still, und im Terminal steht jede Meldung nur einmal |
| `test_migrations.py` | Datenbank aus einer älteren Version weiterbenutzen |
| `test_task_exchange.py` | Aufgaben sichern und wiederverwenden |
| `test_wettbewerb_sicherung.py` | einen ganzen Wettbewerb als ZIP sichern und als neuen einlesen, Namen und Passwörter nur auf Wunsch; der Beispiel-Wettbewerb liest sich ohne Anpassung ein |
| `test_wettbewerb_aufraeumen.py` | nach dem Wettbewerb aufräumen: Teams und Abgaben löschen, Protokolldatei leeren, Sicherungskopien löschen |
| `test_schwierigkeit.py` | die Schwierigkeit einer Aufgabe, von der Eingabe bis in die Datei |
| `test_reihenfolge.py` | die Reihenfolge der Aufgaben mit ▲ und ▼, von der Aufgabenliste über die Nummern auf der Teamseite bis in Rangliste und Sicherung |
| `test_leitfaden.py` | der Leitfaden nennt nur Seiten und Dateien, die es gibt |
| `test_vendor.py` | Versionsliste und `static/vendor/` bleiben deckungsgleich |
| `test_pakete.py` | das Werkzeug, das nach neueren Python-Paketen sieht |

**Sicherheit**

| Datei | prüft |
| --- | --- |
| `test_security.py` | CSRF, Passwörter, Uploads, Rate-Limit, keine Beispielwerte als Schlüssel |
| `test_eingaben.py` | Eingaben werden geprüft, auch am Formular vorbei |

## 📂 Projektstruktur

```
challenge_plattform/
├── start_windows.bat       # Startdateien: doppelklicken, der Rest geht von selbst
├── start_macos.command
├── start_linux.sh
├── starter.py              # was die Startdateien tun: einrichten, dann starten
├── stand.py                # welche Version läuft, aus git oder stand.txt
├── stand.txt               # von GitHub im ZIP ausgefüllt, im Repository nur Platzhalter
├── app.py                  # Einstiegspunkt
├── config.py               # Konfiguration
├── extensions.py           # Datenbank & Extensions
├── models.py               # Datenbankmodelle
├── scoring.py              # Rangliste und Podium
├── certificates.py         # Urkunden als PDF
├── task_exchange.py        # Aufgaben sichern und einlesen
├── wettbewerb_sicherung.py # einen ganzen Wettbewerb als ZIP sichern und einlesen
├── datenschutz.py          # aufräumen: Teams und Abgaben, Protokolldatei, Sicherungskopien
├── migrationen.py          # Umbauten an einer bestehenden Datenbank beim Start
├── network.py              # Adresse, unter der die Teams beitreten
├── sitzung.py              # Anmeldung eines Teams oder zum Bewerten und ihre Gültigkeit
├── protokoll.py            # die Zeilen, die in logs/anwendung.log gehen
├── uploads.py              # Dateinamen der Abgaben, löscht Dateien mit ihrer Abgabe
├── task_rules.py           # Regeln für Aufgabenwerte, für Formular und Import
├── skripte.py              # die Skripte einer Abgabe als Blöcke, für Bewertungs- und Teamseite
├── scratch_skripte.py      # liest die Skripte aus einer .sb3
├── snap_skripte.py         # liest die Skripte aus einem Snap!-Projekt (.xml)
├── requirements.txt        # Abhängigkeiten
├── requirements-dev.txt    # zusätzlich zum Testen
├── pytest.ini              # Test-Einstellungen
├── ruff.toml               # Einstellungen der Fehlerprüfung
├── .github/workflows/      # Tests laufen automatisch bei jedem Push
├── .env.example            # Vorlage für die eigene .env
├── blueprints/             # Modulare Routen
│   ├── admin.py
│   ├── auth.py
│   ├── challenge.py
│   └── public.py
├── static/
│   ├── vendor/             # Lokal eingebundene Frontend-Bibliotheken (Bootstrap, EasyMDE, Font Awesome, scratchblocks)
│   │   ├── fonts/          # Handschriften für die Unterschrift auf den Urkunden (OFL)
│   │   └── versionen.json  # welche Fassungen hier liegen
│   └── ...                 # eigenes CSS, Bilder
├── templates/              # HTML Templates
├── tests/                  # automatische Tests (pytest)
├── beispiele/              # fertige Aufgabensätze und ein Beispiel-Wettbewerb zum Einlesen
├── werkzeuge/              # Hilfsskripte (Bibliotheken und Pakete prüfen)
├── docs/
│   ├── ADMIN_GUIDE.md      # Leitfaden für den Wettbewerbstag
│   ├── ENTWICKLUNG.md      # diese Anleitung
│   └── bilder/             # Screenshots für die README
├── uploads/                # Hochgeladene Abgaben (wird erstellt)
├── logs/                   # Protokolldatei (wird erstellt)
└── data/                   # SQLite Datenbank und ihre Sicherungen (werden erstellt)
```
