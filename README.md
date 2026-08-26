# Inithium Raidbots -> wowaudit Tool

Nimmt deinen SimC-Addon-Export aus der Zwischenablage, lässt ihn bei
[Raidbots Droptimizer](https://www.raidbots.com/simbot/droptimizer)
simulieren und lädt das Ergebnis automatisch bei
[wowaudit](https://wowaudit.com/guild/eu/blackmoore/inithium/teams/inithium/loot/characters)
für Team Inithium hoch.

## Benutzung

1. In WoW: SimC-Addon öffnen, "Copy to Clipboard" für deinen Charakter.
2. `raidbots-wowaudit-tool` (bzw. `raidbots-wowaudit-tool.exe` unter Windows)
   starten.
3. Im Terminal-Fenster ein paar Fragen beantworten (Schwierigkeitsgrad,
   Preferred Stats, SimC-Version, High Precision) — einfach Enter drücken
   für die vorgeschlagenen Standardwerte.
4. Das Tool öffnet den Sim automatisch im Hintergrund und lädt danach ein
   sichtbares Browserfenster für wowaudit. Falls du dort noch nicht
   eingeloggt bist, einmalig mit Battle.net oder Google einloggen — das
   merkt sich das Tool für alle weiteren Läufe.
5. Fertig — der Report ist bei wowaudit hochgeladen.

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
