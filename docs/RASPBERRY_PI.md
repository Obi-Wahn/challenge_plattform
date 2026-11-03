# 🍓 Rechner ohne Bildschirm (etwa Raspberry Pi)

Die Plattform braucht keine Oberfläche und läuft auch auf einem kleinen
Linux-Rechner, der nur per SSH erreichbar ist. Raspberry Pi OS bringt ab
Bookworm ein passendes Python mit (3.11, bei Trixie 3.13). Alles Übrige
steht in der [README](../README.md) und im [Leitfaden](ADMIN_GUIDE.md).

1.  **Holen und einrichten**, per SSH auf dem Rechner, einmal mit Internet.

    *   **Als ZIP:** Auf der
        [Release-Seite](https://github.com/Obi-Wahn/challenge_plattform/releases)
        beim neuesten Release unter *Assets* den Link **Source code (zip)**
        kopieren. Auf dem Rechner holen, entpacken und den Ordner umbenennen
        (hier für 1.25.3, die Nummer steht im Link und im Ordnernamen):
        ```bash
        wget -O plattform.zip https://github.com/Obi-Wahn/challenge_plattform/archive/refs/tags/v1.25.3.zip
        unzip plattform.zip && rm plattform.zip
        mv challenge_plattform-1.25.3 challenge_plattform
        ```
        Fehlt `unzip`: `sudo apt install unzip`. Das ZIP lässt sich auch an
        einem anderen Rechner herunterladen und mit `scp` hinüberkopieren.
    *   **Mit git:**
        ```bash
        git clone https://github.com/Obi-Wahn/challenge_plattform.git
        ```

    Danach in beiden Fällen:
    ```bash
    cd challenge_plattform
    ./start_linux.sh --ohne-browser
    ```
    Diesen Ordnernamen erwartet auch der Dienst weiter unten. Der erste Start
    fragt wie gewohnt das Admin-Passwort ab. Bedient wird die Plattform danach
    vom Browser eines anderen Geräts aus, über die Adresse in der
    Startübersicht.

2.  **Feste Adresse.** Bekommt der Rechner seine Adresse per DHCP, kann sie
    sich ändern – und mit ihr der QR-Code. Die Adresse darum im Router
    reservieren oder am Rechner fest einstellen (unter Raspberry Pi OS mit
    `sudo nmtui`) und als `LAN_ADRESSE=192.168.…` in die `.env` schreiben.

3.  **Uhrzeit prüfen.** Ein Raspberry Pi hat meist keine Uhr mit Batterie.
    Ohne Internet läuft er nach dem Einschalten mit der Zeit weiter, zu der er
    zuletzt lief – und Restzeit, Pause und Zeitstempel richten sich nach
    dieser Uhr. Vor dem Wettbewerb darum `timedatectl` aufrufen: Datum,
    Uhrzeit und Zeitzone (`Europe/Berlin`) müssen stimmen. Sonst von Hand
    setzen, **bevor** die Plattform startet:
    ```bash
    sudo timedatectl set-timezone Europe/Berlin
    sudo date -s "2026-10-05 08:00"
    ```
    Ein Raspberry Pi 5 mit eingesetzter Uhrbatterie oder ein RTC-Modul
    erspart das.

4.  **Weiterlaufen lassen.** Schließt man das SSH-Fenster, endet auch die
    Plattform. Der einfache Weg ist `tmux`. Es läuft **auf dem Rechner mit
    der Plattform**, also auf dem Raspberry Pi, nicht auf dem Gerät, von dem
    aus man sich per SSH verbindet. Dort einmal `sudo apt install tmux`,
    dann in der SSH-Sitzung:
    ```bash
    tmux new -s wettbewerb
    ./start_linux.sh --ohne-browser
    ```
    Mit STRG+B, dann D, löst man sich davon, die Plattform läuft weiter. Nach
    dem nächsten Anmelden holt `tmux attach -t wettbewerb` das Fenster zurück,
    dort beendet STRG+C sie wie gewohnt.

**Optional: als Dienst, der beim Einschalten startet.** Wer den Rechner nur
einstecken will, richtet einen systemd-Dienst ein. Vorher muss der erste
Start aus Schritt 1 durchgelaufen sein. Benutzer und Pfad anpassen, dann als
`/etc/systemd/system/challenge-plattform.service` speichern:

```ini
[Unit]
Description=Challenge-Plattform
After=network-online.target
Wants=network-online.target

[Service]
User=pi
WorkingDirectory=/home/pi/challenge_plattform
ExecStart=/home/pi/challenge_plattform/.venv/bin/python app.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now challenge-plattform   # einschalten und starten
sudo systemctl status challenge-plattform         # läuft er?
sudo systemctl disable --now challenge-plattform  # wieder abschalten
```

Die Uhrzeit aus Schritt 3 gilt dann genauso – der Dienst startet ja schon
beim Einschalten.

**Aktualisieren.** Erst die Plattform beenden, als Dienst mit
`sudo systemctl stop challenge-plattform`, sonst meldet die Startdatei den
Port als belegt.

*   **Als ZIP geholt:** das neue ZIP wie in Schritt 1 mit `wget` holen und
    entpacken (hier 1.25.4), Daten hinüberkopieren und die Ordner tauschen,
    damit der Dienst den neuen findet:
    ```bash
    cd ~
    unzip plattform.zip && rm plattform.zip
    cp -a challenge_plattform/data challenge_plattform/uploads challenge_plattform/.env challenge_plattform-1.25.4/
    mv challenge_plattform challenge_plattform-alt
    mv challenge_plattform-1.25.4 challenge_plattform
    cd challenge_plattform
    ./start_linux.sh --ohne-browser
    ```
    Der erste Start richtet die virtuelle Umgebung neu ein und braucht dafür
    Internet. Läuft alles, den alten Ordner mit
    `rm -rf ~/challenge_plattform-alt` löschen: Darin stehen noch Teamnamen,
    Abgaben, das Protokoll und das Admin-Passwort.
*   **Mit git geholt:** `./start_linux.sh --aktualisieren --ohne-browser`.

Als Dienst danach die Startübersicht abwarten, mit STRG+C beenden und den
Dienst mit `sudo systemctl start challenge-plattform` wieder starten.

**SD-Karte.** Das Protokoll schreibt kaum etwas, der gewöhnliche Betrieb
bleibt darin still (siehe [Protokolldatei](../README.md#-protokolldatei)). Geschrieben
wird vor allem in die Datenbank und in `uploads/`, und beides wird gebraucht.
Eine SD-Karte fällt aber eher aus als eine Festplatte: nach dem Wettbewerb
sichern, wie in der README unter [Daten und Sicherungen](../README.md#-daten-und-sicherungen)
beschrieben. Auf der Karte stehen Teamnamen und Abgaben – ein Rechner, der
danach in der Schublade liegt, wird genauso aufgeräumt wie jeder andere.
