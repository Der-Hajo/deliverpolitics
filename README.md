# DeliverPolitics

**Versprochen. Gehalten?** DeliverPolitics misst, wie viel Parteien von ihrem Wahlprogramm umgesetzt haben. Jede Zusage wird gegen geltendes Recht geprüft, Zusage für Zusage, Monat für Monat.

Website: https://deliverpolitics.org (Beta, Methodik in Erprobung)

## Was ist DeliverPolitics?

Ein Privatprojekt von Hajo Warmbier. Die Seite ist eine neutrale Plattform: Sie misst, ob Zusagen aus Wahlprogrammen umgesetzt wurden. Sie bewertet nicht, ob die Politik gut oder schlecht ist oder ob ein Bruch gerechtfertigt war.

- **Gemessen wird** pro Partei der Anteil erfüllter Teilzusagen am ganzen Wahlprogramm (Gesamtprogramm) sowie, als zweiter Index, der Anteil bei den von der Partei selbst herausgestellten Kernversprechen.
- **Aktuell erfasst:** SPD und CDU/CSU, Bund, 21. Wahlperiode.
- **Belege:** Jede Zusage wird mit Bundesgesetzblatt und amtlichen Quellen belegt.
- **Stand:** monatliches Update zum Monatsende.
- **Methodik:** öffentlich unter [So messen wir](https://deliverpolitics.org/so-messen-wir.html).
- **Daten:** als CSV unter [Daten](https://deliverpolitics.org/daten.html) zum Download.

## Beta und Feedback

Die Seite ist eine Beta-Version. Ziel ist Rückmeldung von Wissenschaft, Politologie, Studierenden und Journalisten, um die Methodik zu verbessern, ohne sie zu verkomplizieren.

Feedback: über das Formular auf der Website oder per E-Mail an feedback@deliverpolitics.org.

## Was liegt in diesem Repository?

Dieses Repository enthält die **fertig erzeugte, öffentliche Website** (statisches HTML, CSS und Daten, kein Server-Code, keine Cookies, keine Tracker). Sie wird über GitHub Pages ausgeliefert.

| Ordner/Datei | Inhalt |
|---|---|
| `index.html` und weitere `*.html` | Seiten der Website |
| `bund-21/` | Index Bund, 21. Wahlperiode (Gesamtprogramm, Kernversprechen, Updates, Vorhaben) |
| `spotlight/` | Monatliche Schlaglichter |
| `daten/` | Datendownloads (CSV) |
| `programme/` | Kopien der Wahlprogramme als PDF (zur Nachprüfbarkeit) |
| `assets/` | Stylesheets, Skripte, Bilder |
| `CNAME` | Eintrag für die Domain deliverpolitics.org |
| [`CHANGELOG.md`](CHANGELOG.md) | Änderungen an der Website mit Datum |

Quelldaten, Arbeitsdokumente und das Programm, das die Seiten erzeugt, liegen **nicht** in diesem Repository.

## Wie werden Änderungen veröffentlicht?

- Der Zweig `main` ist die Live-Version. Alles, was dort landet, erscheint automatisch auf deliverpolitics.org.
- Jede Änderung entsteht in einem eigenen Zweig und wird über einen Pull Request geprüft. Erst nach Freigabe wird sie in `main` übernommen.
- Jede veröffentlichte Änderung steht im [Changelog](CHANGELOG.md).

## Kontakt und Verantwortlicher

Siehe [Impressum](https://deliverpolitics.org/impressum.html).
