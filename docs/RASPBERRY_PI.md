# 🍓 Rechner ohne Bildschirm (etwa Raspberry Pi)

Die Plattform braucht keine Oberfläche und läuft auch auf einem kleinen
Linux-Rechner, der nur per SSH erreichbar ist. Raspberry Pi OS bringt ab
Bookworm ein passendes Python mit (3.11, bei Trixie 3.13). Alles Übrige
steht in der [README](../README.md) und im [Leitfaden](ADMIN_GUIDE.md).

1.  **Holen und einrichten**, per SSH auf dem Rechner, einmal mit Internet:
    ```bash
    git clone https://github.com/Obi-Wahn/challenge_plattform.git
    cd challenge_plattform
    ./start_linux.sh --ohne-browser
    ```
    Wer das ZIP nimmt, kopiert es vorher hinüber (etwa mit `scp`) und
    entpackt es dort mit `unzip`. Der erste Start fragt wie gewohnt das
    Admin-Passwort ab. Bedient wird die Plattform danach vom Browser eines
    anderen Geräts aus, über die Adresse in der Startübersicht.

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
beim Einschalten. Zum **Aktualisieren** den Dienst mit
`sudo systemctl stop challenge-plattform` anhalten, sonst meldet die
Startdatei den Port als belegt. Dann `./start_linux.sh --aktualisieren
--ohne-browser`, nach der Startübersicht mit STRG+C beenden und den Dienst
mit `sudo systemctl start challenge-plattform` wieder starten.

**SD-Karte.** Das Protokoll schreibt kaum etwas, der gewöhnliche Betrieb
bleibt darin still (siehe [Protokolldatei](../README.md#-protokolldatei)). Geschrieben
wird vor allem in die Datenbank und in `uploads/`, und beides wird gebraucht.
Eine SD-Karte fällt aber eher aus als eine Festplatte: nach dem Wettbewerb
sichern, wie in der README unter [Daten und Sicherungen](../README.md#-daten-und-sicherungen)
beschrieben. Auf der Karte stehen Teamnamen und Abgaben – ein Rechner, der
danach in der Schublade liegt, wird genauso aufgeräumt wie jeder andere.
