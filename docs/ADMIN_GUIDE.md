# 🧭 Leitfaden für den Wettbewerbstag

Die README erklärt, **wie** die Anwendung installiert wird und **welche**
Funktionen es gibt. Dieser Leitfaden beschreibt den **Ablauf**: was wann zu
tun ist, und was zu tun ist, wenn etwas klemmt.

Die Kästen unter **💡 Aus der Praxis** am Ende sind absichtlich leer oder knapp
gehalten – sie sind zum Selberfüllen gedacht, nach dem ersten und zweiten Durchlauf.
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

   Welche Fassung danach läuft, steht in der Startübersicht in der Zeile
   **Version**, etwa „1.7.0 (Stand 27.09.2026)“. Mit der Nummer des neuesten
   Releases auf GitHub vergleichen.

2. **Tests laufen lassen**, wenn eine Entwicklungsumgebung eingerichtet ist:
   ```bash
   pip install -r requirements.txt -r requirements-dev.txt
   pytest
   ```
   Wenn `pytest` durchläuft, funktionieren Registrierung, Anmeldung, Abgabe,
   Bewertung, Rangliste und Urkunden.

3. **Auf Updates sehen:**
   ```bash
   python werkzeuge/vendor_aktualisieren.py   # Frontend
   python werkzeuge/pakete_pruefen.py         # Python-Pakete
   ```
   Beide brauchen Internet und ändern nichts, sie zeigen nur an. Eine neue
   Hauptversion kurz vor dem Wettbewerb **nicht** mehr einspielen – und wenn
   doch etwas aktualisiert wird, dann eines nach dem anderen und danach
   `pytest`.

4. **Wettbewerb anlegen** unter `/admin` → *Neuer Wettbewerb*: Name,
   Startzeit, Endzeit. Der Name ist der, unter dem die Teams den Wettbewerb
   sehen – „Scratch-Wettbewerb der Klasse 6b“ etwa. Er steht auf der
   Startseite, der Rangliste, den Urkunden und auch im Browsertitel, in der
   Leiste oben und in der Fußzeile, und er bleibt bei diesem Wettbewerb, auch
   wenn später ein anderer läuft; seine Urkunden tragen ihn also auch nächstes
   Jahr noch. Einen eigenen Untertitel kannst du dazuschreiben, ebenso einen
   eigenen Gruß, der auf der Startseite unter dem Namen steht (sonst „Schön,
   dass ihr dabei seid!“); leer gelassen gilt jeweils der aus *Einstellungen*. Die Werte dort sind nur die Vorgabe für die
   Zeit, in der noch kein Wettbewerb angelegt oder keiner aktiv ist.

   Ist gerade kein Wettbewerb aktiv, wird der neue es von selbst. Läuft schon
   einer, bleibt der aktiv; den neuen aktivierst du dann am Wettbewerbstag.

   Drei Häkchen gibt es erst nach dem Anlegen, auf der Seite des Wettbewerbs
   unter *Name & Zeiten*: **❄️ Rangliste vor Schluss einfrieren** und
   **📢 Durchsagen an die Teams** sind bei einem neuen Wettbewerb aus,
   **🔁 Teams dürfen ihre Abgabe selbst korrigieren** ist an.
   Was sie tun, steht unten unter *Während des Wettbewerbs*; am besten jetzt
   entscheiden, dann ist am Tag selbst nichts mehr umzustellen.

   Zum ersten Kennenlernen gibt es einen fertigen Wettbewerb: auf derselben
   Seite unten unter **Oder aus einer Sicherung einlesen** die Datei
   `beispiele/scratch-wettbewerb.zip` wählen. Er bringt ausgedachte Teams,
   Abgaben und Punkte mit, an ihm lassen sich Bewertungen, Rangliste und
   Urkunden ausprobieren. Danach den echten Wettbewerb aktivieren; den
   Beispiel-Wettbewerb kannst du löschen.

5. **Aufgaben anlegen oder einlesen.** Fertige Sätze liegen unter
   `beispiele/` (Scratch, Calliope) und werden auf der Aufgaben-Seite mit
   **⬆️ Datei einlesen** übernommen; sie bringen auch ihre Schwierigkeit
   mit. Aufgaben aus einem früheren Wettbewerb lassen sich dort ebenso
   einzeln oder als Satz exportieren und wieder einlesen.

6. **Urkundenformat wählen** unter *Einstellungen*: Querformat oder Hochformat.
   Am besten jetzt schon eine Probeurkunde ausdrucken – dann weißt du, ob
   Drucker und Papier mitspielen.

7. **Pro Aufgabe festlegen:** Punkte, erlaubtes Dateiformat
   (z. B. `.sb3` für Scratch, `.hex` für Calliope), die Schwierigkeit und
   optional einen Hinweis. Der Hinweis bleibt verborgen, bis er
   freigeschaltet wird.

   **Titel möglichst kurz halten**, zwei, drei Wörter wie „Ballon-Jagd“
   oder „Geheimes Passwort“. Über den Spalten der Rangliste steht
   „A1: Titel“, und die Spalten teilen sich die Breite des Beamers: Bei
   fünfzehn Aufgaben bleiben von einem langen Titel nur Wortanfänge. Was
   die Teams genau tun sollen, gehört in den Aufgabentext. Reicht am Beamer
   die Nummer, schaltest du die Titel unter *Einstellungen* → *Rangliste*
   ab.

   Die Schwierigkeit ist *einfach*, *mittel* oder *schwer*; „keine Angabe“
   ist auch eine Antwort, dann steht bei der Aufgabe nichts. Die Teams sehen
   sie als farbiges Schild unter dem ersten Satz der Aufgabe, gleich neben
   den Punkten, und finden so schnell etwas Passendes. Beim Sichern reist
   sie in der JSON-Datei mit; ältere Dateien ohne diese Angabe lassen sich
   unverändert einlesen.

   Die **Reihenfolge** änderst du in der Aufgabenliste mit ▲ und ▼ – je
   Klick rückt die Aufgabe eine Stelle. In dieser Reihenfolge stehen die
   Aufgaben auf der Seite der Teams (über jeder „Aufgabe 1“, „Aufgabe 2“ …),
   in der Rangliste (A1, A2 …) und in den Sicherungen. Die Nummern sind
   dieselben, du kannst also im Raum von „Aufgabe 3“ sprechen. Neue und eingelesene Aufgaben kommen ans Ende. Am besten
   vor dem Start sortieren: Wer mitten im Wettbewerb umstellt, ändert auch
   die Nummern über den Spalten der Rangliste am Beamer – die Punkte bleiben
   dabei, wo sie hingehören.

---

## 🌙 Am Vortag

- [ ] **Probedurchlauf**: einen Testwettbewerb anlegen, ein Team registrieren,
      eine Datei hochladen, bewerten, Rangliste und Urkunde ansehen. Danach
      den Testwettbewerb löschen: Steuerzentrale → Kachel **Wettbewerb**
      (*Name, Zeiten, Löschen*) → ganz unten im roten Kasten **🗑 Löschen**.
      Mit ihm verschwinden seine Teams und Abgaben. War er der aktive, ist
      danach keiner mehr aktiv: Die Steuerzentrale sagt das und zeigt die
      übrigen Wettbewerbe mit **✅ Aktivieren** – dort den richtigen wählen.
      Bis dahin können sich Teams weder registrieren noch anmelden.
- [ ] **`data/` und `uploads/` auf einen USB-Stick kopieren.** Beide: In
      `data/` steckt die Datenbank, in `uploads/` die abgegebenen Dateien.
      Die Datenbank merkt sich zu jeder Abgabe nur den Pfad, nicht die Datei.
      Die automatische Sicherung der Anwendung liegt im selben Ordner und
      hilft nicht, wenn der Rechner ausfällt.
- [ ] **Netzwerk testen:** Server starten und von einem *anderen* Gerät die
      Adresse aufrufen, die im Terminal steht. Klappt das nicht, liegt es
      meist an der Firewall des Schul-PCs (Port 8000 eingehend erlauben,
      bzw. den Port aus `PORT` in der `.env`).
- [ ] **Adresse notieren.** Sie steht auch groß auf der Startseite über
      dem QR-Code und lässt sich abtippen – wichtig, weil an normalen PCs und
      Laptops ein QR-Code nichts nützt. Dort fehlt das `http://` davor: Das
      ergänzt der Browser beim Eintippen selbst.
- [ ] **Hilft jemand beim Bewerten?** Dann unter *Einstellungen* →
      *Bewertungszugang* ein eigenes Passwort setzen (mindestens 6 Zeichen,
      nicht das Admin-Passwort) und weitergeben. Angemeldet wird sich wie du
      über **Admin-Anmeldung** unten auf jeder Seite, landet aber direkt auf
      der Bewertungsseite und kommt von dort nirgendwo anders hin. Löschen
      und Freigeben sind dort ausgeblendet. Ohne Passwort gibt es diesen
      Zugang nicht.
- [ ] **Beamer testen** mit der Rangliste `/scoreboard`. Die Restzeit steht
      dort oben, dieselbe, die die Teams sehen. Ist der Raum hell und die
      Tabelle blass, oben in der Leiste auf **☀️ Hell** wechseln. Der
      Browser des Beamer-Rechners merkt sich das; die Geräte der Teams
      zeigen weiter, was dort eingestellt ist.

---

## 🏁 Am Wettbewerbstag

### Vor dem Start

1. Server starten: die Startdatei öffnen (`start_windows.bat`,
   `start_macos.command` oder `./start_linux.sh`), oder von Hand
   `python app.py` in der aktivierten Umgebung.
   Im Terminal stehen beide Adressen (lokal und fürs Netzwerk) und der Pfad
   der Protokolldatei. **Das Fenster offen lassen.**

   Läuft die Plattform auf einem Rechner ohne Bildschirm, etwa einem
   Raspberry Pi, vorher per SSH mit `timedatectl` die Uhrzeit prüfen: Ohne
   Internet stimmt sie dort nach dem Einschalten oft nicht, und die Restzeit
   richtet sich nach ihr. Wie man sie setzt, steht in der README unter
   [Auf einem Rechner ohne Bildschirm](../README.md#auf-einem-rechner-ohne-bildschirm-etwa-raspberry-pi).
2. Wettbewerb unter `/admin` **aktivieren**: Steht der richtige schon oben in
   der Statuszeile, ist nichts zu tun. Sonst steht er weiter unten unter
   *Weitere Wettbewerbe* – dort **✅ Aktivieren**. „▶ Jetzt starten“ auf einem
   nicht aktiven Wettbewerb startet nur seine Uhr; die Meldung danach sagt,
   dass die Teams ihn erst nach dem Aktivieren sehen.
3. Rangliste `/scoreboard` an die Wand werfen. Oben läuft die Zeit, darunter
   füllt sich die Tabelle, sobald du bewertest. Über jeder Spalte stehen
   Nummer und Titel der Aufgabe, ein langer Titel gekürzt; ab Laptopbreite
   passt die Tabelle mit „Gesamt“ immer ganz auf die Seite.
4. Teams registrieren sich selbst auf der Startseite `/`: Teamname und ein
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
- **▶ Jetzt starten für … Minuten**: oben auf der Wettbewerbsseite, neben
  **⏸ Pause** und **🏁 Wettbewerb beenden**. Ein Klick setzt Start auf jetzt
  und Ende auf jetzt plus Dauer. Der Weg für die Schulstunde, in der es selten
  pünktlich losgeht. Läuft die Uhr schon, ist der Knopf nur noch umrandet und
  fragt vor einem Neustart nach.

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

- **Abgaben bewerten** unter `/admin` → *Bewertungen*. Punkte und ein kurzes
  Feedback pro Abgabe. Die Abgaben stehen nach Aufgaben geordnet, so wie auf
  der Teamseite (*Aufgabe 1*, *Aufgabe 2* …), in jeder Aufgabe die offenen
  zuerst. Oben führt *Springen zu* direkt zu jeder Aufgabe; gelb sind die,
  in denen noch etwas offen ist. **↑ nach oben** an jeder Aufgabe führt
  zurück zu dieser Leiste.
- **Mit Hilfe bewerten**: Wer mit dem Passwort für die Bewertung angemeldet
  ist, sieht dieselbe Seite, nur ohne **🗑 Abgabe vollständig löschen** und
  **🔓 Erneut abgeben erlauben**. Wer was bewertet hat, merkt sich die
  Plattform nicht. Soll niemand mehr mitbewerten, unter *Einstellungen* ein
  neues Passwort setzen oder **Bewertungszugang abschalten** – wer noch
  angemeldet ist, ist beim nächsten Klick draußen.
- **Scratch-Abgaben ansehen**: Bei einer `.sb3` zeigt **🧩 Skripte anzeigen**
  die Skripte jeder Figur als Blöcke, so wie in Scratch, nur ohne sie
  auszuführen. Ob das Projekt tut, was es soll, zeigt weiterhin erst
  **⬇️ Datei herunterladen** und Öffnen in Scratch. Blöcke aus Erweiterungen,
  die die Plattform nicht kennt, erscheinen grau mit ihrem englischen Namen;
  Kommentare aus dem Projekt fehlen.
- **Durchsage an alle Teams**, etwa „Noch 10 Minuten, bitte speichern“:
  einmal unter *Name & Zeiten* das Häkchen **📢 Durchsagen an die Teams**
  setzen, dann steht auf der Wettbewerbsseite unter den Knöpfen für die Uhr
  ein Feld mit **📢 Senden**. Der Satz erscheint innerhalb von etwa 15 Sekunden oben auf
  jeder Teamseite und über der Rangliste am Beamer. Es gilt immer nur eine
  Durchsage – eine neue ersetzt die alte, **Entfernen** nimmt sie weg. Ins
  Protokoll kommt nur, dass es eine gab, nicht ihr Text.
- **Korrekturen** machen die Teams selbst: Unter jeder abgegebenen Aufgabe
  steht **🔁 Korrektur abgeben**, die neue Datei ersetzt die alte. War die
  Abgabe schon bewertet, fallen Punkte und Feedback weg, und sie steht wieder
  als offen unter *Bewertungen*. Das geht, solange der Wettbewerb läuft.
  Willst du jede Korrektur selbst freigeben, nimm unter *Name & Zeiten* das
  Häkchen **🔁 Teams dürfen ihre Abgabe selbst korrigieren** heraus; dann
  steht unter jeder Abgabe wieder **🔓 Erneut abgeben erlauben**.
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
- **Rangliste einfrieren**, wenn es am Ende spannend bleiben soll: unter
  *Name & Zeiten* das Häkchen **❄️ Rangliste vor Schluss einfrieren** setzen
  und die Minuten vor Schluss eintragen (vorgeschlagen sind 15). Ab dann
  zeigt die Rangliste nur noch, was bis dahin abgegeben war, mit dem Hinweis
  *❄️ Eingefroren seit …*. Du bewertest weiter wie immer; eine Abgabe von
  davor zählt auch, wenn du sie erst danach bewertest. Jedes Team sieht seine
  eigenen Punkte auf seiner Seite weiter aktuell – nur den Vergleich mit den
  anderen nicht mehr. Eine Pause vor dem Einfrieren schiebt es mit dem Ende
  nach hinten, eine Pause danach nicht. Die Einstellung gilt je Wettbewerb
  und ist bei einem neuen aus.

### Schluss und Siegerehrung

1. **🏁 Wettbewerb beenden** auf der Wettbewerbsseite. Das setzt die Endzeit
   auf jetzt; Abgaben sind gesperrt. Gelöscht wird nichts.
2. **Letzte Abgaben zu Ende bewerten** – das geht nach dem Beenden weiter.
3. **Siegerehrung** `/siegerehrung` an die Wand werfen. Dort steht ein
   Siegerpodest mit Fragezeichen über den Stufen. **🥁 Nächsten Platz
   verkünden** (oder die Leertaste) stellt erst den dritten, dann den
   zweiten und zuletzt den ersten Platz auf seine Stufe; der Knopf bleibt
   dabei oben stehen, scrollen musst du nicht. Gleichstände teilen
   sich einen Platz, niemand fällt durch eine willkürliche Reihung heraus.
   Ist die Rangliste eingefroren, zeigt die Siegerehrung nur dir als
   angemeldeter Lehrkraft den echten Stand; wer die Adresse am Handy
   aufruft, sieht bloß *❄️ Die Rangliste ist eingefroren*. Nach dem letzten
   Platz **❄️ Rangliste auflösen und ansehen** drücken (der Knopf steht auch
   auf der Wettbewerbsseite), dann zeigt die Rangliste wieder alles.
4. **Urkunden**: als Sammel-PDF über `/admin/urkunden.pdf` oder einzeln.
   Die Teams können ihre eigene Urkunde nach dem Beenden selbst
   herunterladen – bei eingefrorener Rangliste erst nach dem Auflösen, denn
   auf der Urkunde steht der Platz. Unter *Einstellungen* stellst du ein: Quer- oder Hochformat,
   den Namen unter der Unterschriftslinie und die Handschrift.
5. **Eine Urkunde nachreichen**, wenn jemand gefehlt hat: Auf der
   Steuerzentrale unten *Beendet* aufklappen, beim gesuchten Wettbewerb
   **Öffnen →**, dort die Urkunden-Kachel. Das geht auch dann noch, wenn
   längst ein anderer Wettbewerb aktiv ist. Punkte, Namen und der Name des
   Wettbewerbs sind die von damals.

---

## 🔧 Wenn etwas klemmt

| Symptom | Ursache und Abhilfe |
|---|---|
| Team tippt seinen Namen anders geschrieben | Beim **Anmelden** ist das in Ordnung: „die pixelpiraten“ findet „Die Pixelpiraten“, solange es nur ein Team dieses Namens gibt. Nur wenn zwei Teams nebeneinander existieren, die sich allein in der Schreibweise unterscheiden, muss die Schreibweise stimmen. |
| Zwei Teams mit fast gleichem Namen | Beim **Registrieren** zählt die Schreibweise: „Die Hacker“ und „die hacker“ werden zwei verschiedene Teams. Umgebende Leerzeichen werden dagegen entfernt, `„ Team A “` wird zu `„Team A“`. Wenn das stört, Team löschen und neu anmelden lassen. |
| Ein Team kommt nicht mehr rein | Passwort vergessen. `/admin` → *Teams* → neues Passwort setzen und dem Team sagen. Das alte wird nicht angezeigt – auch nicht dir. |
| Wer beim Bewerten hilft, landet wieder auf der Anmeldung | Das Passwort für die Bewertung wurde geändert oder der Zugang abgeschaltet – beides meldet ab. Unter *Einstellungen* → *Bewertungszugang* steht, ob er eingerichtet ist; das aktuelle Passwort weitergeben oder ein neues setzen. |
| Ein Team hat die falsche Datei hochgeladen | Normalerweise nichts zu tun: Das Team lädt über **🔁 Korrektur abgeben** die richtige hoch. Hast du das Häkchen **🔁 Teams dürfen ihre Abgabe selbst korrigieren** herausgenommen: `/admin` → *Bewertungen* → **🔓 Erneut abgeben erlauben** – das geht auch, bevor die Abgabe Punkte hat. Die Freigabe gilt **einmal**. Sobald das Team neu abgibt, verschwindet die bisherige Bewertung und die Abgabe landet wieder in der Warteschlange; bis dahin bleibt alles, wie es ist. |
| „Abgaben sind gerade gesperrt“ bei einem Team | Wettbewerb pausiert oder Endzeit überschritten. Die Meldung steht auf der Wettbewerbsseite des Teams. Gehört das Team zu einem anderen als dem aktiven Wettbewerb, landet es gar nicht erst dort, sondern auf der Startseite. |
| Falsches Dateiformat wird abgewiesen | Das erlaubte Format steht pro Aufgabe und in der Meldung, die das Team bekommt. Prüfen, ob es zu dem passt, was die Umgebung tatsächlich exportiert (Scratch: `.sb3`, MakeCode-Calliope: `.hex`, Open Roberta und Snap!: `.xml`, Arduino: `.ino`, App Inventor: `.aia`, Jupyter: `.ipynb`). Open Roberta und Snap! teilen sich `.xml` – aus welcher der beiden Umgebungen die Datei stammt, prüft die Plattform nicht. |
| Ein Team will sich noch registrieren, der Wettbewerb ist beendet oder pausiert | Die Startseite nimmt dann keine neuen Teams an – sonst stünde das Team mit null Punkten in der Rangliste am Beamer. Soll es doch noch mitmachen: **🔓 Wieder öffnen** bzw. **▶ Fortsetzen** auf der Wettbewerbsseite, dann registrieren lassen. |
| Start- oder Anmeldeseite sagt „Gerade ist kein Wettbewerb aktiv“ | Der aktive Wettbewerb wurde gelöscht, und noch ist kein anderer gewählt. `/admin` → auf der Steuerzentrale beim richtigen **✅ Aktivieren**. Danach können sich die Teams wieder registrieren und anmelden. |
| Wettbewerb gelöscht, ein Team sitzt noch davor | Mit dem Wettbewerb sind seine Teams weg. Das Team landet beim nächsten Klick auf der Startseite und registriert sich dort für den nächsten Wettbewerb neu. |
| Nach dem Update auf v1.1.0 waren alle Teams abgemeldet | Einmalig und so gewollt: Anmeldungen aus der Zeit davor galten nicht mehr. Teamname und Passwort blieben, die Teams meldeten sich einmal neu an. Spätere Updates melden niemanden ab. Ein Update spielt man trotzdem besser vor dem Wettbewerb ein als mittendrin. |
| Die Rangliste bewegt sich nicht mehr, obwohl du bewertest | Sie ist eingefroren – das Häkchen **❄️ Rangliste vor Schluss einfrieren** unter *Name & Zeiten* ist gesetzt. Oben auf der Rangliste steht dann *❄️ Eingefroren seit …*, und die Wettbewerbsseite sagt es auch. Den echten Stand zeigt dir die Siegerehrung; **❄️ Rangliste auflösen** zeigt ihn allen. |
| Ein Team bekommt seine Urkunde nicht | Ist der Wettbewerb beendet und die Rangliste eingefroren, gibt es die Urkunde erst nach dem Auflösen – auf ihr steht der Platz. Die Teamseite sagt dann „Eure Urkunde gibt es nach der Siegerehrung“. **❄️ Rangliste auflösen** am Ende der Siegerehrung oder auf der Wettbewerbsseite drücken; der Knopf zur Urkunde erscheint danach von selbst. |
| Auf der Wettbewerbsseite fehlt das Feld für die Durchsage | Durchsagen sind für diesen Wettbewerb aus. Unter *Name & Zeiten* das Häkchen **📢 Durchsagen an die Teams** setzen und speichern. |
| Der Knopf **🧹 Aufräumen** fehlt | Er erscheint erst, wenn der Wettbewerb beendet ist und noch Teams hat. Mitten im Wettbewerb wäre Aufräumen ein Unfall. |
| Versehentlich beendet | **🔓 Wieder öffnen** auf der Wettbewerbsseite. Die Endzeit wird gelöscht und muss neu gesetzt werden. |
| Die Seite ist auf einem Gerät hell, auf einem anderen dunkel | So gewollt: Jedes Gerät folgt seiner eigenen Einstellung (hell oder dunkel im System). Oben in der Leiste wechselt **☀️ Hell** bzw. **🌙 Dunkel**; das merkt sich nur der Browser dieses Geräts. Wer zurück zu dem wechselt, was das Gerät ohnehin zeigt, folgt ihm danach wieder. |
| Teams sehen die geänderte Zeit nicht | Normalerweise kommt sie innerhalb von etwa 15 Sekunden von selbst an; die Teamseiten fragen den Server in diesem Takt nach dem Stand. Bleibt die alte Zeit stehen, hat das Gerät die Verbindung zum Server verloren oder das Tablet hat geschlafen. Einmal neu laden, dann stimmt sie wieder. |
| Ein Gerät erreicht den Server nicht | Zuerst die Adresse auf der Startseite mit der im Terminal vergleichen. Dann Firewall. Dann, ob das Gerät im selben Netz hängt (nicht im Gast-WLAN). |
| „Die Adresse für andere Geräte konnte nicht ermittelt werden“ beim Start, oder auf der Startseite steht `127.0.0.1` | Das Netz hat kein Gateway, die Anwendung kann ihre eigene Adresse nicht erfragen – sie sagt das beim Start. Adresse am Server ablesen (`ip addr` bzw. `ipconfig`) und als `LAN_ADRESSE=192.168.…` in die `.env` eintragen, dann neu starten. |
| Restzeit oder Uhrzeiten liegen weit daneben | Die Uhr des Servers geht falsch – typisch für einen Raspberry Pi ohne Internet, der keine Uhr mit Batterie hat. Plattform beenden, mit `timedatectl` nachsehen, Zeit und Zeitzone setzen (siehe README, [Auf einem Rechner ohne Bildschirm](../README.md#auf-einem-rechner-ohne-bildschirm-etwa-raspberry-pi)), neu starten und die Zeit des Wettbewerbs neu einstellen. |
| Datenbank fehlt oder ist kaputt | Anwendung beenden. `data/challenge.db` zur Seite legen, die passende Sicherung `data/challenge-vor-…​.db` nach `data/challenge.db` umbenennen, neu starten. Die Sicherungen entstehen automatisch vor jeder Strukturänderung – eine regelmäßige Sicherung ersetzen sie nicht. |
| Ein gesicherter Wettbewerb soll zurück | **➕ Neuer Wettbewerb** → unten **Oder aus einer Sicherung einlesen**, die ZIP wählen. Es entsteht ein neuer Wettbewerb, nicht aktiv – auch dann nicht, wenn gerade keiner aktiv ist. Der alte bleibt, wie er ist. Soll er weiterlaufen, ihn aktivieren. Waren die Passwörter mitgesichert, melden sich die Teams wie gewohnt an; sonst haben sie kein Passwort und bekommen nach dem Aktivieren unter **Teams** neue. Für Rangliste und Urkunden braucht es keins. Meldet die Seite, die ZIP sei beschädigt, ist nichts angelegt – eine andere Kopie der Datei nehmen. |
| Hochgeladene Dateien fehlen | Der Download sagt dann „liegt nicht mehr auf dem Server“. Die Abgaben liegen unter `uploads/<Team-Nummer>/`. Aus der letzten Sicherung dieses Verzeichnisses zurückkopieren; die Datenbank kennt nur den Ort innerhalb von `uploads/` und findet sie dort wieder, auch in einem anderen Ordner oder auf einem anderen Rechner. Ohne Sicherung bleiben Punkte und Bewertungen erhalten, nur die Programme sind weg. |
| Etwas ist abgestürzt | In `logs/anwendung.log` steht der Fehler mit Zeitstempel und Adresse der Seite. Diese Datei ist auch nach dem Schließen des Terminals noch da. |
| Wann wurde der Tipp freigegeben? | Steht in `logs/anwendung.log`, mit Zeitstempel und Aufgabe – auch, wenn er wieder verborgen wurde. |
| „Wir haben doch abgegeben!“ | In `logs/anwendung.log` steht jede **abgelehnte** Abgabe mit Team, Aufgabe und Grund – falsche Endung, leere Datei, Datei zu groß, Wettbewerb pausiert oder beendet, schon abgegeben, oder zweimal kurz hintereinander abgeschickt (dann ist eine der beiden angekommen). Eine angekommene Abgabe steht dort nicht, die sieht man unter **Bewertungen**. |
| Nach STRG+C fragt Windows „Batchvorgang abbrechen (J/N)?“ | Die Frage stellt Windows bei jeder `.bat`-Datei. Die Plattform ist da schon beendet – J oder N, beides schließt das Fenster. |
| `--aktualisieren` bricht ab: „In diesem Ordner sind Dateien der Plattform verändert worden“ | Darunter stehen die Dateien. Unter `static/vendor/` steckt nie etwas Eigenes; unter Windows sind es meist nur andere Zeilenenden, etwa nachdem `werkzeuge/vendor_aktualisieren.py` mit einer älteren Fassung gelaufen ist. Dann `git restore static/vendor`. Bei anderen Dateien erst mit `git diff <datei>` nachsehen, was sich geändert hat, Eigenes sichern, dann `git restore <datei>`. Danach die Startdatei noch einmal mit `--aktualisieren` aufrufen. |
| Welche Fassung läuft hier? | Steht beim Start in der Übersicht in der Zeile **Version** und bei jedem Start in `logs/anwendung.log`. „+ 3 Änderungen“ heißt: drei Änderungen nach diesem Release. „unbekannt“ heißt nur, dass weder git noch die `stand.txt` aus dem ZIP es verraten – etwa bei einem von Hand kopierten Ordner. Dann auf GitHub das aktuelle Release als ZIP holen. |
| „Gefunden wurde Python 3.10, die Plattform braucht 3.11“ | Seit der Anhebung auf Python 3.11 reicht das Python von Ubuntu 22.04 und Linux Mint 21 nicht mehr (Mint 22 und Ubuntu 24.04 haben 3.12). Dort `sudo apt install python3.11 python3.11-venv` und dann `python3.11 starter.py` statt der Startdatei, oder den Rechner auf ein neueres System bringen. Unter Windows und macOS das aktuelle Python von python.org installieren. |
| Die Anwendung startet nicht | Meldung lesen: Fehlt `SECRET_KEY` oder `ADMIN_PASSWORD` in der `.env` oder steht dort noch ein Beispielwert, sagt sie das. Die Startdatei ersetzt Beispielwerte selbst. Bricht sie beim Sichern der Datenbank ab, ist meist die Platte voll. |

---

## 📦 Nach dem Wettbewerb

- [ ] **`data/` und `uploads/` sichern**, solange noch alles frisch ist –
      dieselben zwei Verzeichnisse wie am Vortag. In `data/` stecken Punkte
      und Bewertungen, in `uploads/` die Programme der Teams.
- [ ] **Den Wettbewerb als ZIP sichern**, wenn er aufgehoben oder auf einen
      anderen Rechner gebracht werden soll: auf seiner Seite unten
      **💾 Wettbewerb sichern** → **⬇️ Sichern**. In der Datei stecken
      Aufgaben, Teams, Abgaben, Punkte und Feedback. Zwei Häkchen sind
      zunächst aus: **Namen der Teammitglieder** braucht es nur, wenn die
      Urkunden später aus der Sicherung gedruckt werden sollen,
      **Passwörter der Teams** nur, wenn der Wettbewerb auf einem anderen
      Rechner weiterlaufen soll. Die Passwörter stehen nicht im Klartext
      darin, ein schwaches wie „1234“ lässt sich aber zurückraten. Mit Namen
      oder Passwörtern gehört die Datei nicht auf private Geräte oder in eine
      Cloud.
- [ ] **Gut gelaufene Aufgaben exportieren** (Aufgaben-Seite: **⬇️ Alle Aufgaben sichern**, oder das ⬇️ neben einer
      einzelnen Aufgabe) und
      die Datei aufheben. Beim nächsten Mal wieder einlesen – Punkte,
      Dateiformat, Schwierigkeit und Hinweis kommen mit.
- [ ] **Protokolldatei durchsehen**, falls etwas hakte – und die Erkenntnis
      unten unter **💡 Aus der Praxis** eintragen.
- [ ] **Aufräumen**, sobald Urkunden und Nachfragen erledigt sind: auf der
      Seite des beendeten Wettbewerbs **🧹 Aufräumen**. Das löscht alle Teams
      samt Namen und Passwörtern und alle Abgaben mit Dateien, Punkten und
      Feedback, dazu eine noch stehende Durchsage. Wettbewerb, Einstellungen
      und Aufgaben bleiben, beim nächsten Mal ist also alles vorbereitet. Rangliste, Siegerehrung und Urkunden
      dieses Wettbewerbs sind danach leer – wer etwas aufheben will, sichert
      den Wettbewerb vorher als ZIP (siehe oben).
- [ ] **Alte Sicherungskopien löschen**, sobald klar ist, dass nach einem
      Update alles passt: unter *Einstellungen* ganz unten **🧹 Kopien
      löschen**. Die Kopien `challenge-vor-…​.db` in `data/` enthalten alles,
      auch Namen und Passwörter.
- [ ] **Protokolldatei leeren**, sobald keine Nachfrage mehr zu erwarten
      ist: unter *Einstellungen* ganz unten **🧹 Protokoll leeren**. Die Datei
      nennt Teamnamen und bei fehlgeschlagenen Admin-Anmeldungen
      IP-Adressen, auch nach dem Aufräumen oder Löschen des Wettbewerbs.

---

## 💡 Aus der Praxis

### Eine Woche vorher

> Wie viele Aufgaben passen in die zur Verfügung stehende
> Zeit? Welche Punktverteilung hat sich bewährt?
>
> _(hier eintragen, wenn du es weißt)_

### Am Vortag

> Welche Hürde gab es im Schulnetz?
>
> _(hier eintragen)_

### Während des Wettbewerbs

> Ab wann die Rangliste zeigen, und wie viele Minuten vor Schluss
> einfrieren? (Von Anfang an motiviert sie – kurz vor Schluss kann sie
> auch lähmen.)
>
> _(hier eintragen)_

### Wenn etwas klemmt

> Was ist dir tatsächlich passiert, das hier noch fehlt?
>
> _(hier eintragen)_

### Nach dem Wettbewerb

> Was würdest du beim nächsten Mal anders machen?
>
> _(hier eintragen)_
