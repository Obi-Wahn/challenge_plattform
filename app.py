import sys

# Markdown (die Aufgabentexte) setzt seit 3.11 Python 3.11 voraus, und
# Python 3.10 bekommt ab Oktober 2026 keine Sicherheitskorrekturen mehr. Ohne
# diese Prüfung endet ein Start unter einer älteren Fassung in einem
# ImportError, der nicht verrät, woran es wirklich liegt.
if sys.version_info < (3, 11):
    raise SystemExit(
        "Python 3.11 oder neuer wird gebraucht, gefunden: "
        f"{sys.version_info.major}.{sys.version_info.minor}.\n"
        "Die Aufgabentexte (Markdown) laufen unter älteren Fassungen nicht."
    )

import functools
import logging
import os
import re
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, session
from markupsafe import Markup, escape
import markdown
from config import Config, MIN_SCHLUESSEL, schluessel_zu_kurz
from extensions import db, csrf, limiter
from models import MAX_ABGABE_BYTES
from wettbewerb_sicherung import MAX_ZIP_BYTES
from network import FESTE_ADRESSE, lan_adresse, server_port
from protokoll import ereignis
# Name des Handlers, damit ein zweiter Aufruf von create_app() - in den
# Tests kommt das vor - nicht ein zweites Mal in dieselbe Datei schreibt.
# Er steht in datenschutz.py, weil „Protokolldatei leeren“ den Handler
# darüber wiederfindet.
from datenschutz import LOG_HANDLER_NAME
from migrationen import run_startup_migrations
import stand
from blueprints.auth import auth_bp
from blueprints.public import public_bp
from blueprints.challenge import challenge_bp
from blueprints.admin import admin_bp

# Registriert die Haken, die hochgeladene Dateien mit ihrer Abgabe löschen.
import uploads # noqa: F401

# Verweise, die nicht ins Web zeigen. Markdown erzeugt aus [Text](ziel) ein
# href, und "ziel" kommt aus dem Aufgabentext - javascript: gehoert da nicht
# hinein. Erlaubt bleiben http, https, mailto, Sprungmarken und Pfade.
UNSICHERE_ZIELE = re.compile(
    r'(href|src)="(?!https?:|mailto:|#|/)[^"]*"', re.IGNORECASE
)

# Der erste Absatz einer Aufgabe sagt in einem Satz, worum es geht - er liest
# sich wie ein Untertitel. Punkte und Schwierigkeit stehen auf der
# Wettbewerbsseite dahinter, also vor dem ausfuehrlichen Teil.
ERSTER_ABSATZ = re.compile(r"\s*<p>.*?</p>", re.DOTALL)

# Was auf einer Fehlerseite steht, je Fehlerart: ein Zeichen, eine
# Überschrift und ein Satz, der sagt, was zu tun ist.
#
# Ohne diese Seiten zeigt der Webserver seine eigene: englisch, ohne
# Erklärung und ohne Weg zurück. Das trifft genau die Momente, in denen im
# Wettbewerb jemand die Hand hebt - die falsche Dateiart, die zu große Datei,
# der fünfte Fehlversuch am Admin-Passwort.
FEHLERSEITEN = {
    400: ("🤔", "Damit konnte der Server nichts anfangen",
          "Die Anfrage kam unvollständig an. Am einfachsten ist es, die Seite "
          "neu zu laden und es noch einmal zu versuchen."),
    403: ("🔒", "Das geht gerade nicht",
          "Entweder ist die Anmeldung abgelaufen, oder der Wettbewerb nimmt "
          "gerade nichts mehr entgegen. Auf der Startseite geht es weiter."),
    404: ("🧭", "Diese Seite gibt es nicht",
          "Vielleicht hat sich in der Adresse ein Tippfehler versteckt."),
    413: ("📦", "Die Datei ist zu groß",
          f"Bis zu {MAX_ABGABE_BYTES // (1024 * 1024)} MB nimmt der Server an. Bei einem Scratch-Projekt helfen "
          "meist kleinere Klänge oder Bilder - fragt sonst die Lehrkraft."),
    429: ("⏱️", "Zu viele Versuche",
          "Zum Schutz vor Rateversuchen ist die Anmeldung kurz gesperrt. "
          "Wartet eine Minute, dann geht es wieder."),
    500: ("🛠️", "Da ist etwas schiefgegangen",
          "Der Fehler steht mit Zeitstempel in der Protokolldatei "
          "logs/anwendung.log. Ein Neuladen der Seite hilft oft schon."),
}


@functools.lru_cache(maxsize=512)
def markdown_html(text):
    """Ein Aufgabentext als HTML, siehe render_markdown in create_app().

    Zwischengespeichert, weil derselbe Text oft vielfach gebraucht wird: Die
    Bewertungsseite zeigt zu jeder Abgabe die Aufgabenbeschreibung, bei 40
    Teams und 10 Aufgaben also 370-mal dieselben zehn Texte - und lädt nach
    jeder Bewertung neu. Das Umwandeln kostete dort über 80 % der Zeit (bis
    zu 590 ms statt 50 ms). Gleicher Text ergibt gleiches HTML, veralten kann
    hier also nichts; ein geänderter Text ist ein neuer Schlüssel.
    """
    html = markdown.markdown(str(escape(text)))
    return Markup(UNSICHERE_ZIELE.sub(r'\1="#"', html))


def configure_logging(app):
    """Schreibt Fehler und wichtige Ereignisse in eine Datei.

    Ohne das stünde ein Traceback nur im Terminal: Wer das Fenster schließt
    oder den Server als Dienst laufen lässt, hat nach einer Störung nichts
    mehr in der Hand - und am Wettbewerbstag ist genau dann keine Zeit, den
    Fehler noch einmal herbeizuführen.

    Die Datei rotiert bei 1 MB und behält fünf ältere Stände, damit sie nicht
    unbegrenzt wächst.
    """
    if any(h.name == LOG_HANDLER_NAME for h in app.logger.handlers):
        return

    log_dir = app.config["LOG_DIR"]
    os.makedirs(log_dir, exist_ok=True)

    handler = RotatingFileHandler(
        os.path.join(log_dir, "anwendung.log"),
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    handler.name = LOG_HANDLER_NAME
    handler.setLevel(logging.INFO)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s  %(levelname)-8s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)

    # waitress meldet über einen eigenen Logger, was die Anwendung selbst
    # nicht mehr abfangen konnte. Auch das gehört in dieselbe Datei.
    waitress_log = logging.getLogger("waitress")
    if not any(h.name == LOG_HANDLER_NAME for h in waitress_log.handlers):
        waitress_log.addHandler(handler)
        waitress_log.setLevel(logging.INFO)


def einmal_im_terminal(app):
    """Verhindert, dass jede Meldung im Terminal doppelt steht.

    waitress ruft beim Start ``logging.basicConfig()`` auf und hängt damit
    eine zweite Ausgabe ans Terminal. Die Meldungen der Anwendung stehen über
    Flasks eigene Ausgabe schon dort - mit Zeitstempel - und kämen über die
    zweite noch einmal, ohne. Die Protokolldatei betrifft das nicht, dort
    stand jede Zeile immer nur einmal.

    Nur für den echten Start: Die Tests lesen die Meldungen über ``caplog``,
    und das hört am obersten Logger mit.
    """
    app.logger.propagate = False


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    configure_logging(app)

    # Eine Sicherung eines ganzen Wettbewerbs ist größer als eine einzelne
    # Abgabe. Die höhere Grenze muss vor der CSRF-Prüfung stehen: Die liest
    # das Formular als Erstes und bräche sonst schon bei 16 MB ab. Sie gilt
    # nur für die angemeldete Lehrkraft - ohne Anmeldung bleibt es bei 16 MB.
    @app.before_request
    def grenze_fuer_sicherung():
        if request.endpoint == "admin.challenge_restore" and session.get("is_admin"):
            request.max_content_length = MAX_ZIP_BYTES

    # Initialize Extensions
    db.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(challenge_bp)
    app.register_blueprint(admin_bp)

    # Custom Filters
    @app.template_filter('markdown')
    def render_markdown(text):
        """Aufgabentext als Markdown, ohne rohes HTML durchzulassen.

        Das Ergebnis wird als vertrauenswürdiges HTML ausgegeben, darf also
        nichts enthalten, was der Aufgabentext eingeschleust hat. Solange die
        Lehrkraft jede Aufgabe selbst tippt, wäre das unkritisch - seit dem
        Aufgaben-Import kann der Text aber aus einer Datei stammen, die
        jemand anderes geschrieben hat. Und gerendert wird er unter anderem
        in der Bewertungsansicht, also in der Sitzung des Admins.

        Zwei Dinge werden deshalb entschärft: rohes HTML im Text (es wird
        vorher escaped und erscheint als Text, wie es dasteht) und Verweise
        auf andere Ziele als das Web (javascript:, data: und Ähnliches).
        Die Markdown-Auszeichnung selbst - Fettdruck, Listen, Code, Links
        ins Web - funktioniert unverändert.
        """
        if not text:
            return ""
        return markdown_html(str(text))

    @app.template_filter('aufgabentext')
    def split_task_description(text):
        """Der Aufgabentext in zwei Teilen: Einleitung und der Rest.

        Dazwischen stehen auf der Wettbewerbsseite Punkte und Schwierigkeit.
        Die Einleitung ist der erste Absatz - ein Satz, der sagt, worum es
        geht. Faengt der Text ohne Absatz an, etwa mit einer Liste oder einer
        Ueberschrift, bleibt die Einleitung leer und alles steht im Rest; die
        Angaben stehen dann direkt unter dem Titel.
        """
        html = render_markdown(text)
        if not html:
            return {"einleitung": Markup(""), "rest": Markup("")}

        treffer = ERSTER_ABSATZ.match(html)
        if not treffer:
            return {"einleitung": Markup(""), "rest": html}

        return {
            "einleitung": Markup(treffer.group(0)),
            "rest": Markup(html[treffer.end():]),
        }

    # Site branding (name, tagline) is admin-editable, stored in the DB,
    # and injected into every template instead of being hardcoded.
    #
    # "event" ist Name und Untertitel des Wettbewerbs, den eine Seite meint.
    # Eine Seite, die einen anderen als den aktiven Wettbewerb zeigt, reicht
    # ihr eigenes "event" an render_template weiter; das gewinnt gegen den
    # Wert von hier. "site_event" ist dasselbe für den aktiven Wettbewerb und
    # bleibt davon unberührt: Browsertitel, Leiste oben und Fußzeile sollen
    # sagen, was gerade läuft, auch auf einer Seite über einen älteren
    # Wettbewerb. Läuft keiner, gelten die Standardwerte aus den
    # Einstellungen. "site_settings" gibt es weiter für alles andere, was dort
    # eingestellt wird.
    @app.context_processor
    def inject_site_settings():
        """Was jede Seite über Einstellungen und Wettbewerb wissen muss.

        Ein Kontextprozessor für alles, damit jede Seite den aktiven
        Wettbewerb nur einmal abfragt. Die obere Leiste steht in base.html
        und kennt von sich aus weder den Wettbewerb noch das angemeldete
        Team. Sie wächst um höchstens einen Eintrag: die Urkunde, sobald der
        Wettbewerb beendet und die Rangliste nicht mehr eingefroren ist.
        """
        from models import Challenge, Settings, event_branding
        from sitzung import angemeldetes_team

        challenge = Challenge.current()
        branding = event_branding(challenge)
        # Das Team kommt aus der Datenbank, nicht aus der Sitzung: Nach dem
        # Löschen des Wettbewerbs steht der Name noch im Cookie, das Team
        # gibt es aber nicht mehr. Die Leiste zeigte es sonst weiter als
        # angemeldet an, samt "Abmelden".
        team = angemeldetes_team(challenge)

        return {
            "site_settings": Settings.get(),
            "event": branding,
            "site_event": branding,
            "nav_team": team.name if team else None,
            "nav_urkunde": bool(challenge and challenge.certificates_open),
        }

    register_error_handlers(app)

    return app


def register_error_handlers(app):
    """Zeigt für jeden Fehler eine Seite der Anwendung statt der des Servers."""
    from flask import render_template, request

    def fehlerseite(code, erklaerung=None):
        zeichen, ueberschrift, standard = FEHLERSEITEN[code]
        erklaerung = erklaerung or standard

        # Ein angemeldetes Team kommt mit einem Klick zurück an die Arbeit,
        # statt sich über die Startseite neu durchklicken zu müssen.
        zurueck = None
        try:
            from flask import url_for
            from models import Challenge
            from sitzung import angemeldetes_team
            if angemeldetes_team(Challenge.current()):
                zurueck = url_for("challenge.view")
        except Exception: # noqa: BLE001 - eine Fehlerseite darf nie selbst scheitern
            zurueck = None

        return render_template(
            "fehler.html", code=code, zeichen=zeichen,
            ueberschrift=ueberschrift, erklaerung=erklaerung, zurueck=zurueck
        ), code

    def abgabe_der_anfrage():
        """Team und Aufgabe einer Abgabe, die schon an der Größe scheiterte.

        Die Route ist nicht gelaufen, das Sitzungs-Cookie kam aber mit, und
        die Adresse nennt die Aufgabe. Gibt die Namen zurück, für die Zeile
        im Protokoll.
        """
        team = task = None
        try:
            from models import Challenge, Task
            from sitzung import angemeldetes_team
            team = angemeldetes_team(Challenge.current())
            task_id = (request.view_args or {}).get("task_id")
            if task_id is not None:
                task = db.session.get(Task, task_id)
        except Exception: # noqa: BLE001 - eine Fehlerseite darf nie selbst scheitern
            pass

        return (team.name if team else "unbekannt",
                task.title if task else request.path)

    for code in FEHLERSEITEN:
        # Der Umweg über die Vorgabe bindet den Wert fest: Ohne sie zeigten
        # am Ende alle Handler auf dieselbe letzte Zahl.
        @app.errorhandler(code)
        def zeigen(error, code=code):
            if (code == 413 and request.endpoint == "admin.challenge_restore"
                    and session.get("is_admin")):
                # Keine Abgabe, sondern eine Sicherung über der Grenze für
                # Sicherungen - der Satz über Scratch-Klänge passte nicht.
                # Ohne Adresse: Hier kommt nur hin, wer als Lehrkraft
                # angemeldet ist.
                ereignis("Sicherung abgelehnt: Datei zu groß (mehr als %s MB)",
                         MAX_ZIP_BYTES // (1024 * 1024))
                return fehlerseite(code, erklaerung=(
                    f"Eine Sicherung darf bis zu {MAX_ZIP_BYTES // (1024 * 1024)} MB "
                    "groß sein. Diese ist größer - sie ist wohl keine Sicherung "
                    "eines einzelnen Wettbewerbs."))
            if code == 413 and request.endpoint == "challenge.submit_task":
                # Eine zu große Datei bricht die Anfrage ab, bevor die Route
                # läuft - hier ist die einzige Stelle, an der diese Ablehnung
                # überhaupt noch festzuhalten ist. Dieselbe Zeile wie bei
                # jeder anderen abgelehnten Abgabe, also mit Team und Aufgabe
                # statt mit der Adresse des Geräts.
                team, aufgabe = abgabe_der_anfrage()
                ereignis("Abgabe abgelehnt: Team „%s“, Aufgabe „%s“ - zu groß, "
                         "mehr als %s MB", team, aufgabe,
                         app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024))
            elif code == 413:
                ereignis("Anfrage abgelehnt: zu groß (mehr als %s MB), %s",
                         app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024),
                         request.path)
            if code == 500:
                # Nach einem Fehler steht die Sitzung der Datenbank womöglich
                # quer. Die Fehlerseite fragt aber selbst noch einmal nach dem
                # Wettbewerb - also erst aufräumen.
                db.session.rollback()
            return fehlerseite(code)

app = create_app()

def startmeldung(adresse, port, protokoll):
    """Die Zeilen, die beim Start im Fenster stehen.

    Ist die Netzwerkadresse nicht bekannt, wird das gesagt, statt
    127.0.0.1 als Adresse "für andere Geräte" auszugeben - die führt kein
    Handy zum Server, und man sucht den Fehler dann bei der Firewall.
    """
    zeilen = ["Server läuft auf:", f"  http://localhost:{port}  (auf diesem Rechner)"]

    if adresse:
        zeilen.append(f"  http://{adresse}:{port}  (für andere Geräte im gleichen Netzwerk)")
    else:
        zeilen.append("  Die Adresse für andere Geräte konnte nicht ermittelt werden.")
        zeilen.append(f"  Sie gehört dann als {FESTE_ADRESSE}=192.168.… in die .env - sonst")
        zeilen.append("  steht auch auf der Startseite und im QR-Code keine brauchbare Adresse.")

    zeilen.append(f"Protokoll: {protokoll}")
    zeilen.append("Zum Beenden: STRG+C\n")
    return zeilen


def schluesselwarnung(schluessel):
    """Der Satz für Fenster und Protokoll, wenn der SECRET_KEY zu kurz ist, sonst None.

    Nur eine Warnung, kein Abbruch: Eine Installation, die am Wettbewerbstag
    nach einem Update nicht mehr startet, wäre schlimmer als der kurze
    Schlüssel. Die Startdatei ersetzt ihn beim nächsten Start ohnehin.
    """
    if not schluessel_zu_kurz(schluessel):
        return None
    return (f"SECRET_KEY in der .env ist kürzer als {MIN_SCHLUESSEL} Zeichen und lässt "
            "sich durchprobieren - wer ihn errät, kommt ohne Passwort in die "
            "Steuerzentrale. Die Startdatei ersetzt ihn beim nächsten Start selbst.")


if __name__ == "__main__":
    with app.app_context():
        db.create_all() # Auto-create tables for dev
        run_startup_migrations()

    # Debug mode is off by default: the built-in Werkzeug debugger allows
    # arbitrary code execution and this app is bound to 0.0.0.0 for LAN access,
    # so it must only be enabled explicitly for local development.
    warnung = schluesselwarnung(app.config["SECRET_KEY"])
    if warnung:
        print(f"Achtung: {warnung}")
        app.logger.warning(warnung)

    debug_mode = os.environ.get("FLASK_DEBUG", "false").strip().lower() in ("1", "true", "yes")
    port = server_port()

    if debug_mode:
        # Flask's built-in dev server, with debugger and auto-reload, for local development only.
        app.run(
          host="0.0.0.0",
          port=port,
          debug=True
        )
    else:
        # Production WSGI server for real deployments (e.g. the school LAN).
        from waitress import serve

        adresse = lan_adresse()

        for zeile in startmeldung(
            adresse, port, os.path.join(app.config["LOG_DIR"], "anwendung.log")
        ):
            print(zeile)

        # Der Start gehört ins Protokoll: Danach lässt sich später zuordnen,
        # welche Meldungen zu welchem Wettbewerbstag gehören - und mit der
        # Version, welche Fassung dabei lief.
        version = stand.ermitteln()
        if adresse:
            app.logger.info("Server gestartet auf http://%s:%s, Version %s", adresse, port, version)
        else:
            app.logger.warning(
                "Server gestartet auf Port %s, Version %s, die Netzwerkadresse ist unbekannt "
                "(%s in der .env setzen).", port, version, FESTE_ADRESSE
            )

        einmal_im_terminal(app)
        serve(app, host="0.0.0.0", port=port)

