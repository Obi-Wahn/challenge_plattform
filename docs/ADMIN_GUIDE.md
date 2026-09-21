# 🧭 Leitfaden für den Wettbewerbstag

Die README erklärt, **wie** die Anwendung installiert wird und **welche**
Funktionen es gibt. Dieser Leitfaden beschreibt den **Ablauf**: was wann zu
tun ist, und was zu tun ist, wenn etwas klemmt.

Die Kästen mit **Aus der Praxis** sind absichtlich leer oder knapp gehalten –
sie sind zum Selberfüllen gedacht, nach dem ersten und zweiten Durchlauf.
Was dort steht, weiß nur, wer mit einer echten Klasse im Raum stand.

---

## 📅 Eine Woche vorher

1. **Anwendung auf den Stand bringen und Tests laufen lassen.**
   ```bash
   git pull
   pip install -r requirements.txt -r requirements-dev.txt
   pytest
   ```
   Braucht Internet – also zu Hause oder am Lehrerrechner, nicht am
   Wettbewerbstag. Wenn `pytest` durchläuft, funktionieren Anmeldung,
   Abgabe, Bewertung, Rangliste und Urkunden.

2. **Auf Updates sehen** (ebenfalls nur mit Internet):
   ```bash
   python werkzeuge/vendor_aktualisieren.py --pruefen   # Frontend
   python werkzeuge/pakete_pruefen.py                   # Python-Pakete
   ```
   Beide ändern nichts, sie zeigen nur an. Eine neue Hauptversion kurz vor
   dem Wettbewerb **nicht** mehr einspielen – und wenn doch etwas
   aktualisiert wird, dann eines nach dem anderen und danach `pytest`.

3. **Wettbewerb anlegen** unter `/admin` → *Neuer Wettbewerb*: Titel,
   Startzeit, Endzeit.

4. **Aufgaben anlegen oder einlesen.** Fertige Sätze liegen unter
   `beispiele/` (Scratch, Calliope) und werden auf der Aufgaben-Seite mit
   **⬆️ Datei einlesen** übernommen. Aufgaben aus einem früheren Wettbewerb
   lassen sich dort ebenso einzeln oder als Satz exportieren und wieder
   einlesen.

5. **Urkundenformat wählen** unter *Einstellungen*: Querformat oder Hochformat.
   Am besten jetzt schon eine Probeurkunde ausdrucken – dann weißt du, ob
   Drucker und Papier mitspielen.

6. **Pro Aufgabe festlegen:** Punkte, erlaubtes Dateiformat
   (z. B. `.sb3` für Scratch, `.hex` für Calliope) und optional einen
   Hinweis. Der Hinweis bleibt verborgen, bis er freigeschaltet wird.

> **Aus der Praxis:** Wie viele Aufgaben passen in die zur Verfügung stehende
> Zeit? Welche Punktverteilung hat sich bewährt?
>
> _(hier eintragen, wenn du es weißt)_

---

## 🌙 Am Vortag

- [ ] **Probedurchlauf**: einen Testwettbewerb anlegen, ein Team anmelden,
      eine Datei hochladen, bewerten, Rangliste und Urkunde ansehen. Danach
      den Testwettbewerb löschen – mit ihm verschwinden seine Teams und
      Abgaben.
- [ ] **`data/` und `uploads/` auf einen USB-Stick kopieren.** Beide: In
      `data/` steckt die Datenbank, in `uploads/` die abgegebenen Dateien.
      Die Datenbank merkt sich zu jeder Abgabe nur den Pfad, nicht die Datei.
      Die automatische Sicherung der Anwendung liegt im selben Ordner und
      hilft nicht, wenn der Rechner ausfällt.
- [ ] **Netzwerk testen:** Server starten und von einem *anderen* Gerät die
      Adresse aufrufen, die im Terminal steht. Klappt das nicht, liegt es
      meist an der Firewall des Schul-PCs (Port 8000 eingehend erlauben).
- [ ] **Adresse notieren.** Sie steht auch auf der Startseite unter dem
      QR-Code und lässt sich abtippen – wichtig, weil an normalen PCs und
      Laptops ein QR-Code nichts nützt.
- [ ] **Beamer testen** mit der Countdown-Seite `/start` und der Rangliste
      `/scoreboard`.

> **Aus der Praxis:** Welche Hürde gab es im Schulnetz?
>
> _(hier eintragen)_

---

## 🏁 Am Wettbewerbstag

### Vor dem Start

1. Server starten:
   ```bash
   python app.py
   ```
   Im Terminal stehen beide Adressen (lokal und fürs Netzwerk) und der Pfad
   der Protokolldatei. **Das Fenster offen lassen.**
2. Wettbewerb unter `/admin` **aktivieren**.
3. Countdown-Seite `/start` an die Wand werfen.
4. Teams melden sich selbst auf der Startseite an: Teamname und ein
   Passwort, das sie sich ausdenken. Jedes Team merkt sich beides.

### Während des Wettbewerbs

- **Abgaben bewerten** unter `/admin` → *Abgaben*. Punkte und ein kurzes
  Feedback pro Abgabe.
- **Hinweis freischalten**, wenn eine Aufgabe zu schwer ist: auf der
  Aufgaben-Seite umschalten. Der Hinweis erscheint bei allen Teams sofort.
- **Pausieren**, wenn etwas geklärt werden muss: **⏸ Pause** sperrt alle
  Abgaben, **▶ Fortsetzen** gibt sie wieder frei. Die Uhr läuft dabei weiter – wenn
  die Pause länger dauert, die Endzeit nachziehen.
- **Rangliste** `/scoreboard` aktualisiert sich alle 30 Sekunden von selbst.

> **Aus der Praxis:** Ab wann die Rangliste zeigen? (Von Anfang an motiviert
> sie – kurz vor Schluss kann sie auch lähmen.)
>
> _(hier eintragen)_

### Schluss und Siegerehrung

1. **🏁 Wettbewerb beenden** auf der Wettbewerbsseite. Das setzt die Endzeit
   auf jetzt; Abgaben sind gesperrt. Gelöscht wird nichts.
2. **Letzte Abgaben zu Ende bewerten** – das geht nach dem Beenden weiter.
3. **Siegerehrung** `/siegerehrung` an die Wand werfen. Gleichstände teilen
   sich einen Platz, niemand fällt durch eine willkürliche Reihung heraus.
4. **Urkunden**: als Sammel-PDF über `/admin/urkunden.pdf` oder einzeln.
   Die Teams können ihre eigene Urkunde nach dem Beenden selbst
   herunterladen. Unter *Einstellungen* stellst du ein: Quer- oder Hochformat,
   den Namen unter der Unterschriftslinie und die Handschrift.

---

## 🔧 Wenn etwas klemmt

| Symptom | Ursache und Abhilfe |
|---|---|
| Team tippt seinen Namen anders geschrieben | Beim **Anmelden** ist das in Ordnung: „die pixelpiraten“ findet „Die Pixelpiraten“, solange es nur ein Team dieses Namens gibt. Nur wenn zwei Teams nebeneinander existieren, die sich allein in der Schreibweise unterscheiden, muss die Schreibweise stimmen. |
| Zwei Teams mit fast gleichem Namen | Beim **Registrieren** zählt die Schreibweise: „Die Hacker“ und „die hacker“ werden zwei verschiedene Teams. Umgebende Leerzeichen werden dagegen entfernt, `„ Team A “` wird zu `„Team A“`. Wenn das stört, Team löschen und neu anmelden lassen. |
| Ein Team kommt nicht mehr rein | Passwort vergessen. `/admin` → *Teams* → neues Passwort setzen und dem Team sagen. Das alte wird nicht angezeigt – auch nicht dir. |
| Ein Team hat die falsche Datei hochgeladen | `/admin` → *Abgaben* → **🔓 Erneut abgeben erlauben**. Das gilt **einmal**; die bisherige Bewertung wird dabei gelöscht und die Abgabe landet wieder in der Warteschlange. |
| „Abgabe nicht möglich" bei einem Team | Wettbewerb pausiert, Endzeit überschritten, oder das Team gehört zu einem anderen Wettbewerb. |
| Falsches Dateiformat wird abgewiesen | Das erlaubte Format steht pro Aufgabe. Prüfen, ob es zu dem passt, was die Umgebung tatsächlich exportiert (Scratch: `.sb3`, MakeCode-Calliope: `.hex`). |
| Versehentlich beendet | **🔓 Wieder öffnen** auf der Wettbewerbsseite. Die Endzeit wird gelöscht und muss neu gesetzt werden. |
| Ein Gerät erreicht den Server nicht | Zuerst die Adresse auf der Startseite mit der im Terminal vergleichen. Dann Firewall. Dann, ob das Gerät im selben Netz hängt (nicht im Gast-WLAN). |
| Etwas ist abgestürzt | In `logs/anwendung.log` steht der Fehler mit Zeitstempel und Adresse der Seite. Diese Datei ist auch nach dem Schließen des Terminals noch da. |
| Die Anwendung startet nicht | Meldung lesen: Fehlt `SECRET_KEY` oder `ADMIN_PASSWORD` in der `.env`, sagt sie das. Bricht sie beim Sichern der Datenbank ab, ist meist die Platte voll. |

> **Aus der Praxis:** Was ist dir tatsächlich passiert, das hier noch fehlt?
>
> _(hier eintragen)_

---

## 📦 Nach dem Wettbewerb

- [ ] **`data/` und `uploads/` sichern**, solange noch alles frisch ist –
      dieselben zwei Verzeichnisse wie am Vortag. In `data/` stecken Punkte
      und Bewertungen, in `uploads/` die Programme der Teams.
- [ ] **Gut gelaufene Aufgaben exportieren** (Aufgaben-Seite: **⬇️ Alle Aufgaben sichern**, oder das ⬇️ neben einer
      einzelnen Aufgabe) und
      die Datei aufheben. Beim nächsten Mal wieder einlesen.
- [ ] **Protokolldatei durchsehen**, falls etwas hakte – und die Erkenntnis
      oben in den Kasten eintragen.
- [ ] Alte Sicherungskopien in `data/` (`challenge-vor-…​.db`) löschen,
      sobald klar ist, dass alles passt.

> **Aus der Praxis:** Was würdest du beim nächsten Mal anders machen?
>
> _(hier eintragen)_
