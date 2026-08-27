# Inithium Raidbots -> wowaudit Tool

Nimmt deinen SimC-Addon-Export aus der Zwischenablage, lässt ihn bei
[Raidbots Droptimizer](https://www.raidbots.com/simbot/droptimizer)
simulieren und lädt das Ergebnis automatisch über die offizielle
[wowaudit-API](https://wowaudit.com/api) für Team Inithium hoch.

## Benutzung

1. In WoW: SimC-Addon öffnen, "Copy to Clipboard" für deinen Charakter.
2. `raidbots-wowaudit-tool` (bzw. `raidbots-wowaudit-tool.exe` unter Windows)
   starten.
3. Im Terminal-Fenster ein paar Fragen beantworten (Schwierigkeitsgrad,
   Preferred Stats) — einfach Enter drücken für die vorgeschlagenen
   Standardwerte. Beim ersten Start wird einmalig der wowaudit-API-Key
   abgefragt (zu finden in wowaudit unter Team-Einstellungen -> API) und
   danach lokal gespeichert.
4. Fertig — Sim läuft automatisch, Report wird automatisch bei wowaudit
   hochgeladen.

**Wichtig:** Beim allerersten Start lädt das Tool automatisch einen Chromium-
Browser herunter (ca. 150–300 MB, einmalig, braucht Internet).

## Für Entwickler

```
pip install -r requirements.txt
python raidbots_wowaudit_tool.py
```

Die Executables werden automatisch per GitHub Actions gebaut (siehe
`.github/workflows/build.yml`) — bei jedem Push nach `main` entstehen eine
Linux- und eine Windows-Version als Build-Artefakte.
