#!/usr/bin/env python3
"""
Inithium Raidbots -> wowaudit Tool
===================================

1. Liest den SimC-Addon-Export aus der Zwischenablage.
2. Trägt ihn bei raidbots.com/simbot/droptimizer ein, fragt interaktiv nach
   Schwierigkeitsgrad / Preferred Stats / SimC-Version / High Precision und
   startet die Simulation (Quelle: aktuelle Season-Raids, höchstmögliches
   Upgrade-Level, 'Upgrade All Equipped Gear to the Same Level' ist fest an,
   da wowaudit das voraussetzt).
3. Lädt den fertigen Report automatisch bei wowaudit hoch
   (Team Inithium, Blackmoore-EU).

Funktioniert unter Windows und Linux. Beim allerersten Start wird Chromium
für Playwright automatisch heruntergeladen (einmalig, ca. 150-300 MB).
"""

import json
import os
import re
import sys
import time
import webbrowser
from typing import Optional


def _app_data_dir() -> str:
    """Persistentes Datenverzeichnis, unabhängig vom PyInstaller-Temp-Ordner
    (der bei --onefile bei jedem Start neu und woanders angelegt wird)."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    path = os.path.join(base, "raidbots-wowaudit-tool")
    os.makedirs(path, exist_ok=True)
    return path


# Muss VOR dem ersten Import von playwright gesetzt werden, sonst würde
# Playwright im gefrorenen (PyInstaller-)Zustand versuchen, Chromium in den
# ephemeren Extraktions-Temp-Ordner zu installieren/suchen - das würde bei
# jedem Start einen Neu-Download erzwingen.
os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH", os.path.join(_app_data_dir(), "browsers")
)

from playwright.sync_api import sync_playwright  # noqa: E402

RAIDBOTS_URL = "https://www.raidbots.com/simbot/droptimizer"
WOWAUDIT_URL = "https://wowaudit.com/guild/eu/blackmoore/inithium/teams/inithium/loot/characters"
SCREENSHOT_PATH = os.path.join(os.path.expanduser("~"), "wowaudit_upload_result.png")

FAILURE_PHRASES = [
    "Something is not quite right",
    "SimC Input is invalid",
    "only works for level",
    "rejected this input",
]

DIFFICULTIES = [
    ("Raid Finder", "Veteran"),
    ("Normal", "Champion"),
    ("Heroic", "Hero"),
    ("Mythic", "Myth"),
]

SIMC_VERSIONS = [
    ("weekly", "Weekly (stabiler Release, wöchentlich aktualisiert)"),
    ("nightly", "Nightly (aktuellster Stand, geringe Bug-Chance)"),
    ("latest", "Latest (jeder Commit, am wenigsten getestet)"),
]

ITEMS_TO_SIM_TRUE_SELECTORS = [
    "input[type='checkbox'][name='includeConversions']",  # Include Catalyst Items
    "input[type='checkbox'][name='upgradeEquipped']",      # Upgrade All Equipped Gear (Pflicht für wowaudit)
]

ITEMS_TO_SIM_FALSE_SELECTORS = [
    "input[type='checkbox'][name='offSpecItems']",
    "input[type='checkbox'][name='addSocket']",
]

SIM_OPTIONS_TRUE_SELECTORS = [
    "#AdvancedSimOptions-ExpansionOption-crucibleViolence",
    "#AdvancedSimOptions-ExpansionOption-crucibleSustenance",
    "#AdvancedSimOptions-ExpansionOption-cruciblePredation",
    "#AdvancedSimOptions-bloodlust",
    "#AdvancedSimOptions-arcaneInt",
    "#AdvancedSimOptions-powerWordFort",
    "#AdvancedSimOptions-markOfTheWild",
    "#AdvancedSimOptions-battleShout",
    "#AdvancedSimOptions-mysticTouch",
    "#AdvancedSimOptions-chaosBrand",
    "#AdvancedSimOptions-skyfury",
    "#AdvancedSimOptions-huntersMark",
    "#AdvancedSimOptions-bleeding",
]

SIM_OPTIONS_FALSE_SELECTORS = [
    "#AdvancedSimOptions-powerInfusion",
    "#AdvancedSimOptions-vantusRune",
    "#AdvancedSimOptions-reportDetails",
]


def ensure_chromium_installed() -> None:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
            return
    except Exception as e:  # noqa: BLE001
        if "Executable doesn't exist" not in str(e):
            raise

    print("Chromium wird einmalig heruntergeladen (ca. 150-300 MB, kann ein paar Minuten dauern) ...")
    import playwright.__main__ as pw_main

    old_argv = sys.argv
    sys.argv = ["playwright", "install", "chromium"]
    try:
        pw_main.main()
    except SystemExit:
        pass
    finally:
        sys.argv = old_argv
    print("Chromium installiert.")


def get_clipboard_text() -> str:
    try:
        import pyperclip

        text = pyperclip.paste()
        if text and text.strip():
            return text
    except Exception:  # noqa: BLE001
        pass

    import subprocess

    for cmd in (
        ["wl-paste", "--no-newline", "-t", "text/plain"],
        ["xclip", "-selection", "clipboard", "-o"],
    ):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        except FileNotFoundError:
            continue
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout

    raise SystemExit(
        "Die Zwischenablage enthält keinen Text. Bitte in WoW den SimC-Addon-Export "
        "kopieren (im Addon-Fenster: 'Copy to Clipboard' bzw. Strg+C) und danach "
        "dieses Programm erneut starten."
    )


def ask_choice(prompt: str, options: list, default_index: int = 0) -> int:
    print(prompt)
    for i, label in enumerate(options, start=1):
        marker = " (Standard)" if i - 1 == default_index else ""
        print(f"  {i}) {label}{marker}")
    while True:
        try:
            raw = input(f"Auswahl [1-{len(options)}, Enter für Standard]: ").strip()
        except EOFError:
            return default_index
        if raw == "":
            return default_index
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw) - 1
        print("Ungültige Eingabe, bitte erneut.")


def wait_for_enter(prompt: str) -> None:
    try:
        input(prompt)
    except EOFError:
        pass


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    suffix = "[J/n]" if default else "[j/N]"
    while True:
        try:
            raw = input(f"{prompt} {suffix}: ").strip().lower()
        except EOFError:
            return default
        if raw == "":
            return default
        if raw in ("j", "ja", "y", "yes"):
            return True
        if raw in ("n", "nein", "no"):
            return False
        print("Bitte mit j/n antworten.")


def open_react_select(page, label_text):
    label = page.get_by_text(label_text, exact=False)
    control = label.locator(
        "xpath=following-sibling::div[1]//div[contains(@class,'-control')]"
    )
    control.click()
    page.wait_for_timeout(300)


def run_droptimizer(simc_text: str, difficulty_index: int, simc_version: str, high_precision: bool) -> Optional[str]:
    difficulty_label = DIFFICULTIES[difficulty_index][0]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 1400})

        submit_response: dict = {}

        def on_response(resp):
            if resp.request.method == "POST" and resp.url == "https://www.raidbots.com/sim":
                submit_response["status"] = resp.status
                try:
                    submit_response["body"] = resp.json()
                except Exception:  # noqa: BLE001
                    submit_response["body"] = None

        page.on("response", on_response)

        print("Öffne Raidbots Droptimizer ...")
        page.goto(RAIDBOTS_URL, wait_until="networkidle", timeout=60000)

        print("Füge SimC-Addon-Export aus der Zwischenablage ein ...")
        editor = page.locator(".cm-content, .CodeMirror, [contenteditable='true']").first
        editor.click()
        page.keyboard.press("Control+A")
        page.keyboard.insert_text(simc_text)

        print("Warte auf Charakter-Parsing ...")
        deadline = time.time() + 25
        loaded = False
        while time.time() < deadline:
            body_text = page.inner_text("body")
            hit = next((p for p in FAILURE_PHRASES if p in body_text), None)
            if hit:
                idx = body_text.find(hit)
                print("Raidbots meldet einen Fehler beim Einlesen des Charakters:")
                print(body_text[max(0, idx - 100) : idx + 300])
                browser.close()
                return None
            if page.get_by_text("Sources", exact=True).count() > 0:
                loaded = True
                break
            page.wait_for_timeout(500)
        if not loaded:
            print(
                "Zeitüberschreitung: Der Charakter wurde nicht rechtzeitig geladen. "
                "Ist wirklich ein gültiger SimC-Addon-Export in der Zwischenablage?"
            )
            browser.close()
            return None

        print("Wähle Quelle: aktuelle Season-Raids ...")
        page.get_by_text("Raids", exact=False).first.click()
        page.wait_for_timeout(600)

        print(f"Wähle Schwierigkeitsgrad: {difficulty_label} ...")
        page.get_by_text(difficulty_label, exact=True).click()
        page.wait_for_timeout(400)

        print("Konfiguriere 'Items to Sim' ...")
        for sel in ITEMS_TO_SIM_TRUE_SELECTORS:
            page.set_checked(sel, True, force=True, timeout=5000)
        for sel in ITEMS_TO_SIM_FALSE_SELECTORS:
            page.set_checked(sel, False, force=True, timeout=5000)

        # Upgrade up to: höchstmögliches Level für die gewählte Schwierigkeit
        open_react_select(page, "Upgrade up to:")
        page.locator("[role='option']").first.click()
        page.wait_for_timeout(300)

        # Preferred Stats: Optionen live von der Seite lesen und abfragen
        open_react_select(page, "Preferred Stats:")
        stat_options = page.locator("[role='option']").all_inner_texts()
        stat_options = [s.strip() for s in stat_options if s.strip()]
        idx = ask_choice("Preferred Stats wählen:", stat_options, default_index=0)
        chosen_stats = stat_options[idx]
        page.locator("[role='option']", has_text=chosen_stats).first.click()
        page.wait_for_timeout(300)

        # Preferred Gem passend zu Preferred Stats ableiten (enthält beide Stat-Kürzel)
        stat_parts = re.split(r"[/ ]+", chosen_stats)
        if len(stat_parts) >= 2:
            open_react_select(page, "Preferred Gem:")
            gem_option = page.locator("[role='option']")
            gem_option = gem_option.filter(has_text=re.compile(re.escape(stat_parts[0][:4]), re.I))
            gem_option = gem_option.filter(has_text=re.compile(re.escape(stat_parts[1][:4]), re.I))
            if gem_option.count() > 0:
                gem_option.first.click()
            else:
                page.keyboard.press("Escape")
            page.wait_for_timeout(300)

        print("Öffne 'Simulation Options' ...")
        page.get_by_text("Simulation Options:", exact=False).click()
        page.wait_for_timeout(400)
        page.locator("#AdvancedSimOptions-showAllOptions").click()
        page.wait_for_timeout(400)

        page.select_option("#AdvancedSimOptions-simcVersion", simc_version)
        page.select_option("#AdvancedSimOptions-ExpansionOption-rubyWhelpShellTraining", "")

        for sel in SIM_OPTIONS_TRUE_SELECTORS:
            page.set_checked(sel, True, force=True, timeout=5000)
        for sel in SIM_OPTIONS_FALSE_SELECTORS:
            page.set_checked(sel, False, force=True, timeout=5000)

        page.set_checked("#smartHighPrecision", high_precision, force=True, timeout=5000)

        print("Starte Droptimizer-Simulation ...")
        page.get_by_role("button", name="Run Droptimizer").click()

        deadline = time.time() + 20
        while time.time() < deadline and "status" not in submit_response:
            page.wait_for_timeout(300)

        if submit_response.get("status") != 200:
            body = submit_response.get("body")
            print("FEHLER: Raidbots hat die Simulation abgelehnt.")
            if isinstance(body, dict):
                print(json.dumps(body, indent=2, ensure_ascii=False))
            browser.close()
            return None

        page.wait_for_timeout(1500)
        result_url = page.url
        print(f"Simulation gestartet: {result_url}")

        print("Warte auf Simulationsergebnis ...")
        deadline = time.time() + 10 * 60
        finished = False
        while time.time() < deadline:
            if page.get_by_text("BOSS SUMMARY", exact=False).count() > 0:
                finished = True
                break
            page.wait_for_timeout(2000)

        if not finished:
            print("Zeitüberschreitung beim Warten auf das Ergebnis (Sim läuft evtl. noch).")
            browser.close()
            print(f"Report-URL (später im Browser öffnen): {result_url}")
            return None

        print("Simulation fertig.")
        browser.close()

        try:
            webbrowser.open(result_url)
        except Exception:  # noqa: BLE001
            pass

        return result_url


def really_logged_in(page) -> bool:
    from urllib.parse import urlparse

    host = urlparse(page.url).hostname or ""
    if host != "wowaudit.com":
        return False
    if page.get_by_text("Log in with", exact=False).count() > 0:
        return False
    if page.get_by_text("Not logged in", exact=False).count() > 0:
        return False
    return True


def upload_to_wowaudit(report_url: str) -> bool:
    profile_dir = os.path.join(_app_data_dir(), "wowaudit-browser-profile")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            profile_dir, headless=False, viewport={"width": 1280, "height": 900}
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(WOWAUDIT_URL, wait_until="networkidle", timeout=60000)

        if not really_logged_in(page):
            print("Bitte im geöffneten Fenster bei wowaudit einloggen (Battle.net/Google) ...")
            deadline = time.time() + 10 * 60
            stable_hits = 0
            logged_in = False
            while time.time() < deadline:
                page.wait_for_timeout(2000)
                if really_logged_in(page):
                    stable_hits += 1
                    if stable_hits >= 2:
                        logged_in = True
                        break
                else:
                    stable_hits = 0
            if not logged_in:
                print("Zeitüberschreitung: kein Login erkannt.")
                context.close()
                return False
            page.goto(WOWAUDIT_URL, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(1000)

        print("Eingeloggt. Fülle Raidbots-Upload-Feld bei wowaudit ...")
        page.get_by_text("Wishlist for", exact=False).wait_for(timeout=20000)
        page.wait_for_timeout(500)

        upload_another = page.get_by_text("Upload another", exact=False)
        if upload_another.count() > 0:
            upload_another.first.click()
            page.wait_for_timeout(500)

        go_button = page.get_by_role("button", name=re.compile("^go$", re.I))
        if go_button.count() == 0:
            page.screenshot(path=SCREENSHOT_PATH, full_page=True)
            print(f"Konnte den 'Go'-Button bei wowaudit nicht finden. Screenshot: {SCREENSHOT_PATH}")
            context.close()
            return False

        container = go_button.first.locator("xpath=ancestor::div[contains(@class,'relative')][1]")
        target_input = container.locator("input[type='text']")
        if target_input.count() == 0:
            page.screenshot(path=SCREENSHOT_PATH, full_page=True)
            print(f"Konnte das Raidbots-Upload-Feld bei wowaudit nicht finden. Screenshot: {SCREENSHOT_PATH}")
            context.close()
            return False

        target_input.first.click()
        target_input.first.fill(report_url)
        go_button.first.click()
        page.wait_for_timeout(3000)

        uploaded = page.get_by_text("Your report has been uploaded", exact=False).count() > 0
        rejected = page.get_by_text("Report must be run with", exact=False).count() > 0
        page.screenshot(path=SCREENSHOT_PATH, full_page=True)
        context.close()

        if uploaded:
            print(f"Upload bei wowaudit erfolgreich. Screenshot: {SCREENSHOT_PATH}")
            return True
        if rejected:
            print(f"wowaudit hat den Report abgelehnt (Einstellungen passen nicht). Screenshot: {SCREENSHOT_PATH}")
            return False
        print(f"Unklarer Zustand nach dem Upload-Versuch bei wowaudit. Screenshot: {SCREENSHOT_PATH}")
        return False


def main() -> None:
    print("=== Inithium Raidbots -> wowaudit Tool ===")
    print()

    ensure_chromium_installed()
    simc_text = get_clipboard_text()

    diff_labels = [f"{a}/{b}" for a, b in DIFFICULTIES]
    difficulty_index = ask_choice("Schwierigkeitsgrad wählen:", diff_labels, default_index=2)

    version_labels = [desc for _, desc in SIMC_VERSIONS]
    version_index = ask_choice("SimC-Version wählen:", version_labels, default_index=1)
    simc_version = SIMC_VERSIONS[version_index][0]

    high_precision = ask_yes_no("High Precision (2x genauer, 4x langsamer) aktivieren?", default=True)

    print()
    result_url = run_droptimizer(simc_text, difficulty_index, simc_version, high_precision)
    if not result_url:
        wait_for_enter("\nFehlgeschlagen. Enter zum Beenden ...")
        sys.exit(1)

    print()
    print(f"Report-URL: {result_url}")
    print()
    print("Lade Report bei wowaudit hoch ...")
    ok = upload_to_wowaudit(result_url)

    print()
    if ok:
        print("Fertig! Report wurde bei wowaudit für dein Team hochgeladen.")
    else:
        print("Der wowaudit-Upload hat nicht geklappt. Report-URL zum manuellen Einfügen:")
        print(result_url)

    wait_for_enter("\nEnter zum Beenden ...")


if __name__ == "__main__":
    main()
