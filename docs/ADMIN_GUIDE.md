# 🧭 Leitfaden für den Wettbewerbstag

Die README erklärt, **wie** die Anwendung installiert wird und **welche**
Funktionen es gibt. Dieser Leitfaden beschreibt den **Ablauf**: was wann zu
tun ist, und was zu tun ist, wenn etwas klemmt.

---

## 📅 Rechtzeitig vorher

1. **Anwendung auf den Stand bringen.** Die Startdatei einmal mit
   `--aktualisieren` aufrufen, also `start_windows.bat --aktualisieren` in
   der Eingabeaufforderung bzw. `./start_linux.sh --aktualisieren`. Wer die
   Plattform als ZIP geholt hat, geht den Weg aus der README unter
   [Aktualisieren](../README.md#aktualisieren) – dort stehen beide Fälle.

   Das braucht Internet – also zu Hause oder am Lehrerrechner, nicht am
   Wettbewerbstag.

   Welche Fassung danach läuft, steht in der Startübersicht in der Zeile
   **Version**, etwa „1.23.1 (Stand 27.10.2026)“. Mit der Nummer des neuesten
   Releases auf GitHub vergleichen.

   Wer am Code arbeitet, lässt danach noch die Tests laufen und sieht nach
   neuen Paketen, siehe [docs/ENTWICKLUNG.md](ENTWICKLUNG.md#-vor-einem-wettbewerb).

2. **Wettbewerb anlegen** unter `/admin` → *Neuer Wettbewerb*: Name,
   Startzeit, Endzeit. Der Name ist der, unter dem die Teams den Wettbewerb
   sehen – „Scratch-Wettbewerb der Klasse 6b“ etwa. Er steht auf der
   Startseite, der Rangliste, den Urkunden und auch im Browsertitel, in der
   Leiste oben und in der Fußzeile, und er bleibt bei diesem Wettbewerb, auch
   wenn später ein anderer läuft; seine Urkunden tragen ihn also auch nächstes
   Jahr noch. Dazu kommen nach Wunsch ein eigener Untertitel und ein
   eigener Gruß, der auf der Startseite unter dem Namen steht (sonst „Schön,
   dass ihr dabei seid!“); leer gelassen gilt jeweils der aus *Einstellungen*. Die Werte dort sind nur die Vorgabe für die
   Zeit, in der noch kein Wettbewerb angelegt oder keiner aktiv ist.

   Ist gerade kein Wettbewerb aktiv, wird der neue es von selbst. Läuft schon
   einer, bleibt der aktiv; der neue wird dann am Wettbewerbstag aktiviert.

   Treffen sich dieselben Teams wieder, etwa in einer AG, hilft beim Anlegen
   das Häkchen **Teams aus „…“ übernehmen**: Die Teams des letzten
   Wettbewerbs kommen mit Passwort mit und melden sich gleich an, ihre Namen
   für die Urkunde warten wieder auf die Freigabe.

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
   Beispiel-Wettbewerb danach löschen.

3. **Aufgaben anlegen oder einlesen.** Fertige Sätze liegen unter
   `beispiele/` (Scratch, Snap!, Calliope) und werden auf der Aufgaben-Seite mit
   **⬆️ Datei einlesen** übernommen; sie bringen auch ihre Schwierigkeit
   mit. Aufgaben aus einem früheren Wettbewerb lassen sich dort ebenso
   einzeln oder als Satz exportieren und wieder einlesen.

4. **Pro Aufgabe festlegen:** Punkte, erlaubtes Dateiformat
   (z. B. `.sb3` für Scratch, `.xml` für Snap!, `.hex` für Calliope), die Schwierigkeit und
   optional einen Hinweis. Der Hinweis bleibt verborgen, bis er
   freigeschaltet wird.

   **Titel möglichst kurz halten**, zwei, drei Wörter wie „Ballon-Jagd“
   oder „Geheimes Passwort“. Über den Spalten der Rangliste steht
   „A1: Titel“, und die Spalten teilen sich die Breite des großen
   Bildschirms (Display, Smartboard oder Beamer): Bei fünfzehn Aufgaben
   bleiben von einem langen Titel nur Wortanfänge. Was die Teams genau tun
   sollen, gehört in den Aufgabentext. Reicht die Nummer, lassen sich die
   Titel unter *Einstellungen* → *Rangliste* abschalten.

   Die Schwierigkeit ist *einfach*, *mittel* oder *schwer*; „keine Angabe“
   ist auch eine Antwort, dann steht bei der Aufgabe nichts. Die Teams sehen
   sie neben den Punkten und finden so schnell etwas Passendes. Beim Sichern
   reist sie in der JSON-Datei mit.

   Die **Reihenfolge** lässt sich in der Aufgabenliste mit ▲ und ▼ ändern –
   je Klick rückt die Aufgabe eine Stelle. In dieser Reihenfolge stehen die
   Aufgaben auf der Seite der Teams (über jeder „Aufgabe 1“, „Aufgabe 2“ …),
   in der Rangliste (A1, A2 …) und in den Sicherungen. Die Nummern sind
   dieselben, im Raum lässt sich also von „Aufgabe 3“ sprechen. Neue und
   eingelesene Aufgaben kommen ans Ende. Am besten vor dem Start sortieren:
   Wer mitten im Wettbewerb umstellt, ändert auch die Nummern in der
   Rangliste – die Punkte bleiben dabei, wo sie hingehören.

5. **Urkunden einstellen** unter *Einstellungen*: Quer- oder Hochformat, der
   Name unter der Unterschriftslinie und die Handschrift. Am besten jetzt
   schon eine Probeurkunde ausdrucken – dann ist klar, ob Drucker und Papier
   mitspielen.

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
- [ ] **`data/` und `uploads/` auf einen USB-Stick kopieren**, beide: in
      `data/` die Datenbank, in `uploads/` die abgegebenen Dateien (siehe
      README, [Daten und Sicherungen](../README.md#-daten-und-sicherungen)).
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
      nicht das Admin-Passwort) und weitergeben. Die Anmeldung läuft wie beim
      Admin über **Jury-Anmeldung** unten auf jeder Seite (die Seite heißt
      „Anmeldung für Admin und Bewertungszugang“), führt aber direkt auf die
      Bewertungsseite, und von dort geht es nirgendwo anders hin. Löschen
      und Freigeben sind dort ausgeblendet. Ohne Passwort gibt es diesen
      Zugang nicht.
- [ ] **Großen Bildschirm testen** mit der Rangliste `/scoreboard`. Die Restzeit steht
      dort oben, dieselbe, die die Teams sehen. Ist der Raum hell und die
      Tabelle blass, oben in der Leiste auf **☀️ Hell** wechseln. Der
      Browser an diesem Bildschirm merkt sich das; die Geräte der Teams
      zeigen weiter, was dort eingestellt ist.

---

## 🏁 Am Wettbewerbstag

### Vor dem Start

1. Server starten: die Startdatei öffnen (`start_windows.bat`,
   `start_macos.command` oder `./start_linux.sh`), oder von Hand
   `python app.py` in der aktivierten Umgebung.
   Im Terminal stehen beide Adressen (lokal und fürs Netzwerk) und der Pfad
   der Protokolldatei. **Das Fenster offen lassen.**

   Auf einem Raspberry Pi vorher mit `timedatectl` die Uhrzeit prüfen, siehe
   [Auf einem Rechner ohne Bildschirm](RASPBERRY_PI.md).
2. Wettbewerb unter `/admin` **aktivieren**: Steht der richtige schon oben in
   der Statuszeile, ist nichts zu tun. Sonst steht er weiter unten unter
   *Weitere Wettbewerbe* – dort **✅ Aktivieren**. „▶ Jetzt starten“ auf einem
   nicht aktiven Wettbewerb startet nur seine Uhr; die Meldung danach sagt,
   dass die Teams ihn erst nach dem Aktivieren sehen.
3. Rangliste `/scoreboard` auf dem großen Bildschirm öffnen. Oben läuft die Zeit, darunter
   füllt sich die Tabelle mit jeder Bewertung.
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
Restzeit. Ein kurzer Hinweis an die Teams schadet trotzdem nicht – eine Uhr,
die plötzlich anders steht, verunsichert sonst.

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
  **🔓 Erneut abgeben erlauben**. Abgaben älterer Wettbewerbe erreicht der
  Zugang nicht, nur die des aktiven. Wer was bewertet hat, merkt sich die
  Plattform nicht. Soll niemand mehr mitbewerten, unter *Einstellungen* ein
  neues Passwort setzen oder **Bewertungszugang abschalten** – wer noch
  angemeldet ist, ist beim nächsten Klick draußen.
- **Scratch-, Snap!- und MakeCode-Abgaben ansehen**: Bei einer `.sb3`, bei
  einer `.xml` aus Snap! und bei einer `.hex` oder `.mkcd` aus MakeCode für
  den Calliope mini zeigt **🧩 Skripte anzeigen** die Skripte als Blöcke, nur
  ohne sie auszuführen. Ob das Projekt tut, was es soll, zeigt erst
  **⬇️ Datei herunterladen** und Öffnen in Scratch, Snap! oder MakeCode.
  Unbekannte Blöcke erscheinen grau mit ihrem englischen Namen, Kommentare
  fehlen. Ein Programm aus Open Roberta, ebenfalls `.xml`, zeigt die Plattform
  nicht als Blöcke, sondern sagt das. Die Teams sehen dieselben Blöcke ihrer
  eigenen Abgabe unter **🧩 Unsere Skripte anzeigen**.
- **MakeCode-Abgaben im Einzelnen**: Die Blöcke stehen in den Farben und mit
  den Texten des deutschen Calliope-Editors da, die Symbole als kleines
  LED-Bild, nur in der Form von Scratch-Blöcken. Teile, die sich im Editor
  mit ⊕ aufklappen lassen, etwa „in einem Intervall von … ms“, erscheinen nur,
  wenn das Team sie aufgeklappt hat. Blöcke aus Erweiterungen wie
  dem MotionKit liest die Plattform aus der Datei selbst; wo eine Erweiterung
  keine deutschen Texte mitbringt, bleiben sie englisch. Eine `.hex` aus
  einem anderen Editor, etwa für Python, enthält keine Blöcke; das sagt die
  Plattform dann. Den Projektnamen und die Beschreibung, die ein Team in
  MakeCode eintippt, zeigt sie nicht an.
- **Durchsage an alle Teams**, etwa „Noch 10 Minuten, bitte speichern“:
  einmal unter *Name & Zeiten* das Häkchen **📢 Durchsagen an die Teams**
  setzen, dann steht auf der Wettbewerbsseite unter den Knöpfen für die Uhr
  ein Feld mit **📢 Senden**. Der Satz erscheint innerhalb von etwa 15 Sekunden oben auf
  jeder Teamseite und über der Rangliste am großen Bildschirm. Es gilt immer nur eine
  Durchsage – eine neue ersetzt die alte, **Entfernen** nimmt sie weg. Ins
  Protokoll kommt nur, dass es eine gab, nicht ihr Text.
- **Korrekturen** machen die Teams selbst: Unter jeder abgegebenen Aufgabe
  steht **🔁 Korrektur abgeben**, die neue Datei ersetzt die alte. War die
  Abgabe schon bewertet, fallen Punkte und Feedback weg, und sie steht wieder
  als offen unter *Bewertungen*. Das geht, solange der Wettbewerb läuft.
  Kommt die Korrektur, während die Abgabe gerade bewertet wird, speichert
  die Plattform die Punkte nicht, sondern meldet die neue Fassung; einmal
  ansehen, dann bewerten.
  Soll jede Korrektur einzeln freigegeben werden, unter *Name & Zeiten* das
  Häkchen **🔁 Teams dürfen ihre Abgabe selbst korrigieren** herausnehmen;
  dann steht unter jeder Abgabe wieder **🔓 Erneut abgeben erlauben**.
- **Hinweis freischalten**, wenn eine Aufgabe zu schwer ist: auf der
  Aufgaben-Seite umschalten. Der Hinweis erscheint bei allen Teams innerhalb
  von etwa 15 Sekunden, ohne dass jemand neu laden muss.
- **Pausieren**, wenn etwas geklärt werden muss: **⏸ Pause** sperrt alle
  Abgaben und hält die Uhr an, **▶ Fortsetzen** gibt sie wieder frei und
  schiebt die Endzeit um die Dauer der Pause nach hinten. Den Teams geht also
  keine Arbeitszeit verloren, und niemand muss nachrechnen. Auf den
  Teamseiten erscheint innerhalb von etwa 15 Sekunden von selbst ein Kasten
  *⏸ Kurze Pause*, die Rangliste zeigt dieselbe stillstehende Zeit. Beim
  Fortsetzen verschwindet der Kasten von selbst wieder. Die Aufgaben bleiben in der Pause
  absichtlich lesbar – nachdenken und nachlesen darf ein Team, nur abgeben
  nicht.
- **Rangliste** `/scoreboard` aktualisiert sich alle 30 Sekunden von selbst und
  trägt die Restzeit oben — sie ist die Seite für den großen Bildschirm, den
  ganzen Wettbewerb über.
- **Rangliste einfrieren**, wenn es am Ende spannend bleiben soll: unter
  *Name & Zeiten* das Häkchen **❄️ Rangliste vor Schluss einfrieren** setzen
  und die Minuten vor Schluss eintragen (vorgeschlagen sind 15). Ab dann
  zeigt die Rangliste nur noch, was bis dahin abgegeben war, mit dem Hinweis
  *❄️ Eingefroren seit …*. Bewertet wird weiter wie immer; eine Abgabe von
  davor zählt auch, wenn sie erst danach bewertet wird. Korrigiert ein Team
  danach noch eine Abgabe, behält die Rangliste deren alte Punkte bis zum
  Auflösen; die neue Fassung wird bewertet wie jede andere. Jedes Team
  sieht seine eigenen Punkte auf seiner Seite weiter aktuell – nur den
  Vergleich mit den anderen nicht mehr. Eine Pause vor dem Einfrieren
  schiebt es mit dem Ende nach hinten, eine Pause danach nicht.

### Schluss und Siegerehrung

1. **🏁 Wettbewerb beenden** auf der Wettbewerbsseite. Das setzt die Endzeit
   auf jetzt; Abgaben sind gesperrt. Gelöscht wird nichts.
2. **Letzte Abgaben zu Ende bewerten** – das geht nach dem Beenden weiter.
3. **Siegerehrung** `/siegerehrung` auf dem großen Bildschirm öffnen. Hängt
   dort schon die Rangliste, ist nichts zu tun: Spätestens 30 Sekunden nach
   dem Ende wechselt sie von selbst zur Siegerehrung, sobald die erste Abgabe
   Punkte hat; wer die Rangliste danach aufruft, landet ebenfalls dort. Bis
   der erste Platz verkündet ist, holt sich die Siegerehrung alle 30 Sekunden
   den neuesten Stand, es lässt sich also in Ruhe zu Ende bewerten.

   **🥁 Nächsten Platz verkünden** (oder die Leertaste) stellt erst den
   dritten, dann den zweiten und zuletzt den ersten Platz auf seine Stufe.
   Gleichstände teilen sich einen Platz, niemand fällt durch eine
   willkürliche Reihung heraus. Die ganze Rangliste gibt es danach über
   **Vollständige Rangliste ansehen** unter dem Podest.

   **Mit eingefrorener Rangliste** zeigt die Siegerehrung den echten Stand
   nur der angemeldeten Lehrkraft; wer die Adresse am Handy aufruft,
   sieht bloß *❄️ Die Rangliste ist eingefroren*. Darum wechselt die
   Rangliste am großen Bildschirm nur zum Podest, wenn dort jemand als
   Admin angemeldet ist. Nach dem letzten Platz **❄️ Rangliste auflösen und ansehen**
   drücken (der Knopf steht auch auf der Wettbewerbsseite), dann sehen alle
   wieder alles.
4. **Urkunden**: als Sammel-PDF über `/admin/urkunden.pdf` oder einzeln.
   Die Teams können ihre eigene Urkunde nach dem Beenden selbst
   herunterladen – bei eingefrorener Rangliste erst nach dem Auflösen, denn
   auf der Urkunde steht der Platz.
   Die Schrift im PDF kennt nicht jedes Zeichen: Buchstaben mit fremden
   Akzenten verlieren ihn (aus „Şükrü Yılmaz“ wird „Sükrü Yilmaz“), Emoji
   und andere Schriften fallen weg. Die Seite *Urkunden* nennt dann über den
   Urkunden jeden betroffenen Namen und wie er im PDF steht. **🖨️ Drucken**
   auf derselben Seite druckt alles wie eingegeben.
5. **Eine Urkunde nachreichen**, wenn jemand gefehlt hat: Auf der
   Steuerzentrale unten *Beendet* aufklappen, beim gesuchten Wettbewerb
   **Öffnen →**, dort die Urkunden-Kachel. Das geht auch dann noch, wenn
   längst ein anderer Wettbewerb aktiv ist. Punkte, Namen, der Name des
   Wettbewerbs und das Datum sind die von damals: Auf jeder Urkunde steht der
   Tag, an dem der Wettbewerb endete.

---

## 🔧 Wenn etwas klemmt

| Symptom | Ursache und Abhilfe |
|---|---|
| Team tippt seinen Namen anders geschrieben | Beim **Anmelden** ist das in Ordnung: „die pixelpiraten“ findet „Die Pixelpiraten“, solange es nur ein Team dieses Namens gibt. Nur wenn zwei Teams nebeneinander existieren, die sich allein in der Schreibweise unterscheiden, muss die Schreibweise stimmen. |
| Zwei Teams mit fast gleichem Namen | Beim **Registrieren** zählt die Schreibweise: „Die Hacker“ und „die hacker“ werden zwei verschiedene Teams. Umgebende Leerzeichen werden dagegen entfernt, `„ Team A “` wird zu `„Team A“`. Wenn das stört, Team löschen und neu registrieren lassen. |
| Ein Team kommt nicht mehr rein | Passwort vergessen. `/admin` → *Teams* → neues Passwort setzen und dem Team sagen. Das alte zeigt die Plattform niemandem an, auch nicht dem Admin. |
| Wer beim Bewerten hilft, landet wieder auf der Anmeldung | Das Passwort für die Bewertung wurde geändert oder der Zugang abgeschaltet – beides meldet ab. Unter *Einstellungen* → *Bewertungszugang* steht, ob er eingerichtet ist; das aktuelle Passwort weitergeben oder ein neues setzen. |
| Ein Team hat die falsche Datei hochgeladen | Normalerweise nichts zu tun: Das Team lädt über **🔁 Korrektur abgeben** die richtige hoch. Ist das Häkchen **🔁 Teams dürfen ihre Abgabe selbst korrigieren** herausgenommen: `/admin` → *Bewertungen* → **🔓 Erneut abgeben erlauben** – das geht auch, bevor die Abgabe Punkte hat. Die Freigabe gilt **einmal**. Sobald das Team neu abgibt, verschwindet die bisherige Bewertung und die Abgabe landet wieder in der Warteschlange; bis dahin bleibt alles, wie es ist. |
| „Abgaben sind gerade gesperrt“ bei einem Team | Wettbewerb pausiert oder Endzeit überschritten. Die Meldung steht auf der Wettbewerbsseite des Teams. Gehört das Team zu einem anderen als dem aktiven Wettbewerb, landet es gar nicht erst dort, sondern auf der Startseite. |
| Falsches Dateiformat wird abgewiesen | Das erlaubte Format steht pro Aufgabe und in der Meldung, die das Team bekommt. Prüfen, ob es zu dem passt, was die Umgebung tatsächlich exportiert (Scratch: `.sb3`, MakeCode-Calliope: `.hex`, Open Roberta und Snap!: `.xml`, Arduino: `.ino`, App Inventor: `.aia`, Jupyter: `.ipynb`). Open Roberta und Snap! teilen sich `.xml` – aus welcher der beiden Umgebungen die Datei stammt, prüft die Plattform beim Abgeben nicht; erst **🧩 Skripte anzeigen** merkt es. |
| Ein Team will sich noch registrieren, der Wettbewerb ist beendet oder pausiert | Die Startseite nimmt dann keine neuen Teams an – sonst stünde das Team mit null Punkten in der Rangliste am großen Bildschirm. Soll es doch noch mitmachen: **🔓 Wieder öffnen** bzw. **▶ Fortsetzen** auf der Wettbewerbsseite, dann registrieren lassen. |
| Start- oder Anmeldeseite sagt „Gerade ist kein Wettbewerb aktiv“ | Der aktive Wettbewerb wurde gelöscht, und noch ist kein anderer gewählt. `/admin` → auf der Steuerzentrale beim richtigen **✅ Aktivieren**. Danach können sich die Teams wieder registrieren und anmelden. |
| Wettbewerb gelöscht, ein Team sitzt noch davor | Mit dem Wettbewerb sind seine Teams weg. Das Team landet beim nächsten Klick auf der Startseite und registriert sich dort für den nächsten Wettbewerb neu. |
| Nach dem Start sind alle Teams abgemeldet | Die Startdatei hat einen neuen `SECRET_KEY` gewürfelt, weil in der `.env` noch ein Beispielwert stand oder der Schlüssel zu kurz war; die Startübersicht sagt das. Einmalig: Teamname und Passwort bleiben, die Teams melden sich neu an. Ein Update spielt man darum besser vor dem Wettbewerb ein als mittendrin. |
| Die Rangliste bewegt sich nicht mehr, obwohl bewertet wird | Sie ist eingefroren – das Häkchen **❄️ Rangliste vor Schluss einfrieren** unter *Name & Zeiten* ist gesetzt. Oben auf der Rangliste steht dann *❄️ Eingefroren seit …*, und die Wettbewerbsseite sagt es auch. Den echten Stand zeigt der Lehrkraft die Siegerehrung; **❄️ Rangliste auflösen** zeigt ihn allen. |
| Ein Team bekommt seine Urkunde nicht | Ist der Wettbewerb beendet und die Rangliste eingefroren, gibt es die Urkunde erst nach dem Auflösen – auf ihr steht der Platz. Die Teamseite sagt dann „Eure Urkunde gibt es nach der Siegerehrung“. **❄️ Rangliste auflösen** am Ende der Siegerehrung oder auf der Wettbewerbsseite drücken; der Knopf zur Urkunde erscheint danach von selbst. |
| Auf der Wettbewerbsseite fehlt das Feld für die Durchsage | Durchsagen sind für diesen Wettbewerb aus. Unter *Name & Zeiten* das Häkchen **📢 Durchsagen an die Teams** setzen und speichern. |
| Der Knopf **🧹 Aufräumen** fehlt | Er erscheint erst, wenn der Wettbewerb beendet ist und noch Teams hat. Mitten im Wettbewerb wäre Aufräumen ein Unfall. |
| Versehentlich beendet | **🔓 Wieder öffnen** auf der Wettbewerbsseite. Die Endzeit wird gelöscht und muss neu gesetzt werden. |
| Die Seite ist auf einem Gerät hell, auf einem anderen dunkel | So gewollt: Jedes Gerät folgt seiner eigenen Einstellung (hell oder dunkel im System). Oben in der Leiste wechselt **☀️ Hell** bzw. **🌙 Dunkel**; das merkt sich nur der Browser dieses Geräts. Wer zurück zu dem wechselt, was das Gerät ohnehin zeigt, folgt ihm danach wieder. |
| Teams sehen die geänderte Zeit nicht | Normalerweise kommt sie innerhalb von etwa 15 Sekunden von selbst an; die Teamseiten fragen den Server in diesem Takt nach dem Stand. Bleibt die alte Zeit stehen, hat das Gerät die Verbindung zum Server verloren oder das Tablet hat geschlafen. Einmal neu laden, dann stimmt sie wieder. |
| Ein Gerät erreicht den Server nicht | Zuerst die Adresse auf der Startseite mit der im Terminal vergleichen. Dann Firewall. Dann, ob das Gerät im selben Netz hängt (nicht im Gast-WLAN). |
| „Die Adresse für andere Geräte konnte nicht ermittelt werden“ beim Start, oder auf der Startseite steht `127.0.0.1` | Das Netz hat kein Gateway, die Anwendung kann ihre eigene Adresse nicht erfragen – sie sagt das beim Start. Adresse am Server ablesen (`ip addr` bzw. `ipconfig`) und als `LAN_ADRESSE=192.168.…` in die `.env` eintragen, dann neu starten. |
| Restzeit oder Uhrzeiten liegen weit daneben | Die Uhr des Servers geht falsch – typisch für einen Raspberry Pi ohne Internet, der keine Uhr mit Batterie hat. Plattform beenden, mit `timedatectl` nachsehen, Zeit und Zeitzone setzen (siehe [Rechner ohne Bildschirm](RASPBERRY_PI.md)), neu starten und die Zeit des Wettbewerbs neu einstellen. |
| Datenbank fehlt oder ist kaputt | Anwendung beenden. `data/challenge.db` zur Seite legen, die passende Sicherung `data/challenge-vor-…​.db` nach `data/challenge.db` umbenennen, neu starten. Die Sicherungen entstehen automatisch vor jeder Strukturänderung – eine regelmäßige Sicherung ersetzen sie nicht. |
| Ein gesicherter Wettbewerb soll zurück | **➕ Neuer Wettbewerb** → unten **Oder aus einer Sicherung einlesen**, die ZIP wählen. Es entsteht ein neuer Wettbewerb, nicht aktiv – auch dann nicht, wenn gerade keiner aktiv ist. Der alte bleibt, wie er ist. Soll er weiterlaufen, ihn aktivieren. Waren die Passwörter mitgesichert, melden sich die Teams wie gewohnt an; sonst haben sie kein Passwort und bekommen nach dem Aktivieren unter **Teams** neue. Für Rangliste und Urkunden braucht es keins. Meldet die Seite, die ZIP sei beschädigt, ist nichts angelegt – eine andere Kopie der Datei nehmen. |
| Hochgeladene Dateien fehlen | Der Download sagt dann „liegt nicht mehr auf dem Server“. Die Abgaben liegen unter `uploads/<Team-Nummer>/`. Aus der letzten Sicherung dieses Verzeichnisses zurückkopieren; die Datenbank kennt nur den Ort innerhalb von `uploads/` und findet sie dort wieder, auch in einem anderen Ordner oder auf einem anderen Rechner. Ohne Sicherung bleiben Punkte und Bewertungen erhalten, nur die Programme sind weg. |
| Etwas ist abgestürzt | In `logs/anwendung.log` steht der Fehler mit Zeitstempel und Adresse der Seite. Diese Datei ist auch nach dem Schließen des Terminals noch da. |
| Wann wurde der Hinweis freigeschaltet? | Steht in `logs/anwendung.log` als „Tipp freigeschaltet“, mit Zeitstempel und Aufgabe – auch, wenn er wieder verborgen wurde. |
| „Wir haben doch abgegeben!“ | In `logs/anwendung.log` steht jede **abgelehnte** Abgabe mit Team, Aufgabe und Grund – falsche Endung, leere Datei, Datei zu groß, Wettbewerb pausiert oder beendet, schon abgegeben, oder zweimal kurz hintereinander abgeschickt (dann ist eine der beiden angekommen). Eine angekommene Abgabe steht dort nicht, die sieht man unter **Bewertungen**. |
| Im Terminal steht „WARNING … Task queue depth is 1“ | Harmlos: Mehrere Geräte haben im selben Augenblick angefragt, und eine Anfrage hat kurz gewartet. Das passiert, wenn viele Teams zugleich abgeben oder die Seite laden. Erst wenn die Zahl dauerhaft wächst und Seiten spürbar langsam werden, ist der Rechner zu schwach. |
| Nach STRG+C fragt Windows „Batchvorgang abbrechen (J/N)?“ | Die Frage stellt Windows bei jeder `.bat`-Datei. Die Plattform ist da schon beendet – J oder N, beides schließt das Fenster. |
| `--aktualisieren` bricht ab: „In diesem Ordner sind Dateien der Plattform verändert worden“ | Darunter stehen die Dateien. Unter `static/vendor/` steckt nie etwas Eigenes; unter Windows sind es meist nur andere Zeilenenden, etwa nachdem `werkzeuge/vendor_aktualisieren.py` mit einer älteren Fassung gelaufen ist. Dann `git restore static/vendor`. Bei anderen Dateien erst mit `git diff <datei>` nachsehen, was sich geändert hat, Eigenes sichern, dann `git restore <datei>`. Danach die Startdatei noch einmal mit `--aktualisieren` aufrufen. |
| Welche Fassung läuft hier? | Steht beim Start in der Übersicht in der Zeile **Version** und bei jedem Start in `logs/anwendung.log`. „+ 3 Änderungen“ heißt: drei Änderungen nach diesem Release. „unbekannt“ heißt nur, dass weder git noch die `stand.txt` aus dem ZIP es verraten – etwa bei einem von Hand kopierten Ordner. Dann auf GitHub das aktuelle Release als ZIP holen. |
| „Gefunden wurde Python 3.10, die Plattform braucht 3.11 oder neuer.“ | Seit der Anhebung auf Python 3.11 reicht das Python von Ubuntu 22.04 und Linux Mint 21 nicht mehr (Mint 22 und Ubuntu 24.04 haben 3.12). Dort `sudo apt install python3.11 python3.11-venv` und dann `python3.11 starter.py` statt der Startdatei, oder den Rechner auf ein neueres System bringen. Unter Windows und macOS das aktuelle Python von python.org installieren. |
| Die Anwendung startet nicht | Meldung lesen: Fehlt `SECRET_KEY` oder `ADMIN_PASSWORD` in der `.env` oder steht dort noch ein Beispielwert, sagt sie das. Die Startdatei ersetzt Beispielwerte selbst. Bricht sie beim Sichern der Datenbank ab, ist meist die Platte voll. |

---

## 📦 Nach dem Wettbewerb

- [ ] **`data/` und `uploads/` sichern**, solange noch alles frisch ist –
      dieselben zwei Verzeichnisse wie am Vortag. In `data/` stecken Punkte
      und Bewertungen, in `uploads/` die Programme der Teams.
- [ ] **Den Wettbewerb als ZIP sichern**, wenn er aufgehoben oder auf einen
      anderen Rechner gebracht werden soll: auf seiner Seite unten
      **💾 Wettbewerb sichern** → **⬇️ Sichern**. Die Häkchen für Namen und
      Passwörter nur setzen, wenn es nötig ist; was sie bedeuten, steht in der
      README unter [Einen einzelnen Wettbewerb sichern](../README.md#einen-einzelnen-wettbewerb-sichern).
      Mit Namen oder Passwörtern gehört die Datei nicht auf private Geräte
      oder in eine Cloud.
- [ ] **Gut gelaufene Aufgaben exportieren** (Aufgaben-Seite:
      **⬇️ Alle Aufgaben sichern**, oder das ⬇️ neben einer einzelnen
      Aufgabe) und die Datei aufheben. Beim nächsten Mal wieder einlesen – Punkte,
      Dateiformat, Schwierigkeit und Hinweis kommen mit.
- [ ] **Protokolldatei durchsehen**, falls etwas hakte.
- [ ] **Aufräumen**, sobald Urkunden und Nachfragen erledigt sind: auf der
      Seite des beendeten Wettbewerbs **🧹 Aufräumen**. Das löscht alle Teams
      samt Namen und Passwörtern und alle Abgaben mit Dateien, Punkten und
      Feedback, dazu eine noch stehende Durchsage. Wettbewerb, Einstellungen
      und Aufgaben bleiben, beim nächsten Mal ist also alles vorbereitet.
      Rangliste, Siegerehrung und Urkunden dieses Wettbewerbs sind danach leer – wer etwas aufheben will, sichert
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

## 💬 Rückmeldung aus der Praxis

Erfahrungen aus dem Einsatz mit Klassen und AGs sind sehr willkommen: was gut
lief, was gehakt hat, wie viele Aufgaben in die Zeit gepasst haben. Am
einfachsten als [Issue auf GitHub](https://github.com/Obi-Wahn/challenge_plattform/issues),
ohne Namen von Schülerinnen und Schülern und ohne Auszüge aus der
Protokolldatei, denn dort stehen Teamnamen.
