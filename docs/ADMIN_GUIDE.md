# 🧭 Leitfaden für den Wettbewerbstag

Die README erklärt, **wie** die Anwendung installiert wird und **welche**
Funktionen es gibt. Dieser Leitfaden beschreibt den **Ablauf**: was wann zu
tun ist, und was zu tun ist, wenn etwas klemmt.

Die Kästen mit **Aus der Praxis** sind absichtlich leer oder knapp gehalten –
sie sind zum Selberfüllen gedacht, nach dem ersten und zweiten Durchlauf.
Was dort steht, weiß nur, wer mit einer echten Klasse im Raum stand.

---

## 📅 Eine Woche vorher

1. **Anwendung auf den Stand bringen.** Die Startdatei einmal mit
   `--aktualisieren` aufrufen, also `start_windows.bat --aktualisieren` in
   der Eingabeaufforderung bzw. `./start_linux.sh --aktualisieren`. Wer die
   Plattform als ZIP geholt hat, geht den Weg aus der README unter
   [Aktualisieren](../README.md#aktualisieren) – dort stehen beide Fälle.

   Das braucht Internet – also zu Hause oder am Lehrerrechner, nicht am
   Wettbewerbstag.

2. **Tests laufen lassen**, wenn eine Entwicklungsumgebung eingerichtet ist:
   ```bash
   pip install -r requirements.txt -r requirements-dev.txt
   pytest
   ```
   Wenn `pytest` durchläuft, funktionieren Anmeldung, Abgabe, Bewertung,
   Rangliste und Urkunden.

3. **Auf Updates sehen:**
   ```bash
   python werkzeuge/vendor_aktualisieren.py --pruefen   # Frontend
   python werkzeuge/pakete_pruefen.py                   # Python-Pakete
   ```
   Beide brauchen Internet und ändern nichts, sie zeigen nur an. Eine neue
   Hauptversion kurz vor dem Wettbewerb **nicht** mehr einspielen – und wenn
   doch etwas aktualisiert wird, dann eines nach dem anderen und danach
   `pytest`.

4. **Wettbewerb anlegen** unter `/admin` → *Neuer Wettbewerb*: Name,
   Startzeit, Endzeit. Der Name ist der, unter dem die Teams den Wettbewerb
   sehen – „Scratch-Wettbewerb der Klasse 6b“ etwa. Er steht auf der
   Startseite, der Rangliste und auf den Urkunden, und er bleibt bei
   diesem Wettbewerb, auch wenn später ein anderer läuft; seine Urkunden
   tragen ihn also auch nächstes Jahr noch. Einen eigenen Untertitel kannst
   du dazuschreiben; leer gelassen gilt der aus *Einstellungen*.

5. **Aufgaben anlegen oder einlesen.** Fertige Sätze liegen unter
   `beispiele/` (Scratch, Calliope) und werden auf der Aufgaben-Seite mit
   **⬆️ Datei einlesen** übernommen. Aufgaben aus einem früheren Wettbewerb
   lassen sich dort ebenso einzeln oder als Satz exportieren und wieder
   einlesen.

6. **Urkundenformat wählen** unter *Einstellungen*: Querformat oder Hochformat.
   Am besten jetzt schon eine Probeurkunde ausdrucken – dann weißt du, ob
   Drucker und Papier mitspielen.

7. **Pro Aufgabe festlegen:** Punkte, erlaubtes Dateiformat
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
      meist an der Firewall des Schul-PCs (Port 8000 eingehend erlauben,
      bzw. den Port aus `PORT` in der `.env`).
- [ ] **Adresse notieren.** Sie steht auch auf der Startseite unter dem
      QR-Code und lässt sich abtippen – wichtig, weil an normalen PCs und
      Laptops ein QR-Code nichts nützt.
- [ ] **Beamer testen** mit der Rangliste `/scoreboard`. Die Restzeit steht
      dort oben, dieselbe, die die Teams sehen.

> **Aus der Praxis:** Welche Hürde gab es im Schulnetz?
>
> _(hier eintragen)_

---

## 🏁 Am Wettbewerbstag

### Vor dem Start

1. Server starten: die Startdatei öffnen (`start_windows.bat`,
   `start_macos.command` oder `./start_linux.sh`), oder von Hand
   `python app.py` in der aktivierten Umgebung.
   Im Terminal stehen beide Adressen (lokal und fürs Netzwerk) und der Pfad
   der Protokolldatei. **Das Fenster offen lassen.**
2. Wettbewerb unter `/admin` **aktivieren**.
3. Rangliste `/scoreboard` an die Wand werfen. Oben läuft die Zeit, darunter
   füllt sich die Tabelle, sobald du bewertest.
4. Teams melden sich selbst auf der Startseite `/` an: Teamname und ein
   Passwort, das sie sich ausdenken. Jedes Team merkt sich beides. Danach
   landen sie auf ihrer Wettbewerbsseite `/challenge`, wo die Restzeit über
   den Aufgaben steht.

### Die Zeit einstellen

Drei Wege führen zur Endzeit, und gespeichert wird immer sie:

- **Uhrzeiten**: unter *Name & Zeiten* Start- und Endzeit eintragen. Der Weg
  für einen Wettbewerb, der zu einer festen Uhrzeit beginnt.
- **Dauer in Minuten**: im selben Formular das Feld *Dauer in Minuten*
  füllen. Die Endzeit wird daraus ausgerechnet – Startzeit plus Dauer, ohne
  Startzeit ab jetzt. Eine eingetragene Endzeit wird dabei überschrieben.
- **▶ Jetzt starten für … Minuten**: der Knopf auf der Wettbewerbsseite. Ein
  Klick setzt Start auf jetzt und Ende auf jetzt plus Dauer. Der Weg für die
  Schulstunde, in der es selten pünktlich losgeht.

Alles davon geht auch **während** der Wettbewerb läuft: Die Teamseiten laden
sich innerhalb von etwa 15 Sekunden von selbst neu und zeigen dann die neue
Restzeit. Sag trotzdem kurz Bescheid – eine Uhr, die plötzlich anders steht,
verunsichert sonst.

**In der nächsten Woche weitermachen:** am Ende der Stunde **⏸ Pause**
drücken, in der nächsten Woche **▶ Fortsetzen**. Bei einer so langen Pause
ist es sauberer, die Endzeit beim Fortsetzen neu zu setzen, statt sie um eine
Woche verschieben zu lassen: *Jetzt starten für … Minuten* macht genau das in
einem Klick. Abgaben, Punkte und Namen bleiben dabei alle erhalten.

### Während des Wettbewerbs

- **Abgaben bewerten** unter `/admin` → *Abgaben*. Punkte und ein kurzes
  Feedback pro Abgabe.
- **Hinweis freischalten**, wenn eine Aufgabe zu schwer ist: auf der
  Aufgaben-Seite umschalten. Der Hinweis erscheint bei allen Teams innerhalb
  von etwa 15 Sekunden, ohne dass jemand neu laden muss.
- **Pausieren**, wenn etwas geklärt werden muss: **⏸ Pause** sperrt alle
  Abgaben und hält die Uhr an, **▶ Fortsetzen** gibt sie wieder frei und
  schiebt die Endzeit um die Dauer der Pause nach hinten. Den Teams geht also
  keine Arbeitszeit verloren, und du musst nichts nachrechnen. Auf den
  Teamseiten erscheint innerhalb von etwa 15 Sekunden von selbst ein Kasten
  *⏸ Kurze Pause*, die Zeitleiste wird orange, und die Rangliste am Beamer
  zeigt dieselbe stillstehende Zeit. Beim Fortsetzen verschwindet der
  Kasten genauso von selbst wieder. Die Aufgaben bleiben in der Pause
  absichtlich lesbar – nachdenken und nachlesen darf ein Team, nur abgeben
  nicht.
- **Rangliste** `/scoreboard` aktualisiert sich alle 30 Sekunden von selbst und
  trägt die Restzeit oben — sie ist die Seite für den Beamer, den ganzen
  Wettbewerb über. Eine eigene Countdown-Seite gibt es nicht mehr.

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
5. **Eine Urkunde nachreichen**, wenn jemand gefehlt hat: Die Urkunden-Kachel
   auf der Seite des betreffenden Wettbewerbs führt auch dann noch zu seinen
   Urkunden, wenn längst ein anderer aktiv ist. Punkte, Namen und
   Veranstaltungsname sind die von damals.

---

## 🔧 Wenn etwas klemmt

| Symptom | Ursache und Abhilfe |
|---|---|
| Team tippt seinen Namen anders geschrieben | Beim **Anmelden** ist das in Ordnung: „die pixelpiraten“ findet „Die Pixelpiraten“, solange es nur ein Team dieses Namens gibt. Nur wenn zwei Teams nebeneinander existieren, die sich allein in der Schreibweise unterscheiden, muss die Schreibweise stimmen. |
| Zwei Teams mit fast gleichem Namen | Beim **Registrieren** zählt die Schreibweise: „Die Hacker“ und „die hacker“ werden zwei verschiedene Teams. Umgebende Leerzeichen werden dagegen entfernt, `„ Team A “` wird zu `„Team A“`. Wenn das stört, Team löschen und neu anmelden lassen. |
| Ein Team kommt nicht mehr rein | Passwort vergessen. `/admin` → *Teams* → neues Passwort setzen und dem Team sagen. Das alte wird nicht angezeigt – auch nicht dir. |
| Ein Team hat die falsche Datei hochgeladen | `/admin` → *Abgaben* → **🔓 Erneut abgeben erlauben**. Das gilt **einmal**; die bisherige Bewertung wird dabei gelöscht und die Abgabe landet wieder in der Warteschlange. |
| „Abgabe nicht möglich" bei einem Team | Wettbewerb pausiert, Endzeit überschritten, oder das Team gehört zu einem anderen Wettbewerb. Der Grund steht seit Neuestem als Meldung auf der Wettbewerbsseite des Teams. |
| Falsches Dateiformat wird abgewiesen | Das erlaubte Format steht pro Aufgabe und in der Meldung, die das Team bekommt. Prüfen, ob es zu dem passt, was die Umgebung tatsächlich exportiert (Scratch: `.sb3`, MakeCode-Calliope: `.hex`). |
| Wettbewerb gelöscht, ein Team sitzt noch davor | Mit dem Wettbewerb sind seine Teams weg. Das Team landet beim nächsten Klick auf der Startseite und meldet sich dort für den nächsten Wettbewerb neu an. |
| Nach dem Update auf v1.1.0 waren alle Teams abgemeldet | Einmalig und so gewollt: Anmeldungen aus der Zeit davor galten nicht mehr. Teamname und Passwort blieben, die Teams meldeten sich einmal neu an. Spätere Updates melden niemanden ab. Ein Update spielt man trotzdem besser vor dem Wettbewerb ein als mittendrin. |
| Versehentlich beendet | **🔓 Wieder öffnen** auf der Wettbewerbsseite. Die Endzeit wird gelöscht und muss neu gesetzt werden. |
| Teams sehen die geänderte Zeit nicht | Normalerweise kommt sie innerhalb von etwa 15 Sekunden von selbst an; die Teamseiten fragen den Server in diesem Takt nach dem Stand. Bleibt die alte Zeit stehen, hat das Gerät die Verbindung zum Server verloren oder das Tablet hat geschlafen. Einmal neu laden, dann stimmt sie wieder. |
| Ein Gerät erreicht den Server nicht | Zuerst die Adresse auf der Startseite mit der im Terminal vergleichen. Dann Firewall. Dann, ob das Gerät im selben Netz hängt (nicht im Gast-WLAN). |
| Auf der Startseite steht `127.0.0.1` | Das Netz hat kein Gateway, die Anwendung kann ihre eigene Adresse nicht erfragen – sie sagt das beim Start. Adresse am Server ablesen (`ip addr` bzw. `ipconfig`) und als `LAN_ADRESSE=192.168.…` in die `.env` eintragen, dann neu starten. |
| Datenbank fehlt oder ist kaputt | Anwendung beenden. `data/challenge.db` zur Seite legen, die passende Sicherung `data/challenge-vor-…​.db` nach `data/challenge.db` umbenennen, neu starten. Die Sicherungen entstehen automatisch vor jeder Strukturänderung – eine regelmäßige Sicherung ersetzen sie nicht. |
| Hochgeladene Dateien fehlen | Die Abgaben liegen unter `uploads/<Team-Nummer>/`. Aus der letzten Sicherung dieses Verzeichnisses zurückkopieren; die Datenbank zeigt auf genau diese Pfade. Ohne Sicherung bleiben Punkte und Bewertungen erhalten, nur die Programme sind weg. |
| Etwas ist abgestürzt | In `logs/anwendung.log` steht der Fehler mit Zeitstempel und Adresse der Seite. Diese Datei ist auch nach dem Schließen des Terminals noch da. |
| Nach STRG+C fragt Windows „Batchvorgang abbrechen (J/N)?“ | Die Frage stellt Windows bei jeder `.bat`-Datei. Die Plattform ist da schon beendet – J oder N, beides schließt das Fenster. |
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
