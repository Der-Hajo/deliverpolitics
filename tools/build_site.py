#!/usr/bin/env python3
"""Erzeugt die statische Website (reines HTML/CSS, ohne Server-Code) aus den CSV-Daten.

Aufruf (im Repo-Ordner):  python3 tools/build_site.py --stand 2026-10 --out ../site-build
--stand  letzter ausgewiesener Monat (JJJJ-MM); Stichtag ist dessen Monatsletzter.
--out    Zielordner AUSSERHALB des Repos; er wird vor dem Lauf gelöscht und neu erzeugt.
Ergebnis: Ordner, dessen Inhalt in den Repo-Ordner übernommen wird (ohne tools/, CNAME, README.md, CHANGELOG.md).
Eingaben: tools/daten/ (CSV, befunde.json), tools/entscheidungen.md, tools/datenschutz.html, tools/icon/, programme/ (PDF-Kopien).
"""
import datetime as dt
import posixpath, argparse, calendar, collections, csv, html, json, os, re, shutil

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(BASE, "tools", "daten")
DOMAIN = "deliverpolitics.org"         # nur für die Zitierhilfe
KONTAKT = "feedback@deliverpolitics.org"

MON = ["Jan.", "Feb.", "Mär.", "Apr.", "Mai", "Jun.", "Jul.", "Aug.", "Sep.", "Okt.", "Nov.", "Dez."]
MONL = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
# Parlamente und gemessene Parteien stehen in den Daten (parlamente.csv, indizes.csv), nicht im Code.
PARLAMENTE = sorted(csv.DictReader(open(os.path.join(D, "parlamente.csv"), encoding="utf-8")), key=lambda r: int(r["sortierung"]))
HP = PARLAMENTE[0]            # Hauptparlament (Bund): groß auf der Startseite, eigener Punkt in der Hauptnavigation
LAENDER = [r for r in PARLAMENTE if r["ebene"] == "Land"]  # Landesparlamente (auch „in Vorbereitung“)
INDIZES = list(csv.DictReader(open(os.path.join(D, "indizes.csv"), encoding="utf-8-sig")))

def setze(P):
    """Stellt das Parlament ein, dessen Seiten erzeugt werden (ein Lauf je Parlament)."""
    global PARL, PDIR, IDX, PARLSEITEN, KERN, HAUPT, WAHLTAG, NAECHSTE_WAHL, ENDE_WP
    PARL = P; PDIR = P["parlament_id"]; HAUPT = P is HP
    IDX = {r["kuerzel"]: dict(index_id=r["index_id"], name=r["name"], slug=r["slug"], prog=r["prog"], url=r["url"], url_label=r["url_label"], pdf=r["pdf"], basis=r["basis"])
           for r in INDIZES if r["parlament"] == PDIR and not r["index_id"].endswith("-KERN")}
    KERN = any(r["parlament"] == PDIR and r["index_id"].endswith("-KERN") for r in INDIZES)  # gibt es den Index Kernversprechen (E36)?
    PARLSEITEN = {"index.html", "kernversprechen.html", "gesamtprogramm.html", "aenderungen.html"} | {c["slug"] + ".html" for c in IDX.values()}
    WAHLTAG = P["wahltag"]
    NAECHSTE_WAHL = P["naechste_wahl"]  # voraussichtlich; Bund: frühestens 46, spätestens 48 Monate nach Beginn der Wahlperiode (Art. 39 GG)
    ENDE_WP = P["ende_wp"]              # voraussichtliches Ende der Wahlperiode (JJJJ-MM), Ende der Zeitachse

setze(HP)

# Hinweis zu Absichtssätzen („wollen“, „planen“, „sollen“), freigegeben 12.11.2026 (E5, E29).
# Allgemeine Sätze gelten für alle Parlamente; Beispiel und Zahlen je Land (nur Zahlen, ohne Programmlänge).
W_SATZ1 = ("Gezählt werden nur Sätze, mit denen sich eine Partei festlegt: „Wir führen … ein“, „Wir schaffen …“, „… wird fortgeführt“. "
           "Sätze mit „wollen“, „planen“ oder „sollen“ zählen nicht, auch wenn sie ein konkretes Instrument oder eine Zahl nennen. "
           "Sie beschreiben eine Absicht, keine Zusage.")
W_SATZ3 = ("Die Regel gilt für alle Parteien gleich, im Bund wie im Land. Ein Programm mit vielen Absichtssätzen hat weniger gezählte Zusagen. "
           "Über die Qualität des Programms sagt das nichts. Ob eine Absicht später trotzdem umgesetzt wird, zeigt der Index nicht.")
W_BEISPIEL = {"baden-wuerttemberg-18": "Die CDU nennt eine Anhebung des Ausgleichsstocks auf 350 Mio. Euro, die Grünen eine Polizeizulage von mindestens 228 Euro im Monat. "
                                       "Beides steht als Absicht im Programm und wird deshalb nicht gemessen."}
W_ZAHLEN = {"baden-wuerttemberg-18": "Im Programm der Grünen stehen rund 180 solcher Absichtssätze, im Programm der CDU rund 70."}
# Übereinstimmung der zwei unabhängigen Themen-Codierungen (Hauptthema, E38) je Parlament
CAP_UEB = {"bund-21": 94, "baden-wuerttemberg-18": 92}

def w_hinweis(pid):
    """Hinweistext „Warum manche konkreten Vorhaben nicht zählen“ für die Übersicht eines Landesparlaments."""
    mitte = (f"<p style=\"font-size:15px;color:var(--ink2);margin:8px 0 0\">Ein Beispiel aus jedem Programm: {e(W_BEISPIEL[pid])} {e(W_ZAHLEN[pid])}</p>"
             if pid in W_BEISPIEL else "")
    return (f"<p style=\"font-size:15px;color:var(--ink2);margin:8px 0 0\">{e(W_SATZ1)}</p>{mitte}"
            f"<p style=\"font-size:15px;color:var(--ink2);margin:8px 0 0\">{e(W_SATZ3)}</p>")

def pk(tid):
    """Schlüssel der Partei (kuerzel in indizes.csv = Präfix der Kennungen) zu einer Vorhaben- oder Teilzusagen-ID."""
    return max((k for k in IDX if tid.startswith(k + "-")), key=len)

e = lambda s: html.escape(str(s), quote=True)
de = lambda d: f"{d[8:10]}.{d[5:7]}.{d[:4]}"
pct = lambda x: ("%.1f" % x).replace(".", ",")
def num(v):
    return f"{round(100 * float(v))} %"
def stichtag_str(m):
    y, mo = int(m[:4]), int(m[5:]); return f"{y}-{mo:02d}-{calendar.monthrange(y, mo)[1]:02d}"
def mlabel(m): return f"{MON[int(m[5:]) - 1]} {m[:4]}"

def load():
    items = sorted(csv.DictReader(open(os.path.join(D, "items.csv"), encoding="utf-8")), key=lambda r: r["item_id"])
    tzs = [t for t in csv.DictReader(open(os.path.join(D, "teilzusagen.csv"), encoding="utf-8")) if t["status_zuschnitt"] == "aktiv"]
    ih = {(r["item_id"], r["month"]): r for r in csv.DictReader(open(os.path.join(D, "item_history.csv"), encoding="utf-8"))}
    kh = {(r["index_id"], r["month"]): r for r in csv.DictReader(open(os.path.join(D, "kpi_history.csv"), encoding="utf-8"))}
    return items, tzs, ih, kh

def status(t, st):
    ea, en, fr = t["erfuellt_ab"], t["entfallen_ab"], t["frist"]
    if t["typ_zusage"] == "Bestand":
        if en and en <= st: return "gebrochen seit " + de(en), "br"
        if not ea: return "nicht erfüllt", ""  # Bestandszusage, deren Maßstab (z. B. Mittel über Vorwahlansatz) nicht belegt ist
        return "erfüllt (Bestand)", "ok"
    if ea and ea <= st and (not en or en > st):
        return "erfüllt seit " + de(ea) + (" (befristet)" if en else ""), "ok"
    if ea and ea > st: return "beschlossen, gilt ab " + de(ea), "be"
    if t["bewertung"].startswith("beschlossen"): return "beschlossen, Verkündung ausstehend", "be"
    if fr and fr < st: return "Frist verfehlt", "br"
    if fr: return "nicht erfüllt · Frist " + de(fr), ""
    return "nicht erfüllt", ""

def sauber(b):
    """Entfernt interne Prüfvermerke (… prüfen) aus Belegtexten."""
    b = re.sub(r"\s*\([^()]*prüfen[^()]*\)", "", b)
    b = re.sub(r"\s*[;–]\s*[^;()–]*prüfen[^;()–]*", "", b)
    # interne Versionsvermerke (v1/v2) nicht veröffentlichen
    b = re.sub(r"\s*\((?:v1|v2|v1/v2)\)", "", b)
    b = re.sub(r"[;,]\s*v[12](?:/v2)?(?=\))", "", b)
    b = re.sub(r"\((?:v1|v2|v1/v2)[;,]\s*", "(", b)
    b = re.sub(r"\s*–\s*Aktualisierung gegenüber v2", "", b)
    return b.strip(" ;–")

def beleg(t, prev):
    b = re.sub(r"\s*\((v1|v2)\)", "", t["rechtsakt"]).strip()
    # interne Prüfvermerke nicht veröffentlichen
    b = re.sub(r"\s*\([^()]*prüfen[^()]*\)", "", b)
    b = sauber(b)
    if b.startswith("dto.") and prev: b = prev + b[4:]
    if not b or b == "–":
        b = ("Kein gegenläufiges Handeln Deutschlands bekannt (E32)." if HAUPT else "Kein gegenläufiger Rechtsakt bekannt (E33).") if t["typ_zusage"] == "Bestand" else "Kein Beleg für eine beschlossene Maßnahme."
    return b[:1].upper() + b[1:]

def proglink(cfg, rel="", satz=False):
    """Programmtitel, verlinkt auf die Seite der Partei, plus Link auf die Kopie auf dieser Website."""
    t = f'<a href="{e(cfg["url"])}" rel="noopener">{e(cfg["prog"])}</a>' if cfg["url"] else e(cfg["prog"])
    return t + f' <span style="white-space:nowrap">(<a href="{rel}{cfg["pdf"]}">Kopie als PDF</a>)</span>'

def meter(v, w=72):
    """Balken für den Anteil erfüllter Teilzusagen; v = None für ausgeschlossene Kapitel."""
    if v is None:
        return f'<span class="bar x" style="width:{w}px" aria-hidden="true"></span>'
    return f'<span class="bar" style="width:{w}px" aria-hidden="true"><span style="width:{round(100 * float(v))}%"></span></span>'

CSS = """
:root{--bg:#F6F7F7;--ink:#16191C;--ink2:#39424A;--mut:#5F6A72;--line:#DEE3E6;--line2:#BFC9CE;--card:#FFFFFF;--acc:#2F5D62;--ok:#28695E;--be:#875C08;--br:#B0362A;--no:#AAB4BA}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:system-ui,-apple-system,"Segoe UI",sans-serif;line-height:1.5}
a{color:var(--acc);text-underline-offset:3px}a:hover{color:var(--ink)}
a:focus-visible,summary:focus-visible,.btn:focus-visible,label:focus-visible{outline:2px solid var(--acc);outline-offset:2px}
.skip{position:absolute;left:-9999px;top:0;background:var(--ink);color:var(--bg);padding:10px 16px;z-index:10}.skip:focus{left:16px;top:8px}
.mono{font-variant-numeric:tabular-nums}
.id{font-family:ui-monospace,"Cascadia Mono",Consolas,Menlo,monospace;font-size:12.5px;letter-spacing:0}
.serif{font-family:Georgia,"Iowan Old Style","Palatino Linotype",serif}
.label{font-size:12px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--mut)}
.beta{background:var(--ink);color:var(--bg);font-size:13px}
.beta div{max-width:1080px;margin:0 auto;padding:7px 24px;display:flex;flex-wrap:wrap;gap:6px 16px;align-items:center}
.beta a{color:var(--bg)}
.beta .tag{font-size:11px;font-weight:600;letter-spacing:.1em;border:1px solid var(--bg);padding:2px 8px}
.wrap{max-width:1080px;margin:0 auto;padding:0 24px}
header.top{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px 32px;padding:22px 0 14px;border-bottom:2px solid var(--ink)}
.brand{color:var(--ink);text-decoration:none;font-weight:600;font-size:20px;letter-spacing:.02em}
nav.main{display:flex;flex-wrap:wrap;gap:4px 24px}
nav.main a{color:var(--ink2);text-decoration:none;font-size:15px;padding:12px 0;border-bottom:1px solid transparent}
nav.main a:hover,nav.main a[aria-current]{color:var(--ink);border-bottom-color:var(--ink)}
.crumb{font-size:12.5px;color:var(--mut);padding:18px 0 0;display:flex;gap:8px;flex-wrap:wrap}
.crumb a{color:var(--mut)}
h1{font-weight:600;margin:0}
h2{font-weight:600;margin:0}
.lead{font-size:17px;color:var(--ink2);max-width:62ch}
.card{background:var(--card);border:1px solid var(--line);padding:24px 26px}
.plain{border-top:1px solid var(--line2);padding-top:18px}
.big{font-weight:600;font-variant-numeric:tabular-nums;letter-spacing:-.03em;line-height:1}
.kvd.ok{background:var(--ok)}.kvd.be{background:var(--be)}.kvd.br{background:var(--br)}.kvd.of{background:var(--line);box-shadow:inset 0 0 0 1px var(--line2)}
.gbar{display:flex;gap:2px;width:100%}
.gseg{position:relative;display:block;min-width:4px;cursor:pointer;background:var(--line)}
.gseg.ok{background:var(--ok)}.gseg.be{background:var(--be)}.gseg.br{background:var(--br)}.gseg.of{background:var(--line);box-shadow:inset 0 0 0 1px var(--line2)}
.gseg:hover,.gseg:focus-within{outline:2px solid var(--ink);outline-offset:1px;z-index:30}
.gpop{display:none;position:absolute;top:100%;left:0;padding-top:8px;z-index:30;width:min(360px,86vw);cursor:auto;text-align:left;white-space:normal}
.gseg.r .gpop{left:auto;right:0}
.gseg:hover .gpop,.gseg:focus-within .gpop{display:block}
.gseg:hover .gpop,.gseg:focus-within .gpop{animation:gpe .45s step-end}
@keyframes gpe{from{pointer-events:none}to{pointer-events:auto}}
.gin{display:block;background:var(--card);border:1px solid var(--line2);box-shadow:0 6px 18px rgba(0,0,0,.14);padding:10px 12px;max-height:300px;overflow:auto;font-family:system-ui,-apple-system,"Segoe UI",sans-serif;font-size:13.5px;line-height:1.35;color:var(--ink);font-weight:400;letter-spacing:0;text-transform:none}
.gin b{display:block;font-weight:600;margin-bottom:4px}
.gli{display:block;padding:5px 0;border-top:1px solid var(--line)}
.gli .gst{color:var(--mut);white-space:nowrap}
.gw{display:inline-block;vertical-align:middle}
@media (min-width:721px){.scroll{overflow:visible}}
.kvd{display:inline-block;width:12px;height:12px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.kvl{margin-top:12px;font-size:14px}.kvl summary{cursor:pointer;color:var(--acc)}.kvl ul{list-style:none;padding:0;margin:8px 0 0}.kvl li{padding:4px 0;border-top:1px solid var(--line)}
.metaz{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px 20px;margin:24px 0 0;padding:10px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line);font-size:13px;color:var(--mut)}
.sandz{display:inline-flex;align-items:center;gap:8px;font-size:13.5px;color:var(--ink2)}
.bil .bz{margin-top:18px}.bil .bz+.bz{padding-top:16px;border-top:1px solid var(--line)}
.bkopf{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 16px;margin-bottom:10px}.bkopf .label{flex-basis:100%}.bsub{font-size:14.5px;color:var(--ink2)}
.bnote{font-size:13.5px;color:var(--mut);margin-top:7px}
.sbar{display:flex;background:var(--line)}.sbar .ok{background:var(--ok)}.sbar .be{background:var(--be)}.sbar .br{background:var(--br)}
.kbar{display:flex;gap:1px;background:var(--card)}
.kbar a{flex:1;position:relative;background:var(--line);min-width:2px}
.kbar a.ok{background:var(--ok)}.kbar a.be{background:var(--be)}.kbar a.br{background:var(--br)}
.kbar a:hover,.kbar a:focus{outline:2px solid var(--ink);outline-offset:1px;z-index:4}
.kbar .tip{display:none;position:absolute;bottom:calc(100% + 8px);left:50%;transform:translateX(-50%);width:240px;background:var(--ink);color:#fff;font-size:13.5px;line-height:1.35;padding:8px 10px;border-radius:4px;z-index:5;pointer-events:none;text-align:left}
.kbar a.l .tip{left:0;transform:none}.kbar a.r .tip{left:auto;right:0;transform:none}
.kbar .tip b{display:block;font-weight:600;margin-top:4px;color:#E3E8EA}
.kbar a:hover .tip,.kbar a:focus .tip{display:block}
@media (hover:none){.hovtip{display:none}}
.auf{margin-top:12px;border-top:1px solid var(--line)}.auf>summary{cursor:pointer;list-style:none;display:flex;align-items:center;gap:10px;padding:14px 0;font-size:15.5px;color:var(--acc)}.auf>summary::-webkit-details-marker{display:none}
.auf .pm{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border:1px solid var(--acc);border-radius:3px;font-weight:600;flex:none}.auf .pm::before{content:"+"}.auf[open] .pm::before{content:"−"}
.auf>summary:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.subnav{display:flex;flex-wrap:wrap;align-items:center;gap:6px 22px;padding:12px 0;border-bottom:1px solid var(--line);font-size:14.5px}
.subnav .subtitel{font-weight:600;color:var(--ink);margin-right:6px}.subnav a{color:var(--ink2);text-decoration:none;padding:2px 0}.subnav a[aria-current]{color:var(--ink);border-bottom:2px solid var(--ink)}.subnav a:hover{color:var(--ink)}
.spotgrid{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,1fr);gap:28px;align-items:start}
.spotbild img{width:100%;height:auto;display:block;border:1px solid var(--line)}
.mz{display:grid;grid-template-columns:auto minmax(0,1fr);gap:10px;padding:9px 0;border-top:1px solid var(--line);font-size:15px}
.ptag{font-size:11.5px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:var(--ink2);border:1px solid var(--line2);border-radius:3px;padding:1px 6px;height:fit-content;margin-top:2px}
.teil{margin-top:14px}.teil label{display:block;font-size:14.5px;margin-bottom:6px}
.teil textarea{width:100%;box-sizing:border-box;font:inherit;font-size:14.5px;line-height:1.45;color:var(--ink);background:var(--card);border:1px solid var(--line2);border-radius:3px;padding:10px 12px;resize:vertical}
.teil textarea:focus{outline:2px solid var(--ink);outline-offset:1px}
.lgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:16px}
.lk{background:var(--card);border:1px solid var(--line);padding:18px 20px}
.lgrid.kompakt .lk{padding:14px 16px}.lgrid.kompakt .lk .serif{font-size:18px!important}
.lstatus{display:inline-block;margin-top:12px;font-size:12px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:var(--ink2);border:1px dashed var(--line2);border-radius:3px;padding:2px 8px}
.lsub{text-transform:none;letter-spacing:0;font-weight:400;color:var(--mut)}
.tz2{display:grid;grid-template-columns:230px minmax(0,1fr);gap:6px 20px;padding:12px 0;border-bottom:1px solid var(--line);align-items:center}
.tzn{font-weight:600;font-size:15.5px}
.tp{display:grid;grid-template-columns:72px minmax(0,1fr) 150px;gap:12px;align-items:center;margin:3px 0}
.tpn{font-size:13.5px;color:var(--ink2);white-space:nowrap}.tw{font-size:13.5px;color:var(--mut)}.tw b{color:var(--ink);font-size:15px;margin-right:4px}.tw.klein,.tw.klein b{color:var(--mut);font-weight:400}
.legz{display:flex;flex-wrap:wrap;gap:6px 20px;font-size:14px;margin-top:14px;color:var(--ink2)}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:24px}
.facts{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:13.5px;color:var(--ink2)}
.note{font-size:13.5px;color:var(--mut);max-width:84ch}
a.cardlink{display:block;text-decoration:none;color:inherit}
a.cardlink:hover{border-color:var(--line2)}
.bar{display:inline-block;height:8px;border:1px solid var(--line2);vertical-align:middle;background:var(--card)}
.bar span{display:block;height:100%;background:var(--ok)}
.bar.x{border-style:dotted}
details.v{border-bottom:1px solid var(--line)}
details.v summary{list-style:none;cursor:pointer;display:grid;grid-template-columns:76px minmax(0,1fr) 92px 140px 20px;gap:16px;align-items:center;padding:15px 4px;min-height:56px}
details.v summary::-webkit-details-marker{display:none}
details.v summary:hover{background:var(--card)}
details.v summary .sign::before{content:"+"}
details.v[open] summary .sign::before{content:"–"}
.vbody{background:var(--card);border-top:1px solid var(--line);padding:6px 20px 20px}
.tz{display:grid;grid-template-columns:44px minmax(0,1fr) 230px;gap:14px;padding:9px 0;border-bottom:1px solid #EEF1F2;font-size:14.5px}
.st,.badge{font-size:13.5px;color:var(--mut);white-space:nowrap;display:inline-flex;align-items:center;gap:8px}
.st{white-space:normal;align-items:baseline}.st::before{transform:translateY(1px)}
.st::before,.badge::before{content:"";flex:none;width:10px;height:10px;border-radius:50%;background:var(--no)}
.ok .st,.ok .badge{color:var(--ok);font-weight:600}.ok .st::before,.ok .badge::before{background:var(--ok)}
.be .st,.be .badge{color:var(--be);font-weight:600}.be .st::before,.be .badge::before{background:var(--be)}
.br .st,.br .badge{color:var(--br);font-weight:600}.br .st::before,.br .badge::before{background:var(--br)}
a.brlink{color:var(--br)}
.typ{font-size:12px;color:var(--mut);margin-left:6px}
.typ.kern{color:var(--acc);border:1px solid var(--acc);border-radius:3px;padding:0 4px;font-weight:600;font-size:11px;vertical-align:1px}
.thead{display:grid;grid-template-columns:76px minmax(0,1fr) 92px 140px 20px;gap:16px;padding:12px 4px;border-bottom:1px solid var(--line)}
.scroll{overflow-x:auto}
.sr{position:absolute;opacity:0;width:1px;height:1px}
.sortbar{display:flex;flex-wrap:wrap;align-items:center;gap:6px 8px;margin-top:14px;font-size:14px;color:var(--mut)}
.sortbar label{cursor:pointer;padding:6px 12px;border:1px solid var(--line2);color:var(--ink2)}
#s-kap:checked~.sortbar label[for=s-kap],#s-ant:checked~.sortbar label[for=s-ant]{background:var(--ink);border-color:var(--ink);color:var(--bg)}
#s-kap:focus-visible~.sortbar label[for=s-kap],#s-ant:focus-visible~.sortbar label[for=s-ant]{outline:2px solid var(--acc);outline-offset:2px}
.vlist{display:flex;flex-direction:column}
#s-ant:checked~.scroll .vlist>details{order:var(--o)}
.tzd{border-bottom:1px solid var(--line)}
.tzd summary{list-style:none;cursor:pointer;display:grid;grid-template-columns:52px minmax(0,1fr) 230px 16px;gap:16px;align-items:baseline;padding:14px 4px}
.tzd summary::-webkit-details-marker{display:none}
.tzd summary:hover{background:var(--card)}
.tzd summary .sign::before{content:"+";color:var(--mut)}
.tzd[open] summary .sign::before{content:"–"}
.tzd .tzbody{padding:0 4px 16px 72px;font-size:14px;color:var(--ink2)}
.tzd .tzbody .label{margin-right:8px}
.tzd:target summary{background:var(--card)}
.lc{display:grid;grid-template-columns:110px 120px 1fr;gap:16px;padding:13px 0;border-bottom:1px solid var(--line);font-size:15px}
.ch{display:grid;grid-template-columns:100px 130px minmax(0,1fr) 190px;gap:16px;padding:12px 0;border-bottom:1px solid var(--line);font-size:15px;align-items:baseline}
.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:0 32px;border-top:1px solid var(--line2)}
.steps>div{padding:18px 0;border-bottom:1px solid var(--line)}
.steps p{font-size:15px;color:var(--ink2);margin:8px 0 0}
.btn{display:inline-flex;align-items:center;min-height:44px;padding:10px 16px;border:1px solid var(--line2);color:var(--ink);text-decoration:none;font-size:14px}
.btn.on{background:var(--ink);border-color:var(--ink);color:var(--bg)}
.prose{max-width:76ch;font-size:15.5px;color:var(--ink2)}
.prose h2{font-family:Georgia,serif;font-size:22px;color:var(--ink);margin:36px 0 8px}
.prose details.dec{border-bottom:1px solid var(--line);max-width:76ch}
.prose details.dec summary{list-style:none;cursor:pointer;display:flex;gap:14px;align-items:baseline;padding:12px 4px;font-family:Georgia,serif;font-size:18px;color:var(--ink)}
.prose details.dec summary::-webkit-details-marker{display:none}
.prose details.dec summary:hover{background:var(--card)}
.prose details.dec summary::after{content:"+";margin-left:auto;color:var(--mut);font-family:system-ui,sans-serif}
.prose details.dec[open] summary::after{content:"–"}
.prose details.dec summary .id{min-width:42px;color:var(--mut)}
.prose .decbody{padding:0 4px 14px 60px}
.prose h3{font-size:17px;color:var(--ink);margin:24px 0 6px}
footer.foot{margin-top:64px;padding:22px 0 40px;border-top:1px solid var(--line);display:flex;flex-wrap:wrap;gap:12px 24px;justify-content:space-between;font-size:13.5px;color:var(--mut)}
footer.foot a{color:var(--mut)}
@media (max-width:640px){
 nav.main{gap:2px 16px}nav.main a{font-size:14px;padding:8px 0}
 .subnav{display:grid;grid-template-columns:1fr 1fr;gap:6px 16px;font-size:14px}.subnav .subtitel{grid-column:1/-1;margin:0 0 2px}
 .big.xl{font-size:56px!important}
 h1.hero{font-size:40px!important}
 .tz{grid-template-columns:40px minmax(0,1fr)}
 .tz .st{grid-column:2}
 .tzd summary{grid-template-columns:40px minmax(0,1fr) 16px}
 .tzd summary .st{grid-column:2;grid-row:2}
 .tzd .tzbody{padding-left:60px}
 .ch,.lc{grid-template-columns:1fr!important;gap:2px}
 .wrap{padding:0 16px}
 .tz2{grid-template-columns:1fr}
 .tp{grid-template-columns:58px minmax(0,1fr) 108px;gap:8px}.tpn{font-size:12.5px}.tw{font-size:12.5px}
 .spotgrid{grid-template-columns:1fr}
 .gpop{position:fixed;left:16px!important;right:16px!important;top:auto;bottom:16px;width:auto;padding-top:0}
 .gin{max-height:55vh}
 main{overflow-wrap:anywhere}
}
"""

LEAD_SLUG = "cdu-csu.html"  # wird in main() auf die führende Partei gesetzt


def sanduhr(stichtag_iso, w=96, h=160):
    """Sanduhr als SVG: Anteil der vergangenen Zeit vom Wahltag bis zur voraussichtlichen nächsten Wahl.
    Die Sandhöhe ist proportional zur Zeit gezeichnet (nicht volumentreu), damit der Anteil ablesbar ist."""
    a, z, s_ = (dt.date.fromisoformat(x) for x in (WAHLTAG, NAECHSTE_WAHL, stichtag_iso))
    p = max(0.0, min(1.0, (s_ - a).days / (z - a).days))
    mon = (s_.year - a.year) * 12 + s_.month - a.month - (1 if s_.day < a.day else 0)
    ges = (z.year - a.year) * 12 + z.month - a.month
    W, cx, top, mid, bot, hw = 120, 60, 16, 100, 184, 42
    ho = (mid - top) * (1 - p)            # Sandhöhe oben (über der Taille)
    hu = (bot - mid) * p                  # Sandhöhe unten
    wo = hw * ho / (mid - top)            # Breite der Sandoberfläche oben
    yu = bot - hu; wu = hw * (yu - mid) / (bot - mid)
    sand = "#BCA77A"
    svg = (f'<svg viewBox="0 0 {W} 200" width="{w}" height="{h}" role="img" aria-label="Sanduhr: {mon} von {ges} Monaten der Wahlperiode vergangen ({round(100 * p)} %)">'
           f'<rect x="{cx - hw - 8}" y="8" width="{2 * hw + 16}" height="8" rx="2" fill="#39424A"/>'
           f'<rect x="{cx - hw - 8}" y="{bot}" width="{2 * hw + 16}" height="8" rx="2" fill="#39424A"/>'
           f'<path d="M{cx - hw},{top} L{cx + hw},{top} L{cx + 3},{mid} L{cx + hw},{bot} L{cx - hw},{bot} L{cx - 3},{mid} Z" fill="#FFFFFF" stroke="#BFC9CE" stroke-width="2"/>'
           + (f'<path d="M{cx - wo:.1f},{mid - ho:.1f} L{cx + wo:.1f},{mid - ho:.1f} L{cx},{mid - 1} Z" fill="{sand}"/>' if ho > 0.5 else "")
           + (f'<path d="M{cx - hw + 2},{bot - 1} L{cx + hw - 2},{bot - 1} L{cx + wu:.1f},{yu:.1f} L{cx - wu:.1f},{yu:.1f} Z" fill="{sand}"/>' if hu > 0.5 else "")
           + (f'<line x1="{cx}" y1="{mid - 1}" x2="{cx}" y2="{yu:.1f}" stroke="{sand}" stroke-width="2"/>' if 0 < p < 1 else "")
           + '</svg>')
    return svg, mon, ges, p

def page(title, body, rel="", cur="", og=None, ogalt=None, pub=None):
    # Dateinamen hier im flachen Erzeugungs-Layout; LAYOUT (unten) verschiebt sie an ihre endgültigen Adressen
    parl = cur in PARLSEITEN or cur == "vorhaben"
    top = [("_aktuell.html", "Aktuell", cur in ("_aktuell.html", "befunde.html")), ("index.html" if HAUPT else HP["parlament_id"] + "/index.html", HP["name"], parl and HAUPT)]
    if LAENDER: top.append(("laender.html", "Länder", cur == "laender.html" or (parl and not HAUPT)))
    top += [("methodik.html", "So messen wir", cur == "methodik.html"), ("ueber.html", "Projekt", cur == "ueber.html")]
    navh = "".join(f'<a href="{rel}{h}"{" aria-current=\"page\"" if an else ""}>{t}</a>' for h, t, an in top)
    sub = ""
    if parl:
        sl = [("index.html", "Übersicht"), ("gesamtprogramm.html", "Gesamtprogramm"), ("kernversprechen.html", "Kernversprechen"), ("aenderungen.html", "Updates")]
        if not KERN: sl = [x for x in sl if x[0] != "kernversprechen.html"]
        akt = "gesamtprogramm.html" if (cur == "vorhaben" or cur in {c["slug"] + ".html" for c in IDX.values()}) else cur
        sub = (f'<nav class="subnav" aria-label="{e(PARL["name"])}"><span class="subtitel">{e(PARL["name"])} · {PARL["wahlperiode"]}. Wahlperiode</span>'
               + "".join(f'<a href="{rel}{h}"{" aria-current=\"page\"" if h == akt else ""}>{t}</a>' for h, t in sl) + '</nav>')
    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title) if cur == "_aktuell.html" else e(title) + " – DeliverPolitics"}</title>
<meta name="description" content="@@DESC@@">
<link rel="canonical" href="@@URL@@">
{JSONLD if cur == "_aktuell.html" else ""}
<meta name="author" content="Hajo Warmbier">
<meta property="og:type" content="{"article" if pub else "website"}">{f'<meta property="article:published_time" content="{pub}"><meta property="article:author" content="Hajo Warmbier">' if pub else ""}
<meta property="og:site_name" content="DeliverPolitics">
<meta property="og:locale" content="de_DE">
<meta property="og:title" content="{e(title) if cur == "_aktuell.html" else e(title) + " – DeliverPolitics"}">
<meta property="og:description" content="@@DESC@@">
<meta property="og:url" content="@@URL@@">
<meta property="og:image" content="https://{DOMAIN}/{og or "og.png"}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{e(ogalt) if ogalt else "@@OGALT@@"}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{rel}favicon.ico" sizes="any">
<link rel="icon" href="{rel}favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="{rel}apple-touch-icon.png">
<link rel="stylesheet" href="{rel}assets/style.css">
</head>
<body>
<a class="skip" href="#inhalt">Zum Inhalt springen</a>
<div class="beta"><div><span class="tag">BETA</span><span>Methodik in Erprobung</span><a href="{rel}ueber.html#feedback">Feedback geben</a></div></div>
<div class="wrap">
<header class="top"><a href="{rel}_aktuell.html" class="brand serif">DELIVERPOLITICS</a><nav class="main" aria-label="Hauptnavigation">{navh}</nav></header>
{sub}
<main id="inhalt">
{body}
</main>
<footer class="foot"><span>Unabhängig · werbefrei · <a href="{rel}ueber.html#offenlegung">Offenlegung</a> · <a href="{rel}ueber.html#ki">Erstellt mit Unterstützung von KI</a></span><span style="display:flex;flex-wrap:wrap;gap:8px 20px"><a href="{rel}befunde.html">Alle Spotlights</a><a href="{rel}daten.html">Daten (CSV)</a><a href="{rel}impressum.html">Impressum</a><a href="{rel}datenschutz.html">Datenschutz</a></span></footer>
</div>
</body>
</html>
"""

JSONLD = ""  # wird in main() mit aktuellen Werten gefüllt
OGDESC = "Versprochen. Gehalten? Wie viel die Parteien von ihrem Wahlprogramm umgesetzt haben – jede Zusage gegen geltendes Recht geprüft, Monat für Monat."
OGALT = "DeliverPolitics – Delivery Index"
FONTS = {"serif": "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
         "sb": "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf",
         "rg": "/usr/share/fonts/opentype/inter/Inter-Regular.otf"}

def og_bild(ziel, eintraege, stand):
    """Vorschaubild 1200×630 für geteilte Links. eintraege: [(Name, Prozent gerundet, k, n)]. Gibt False zurück, wenn Pillow oder Schriften fehlen."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        F = lambda k, sz: ImageFont.truetype(FONTS[k], sz)
        F("serif", 10); F("sb", 10); F("rg", 10)
    except Exception:
        return False
    W, H = 1200, 630
    BG, INK, MUT, LINE, OK = "#F6F7F7", "#16191C", "#5F6A72", "#DEE3E6", "#28695E"
    im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 10], fill=OK)
    d.text((72, 58), "DELIVERPOLITICS", font=F("serif", 30), fill=INK)
    d.text((72, 110), "Versprochen. Gehalten?", font=F("serif", 62), fill=INK)
    d.text((72, 192), "Wie viel ist umgesetzt? Delivery Index, 21. Wahlperiode", font=F("rg", 28), fill=MUT)
    x0, bw, gap = 72, 495, 66
    for i, (name, pr, k, n) in enumerate(eintraege[:2]):
        x = x0 + i * (bw + gap); y = 268
        d.rectangle([x, y, x + bw, y + 262], fill="#FFFFFF", outline=LINE, width=2)
        d.text((x + 32, y + 26), name, font=F("serif", 36), fill=INK)
        d.text((x + 32, y + 72), f"{pr} %", font=F("sb", 96), fill=INK)
        by = y + 196; d.rectangle([x + 32, by, x + bw - 32, by + 12], fill=LINE)
        d.rectangle([x + 32, by, x + 32 + round((bw - 64) * k / n), by + 12], fill=OK)
        d.text((x + 32, by + 24), f"{k} von {n} Zusagen erfüllt", font=F("rg", 24), fill=MUT)
    d.text((72, 562), f"Stand {stand} · jede Zusage mit Prüfmaßstab und Quelle", font=F("rg", 24), fill=MUT)
    t = DOMAIN; tw = d.textlength(t, font=F("sb", 24)); d.text((W - 72 - tw, 562), t, font=F("sb", 24), fill=OK)
    im.save(ziel, optimize=True)
    return True

def _umbruch(d, text, font, breite):
    zeilen, z = [], ""
    for w in text.split():
        t = (z + " " + w).strip()
        if d.textlength(t, font=font) <= breite: z = t
        else: zeilen.append(z); z = w
    if z: zeilen.append(z)
    return zeilen

def befund_bild(ziel, b, punkte, idx, fmt):
    """Grafik zu einem Befund. fmt: 'quadrat' 1080×1080, 'story' 1080×1920, 'quer' 1200×630.
    idx: [(Name, Prozent gerundet, Anteil 0–1)] in Reihenfolge der Darstellung."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        F = lambda k, sz: ImageFont.truetype(FONTS[k], round(sz))
        F("serif", 10); F("sb", 10); F("rg", 10)
    except Exception:
        return False
    W, H = {"quadrat": (1080, 1080), "story": (1080, 1920), "quer": (1200, 630)}[fmt]
    BG, INK, MUT, LINE, OK = "#F6F7F7", "#16191C", "#5F6A72", "#DEE3E6", "#28695E"
    quer = fmt == "quer"
    k = {"quadrat": 1.0, "story": 1.3, "quer": 0.7}[fmt]
    M = 72 if not quer else 72
    im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 12], fill=OK)
    # Kopf
    yk = 64 if fmt != "story" else 120
    d.text((M, yk), "DELIVERPOLITICS", font=F("serif", 30 if not quer else 26), fill=INK)
    lab = f"SPOTLIGHT · {b['monat'].upper()}"; f_l = F("sb", 24 if not quer else 21)
    d.text((W - M - d.textlength(lab, font=f_l), yk + 4), lab, font=f_l, fill=OK)
    # Fuß: Indexwerte mit Balken
    f_n, f_v, f_u = F("sb", 26 * min(k, 1.15) if not quer else 20), F("sb", 26 * min(k, 1.15) if not quer else 20), F("sb", 28 * min(k, 1.15) if not quer else 22)
    if quer:
        yb = H - 70
        d.line([(M, yb - 22), (W - M, yb - 22)], fill=LINE, width=2)
        d.text((M, yb), "Delivery Index: " + " · ".join(f"{n} {pr} % (Kern {kp} %)" for n, pr, _, kp in idx), font=F("rg", 21), fill=INK)
        d.text((W - M - d.textlength(DOMAIN, font=f_u), yb), DOMAIN, font=f_u, fill=OK)
        fuss_oben = yb - 40
    else:
        zh = round(f_n.size * 2.4)
        yb = H - (64 if fmt == "quadrat" else 260) - len(idx) * zh - round(f_u.size * 1.6)
        d.line([(M, yb - 28), (W - M, yb - 28)], fill=LINE, width=2)
        y = yb
        lw = d.textlength("CDU/CSU", font=f_n) + 24
        for n, pr, ant, kp in idx:
            d.text((M, y), n, font=f_n, fill=INK)
            bx0, bx1 = M + lw, W - M - d.textlength("100 %  ·  Kern 100 %", font=f_v) - 20
            by = y + f_n.size * 0.35
            d.rectangle([bx0, by, bx1, by + 12], fill=LINE); d.rectangle([bx0, by, bx0 + (bx1 - bx0) * ant, by + 12], fill=OK)
            t = f"{pr} %  ·  Kern {kp} %"; d.text((W - M - d.textlength(t, font=f_v), y), t, font=f_v, fill=INK)
            y += zh
        d.text((M, y - zh * 0.2), "Delivery Index (Balken: Gesamtprogramm) · " + DOMAIN, font=F("sb", f_u.size * 0.8), fill=OK)
        fuss_oben = yb - 28
    # Inhalt: erst messen, dann vertikal mittig zwischen Kopf und Fuß
    viele = len(punkte) > 2
    sk = (0.75 if not quer else 0.8) if viele else 1.0  # ab 3 Punkten kleiner und zweispaltig
    f_h = F("serif", (76 * k if not quer else 56) * (0.8 if viele else 1))
    f_t, f_x, f_p = F("sb", (36 * k if not quer else 30) * sk), F("rg", (28 * k if not quer else 22) * sk), F("sb", (22 * k if not quer else 17) * sk)
    r = round((26 * k if not quer else 20) * sk)
    spalten = 2 if (quer or viele) else 1
    sw = (W - 2 * M - (spalten - 1) * 40) // spalten
    def zeichne(d, y):
        for z in _umbruch(d, b["titel"], f_h, W - 2 * M):
            d.text((M, y), z, font=f_h, fill=INK); y += round(f_h.size * 1.12)
        y += round(34 * k); y0 = y; yend = y; zeile_ende = y
        for i, (pt, partei) in enumerate(punkte):
            if spalten == 2 and i % 2 == 0 and i > 0:
                y0 = zeile_ende + round(30 * k * sk)
            x = M + (i % spalten) * (sw + 40)
            yy = y0 if spalten == 2 else y
            cx, cy = x + r, yy + r
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=OK)
            d.line([(cx - r * .45, cy + r * .02), (cx - r * .1, cy + r * .38), (cx + r * .48, cy - r * .35)], fill="white", width=max(3, round(r * .22)), joint="curve")
            tx = x + 2 * r + round(22 * k if not quer else 14); tw = x + sw - tx
            d.text((tx, yy - 2), partei.upper(), font=f_p, fill=OK); yy += round(f_p.size * 1.5)
            for z in _umbruch(d, pt["titel"], f_t, tw):
                d.text((tx, yy), z, font=f_t, fill=INK); yy += round(f_t.size * 1.2)
            yy += 6
            for z in _umbruch(d, pt["text"], f_x, tw):
                d.text((tx, yy), z, font=f_x, fill=MUT); yy += round(f_x.size * 1.35)
            yend = max(yend, yy); zeile_ende = max(zeile_ende, yy)
            if spalten == 1: y = yy + round(44 * k)
        return yend
    kopf_unten = yk + (70 if not quer else 50)
    hoehe = zeichne(ImageDraw.Draw(Image.new("RGB", (W, H))), 0)
    ystart = kopf_unten + max(0, (fuss_oben - kopf_unten - hoehe) // 2)
    zeichne(d, ystart)
    im.save(ziel, optimize=True)
    return True

def lauf(MONTH, OUT, EXTERN):
    """Erzeugt die Seiten des eingestellten Parlaments. Hauptlauf (Bund): ganze Website; EXTERN = Ergebnisse der übrigen Parlamente.
    Lauf für ein weiteres Parlament: nur dessen Ordner; gibt Kennzahlen für Startseite, Länderseite und Methodik zurück."""
    ST = f"{MONTH}-{calendar.monthrange(int(MONTH[:4]), int(MONTH[5:]))[1]:02d}"; STD = de(ST)
    if os.path.exists(OUT): shutil.rmtree(OUT)
    for sub in ("assets", "vorhaben", "daten", "programme"): os.makedirs(os.path.join(OUT, sub))
    fehlende_pdf = []
    for cfg in IDX.values():  # Kopien der Wahlprogramme aus <BASE>/programme/
        quelle = os.path.join(BASE, cfg["pdf"])
        os.makedirs(os.path.dirname(os.path.join(OUT, cfg["pdf"])), exist_ok=True)
        if os.path.exists(quelle): shutil.copyfile(quelle, os.path.join(OUT, cfg["pdf"]))
        else: fehlende_pdf.append(cfg["pdf"])
    open(os.path.join(OUT, "assets/style.css"), "w", encoding="utf-8").write(CSS.strip() + "\n")
    items, tzs, ih, kh = load()
    # nur das eingestellte Parlament
    ixids = {c["index_id"] for c in IDX.values()}
    items = [i for i in items if i["index_id"] in ixids]; iset = {i["item_id"] for i in items}
    tzs = [t for t in tzs if t["item_id"] in iset]
    kh = {k: v for k, v in kh.items() if k[0] in ixids or (k[0].endswith("-KERN") and k[0][:-5] in ixids)}
    KERNSET = {k["tz_id"] for k in csv.DictReader(open(os.path.join(D, "kernversprechen.csv"), encoding="utf-8"))}
    def kmark(tid): return '<span class="typ kern" title="Kernversprechen">Kern</span>' if tid in KERNSET else ""
    # Einheitlicher Statusbalken (Nr. 34): höchstens vier Abschnitte (erfüllt, beschlossen, offen, gebrochen);
    # Mouseover, Antippen oder Tab-Fokus zeigt die Zusagen des Abschnitts als Liste mit Links (nur CSS).
    GRUPPEN_B = [("ok", "erfüllt"), ("be", "beschlossen, gilt noch nicht"), ("", "offen"), ("br", "gebrochen oder Frist verfehlt")]
    def zrows(tl):
        return [(t["tz_id"], t["text_de"]) + status(t, ST) for t in tl]
    def zlink_tz(tid, rel=""):
        it = tid.rsplit("-", 1)
        return f'{rel}vorhaben/{it[0].lower()}.html#{it[1].lower()}'
    def gbalken(rows, h=14, rel=""):
        n = len(rows)
        if not n: return f'<span class="gbar" style="height:{h}px"><span class="gseg of" style="flex:1 1 0"></span></span>'
        segs, pos, zus = [], 0, []
        for cl, lab in GRUPPEN_B:
            g = [r for r in rows if r[3] == cl]
            if not g: continue
            mitte = (pos + len(g) / 2) / n; pos += len(g); zus.append(f"{len(g)} {lab}")
            li = "".join(f'<span class="gli"><a href="{zlink_tz(tid, rel)}">{e(txt)}</a>' + (f' <span class="gst">· {e(st)}</span>' if cl else "") + "</span>" for tid, txt, st, _ in g)
            segs.append(f'<span class="gseg {cl or "of"}{" r" if mitte > 0.5 else ""}" style="flex:{len(g)} 1 0" tabindex="0" aria-label="{len(g)} {lab}: Liste anzeigen">'
                        f'<span class="gpop"><span class="gin"><b>{len(g)} {lab}</b>{li}</span></span></span>')
        return f'<span class="gbar" style="height:{h}px" role="group" aria-label="{e(", ".join(zus))}">{"".join(segs)}</span>'
    months = sorted({m for (_, m) in kh if m <= MONTH})
    stat = {}; BELEG = {}
    # beste amtliche Quelle je Teilzusage (für den Link am Beleg)
    RANG = {"bgbl": 0, "drucksache": 1, "amtlich": 2}
    QURL = {}
    for r in sorted(csv.DictReader(open(os.path.join(D, "quellen.csv"), encoding="utf-8-sig")), key=lambda r: RANG.get(r["art"], 9)):
        if r["url"] and r["art"] in RANG: QURL.setdefault(r["tz_id"], (r["url"], r["fundstelle"]))
    def qlink(tid):
        if tid not in QURL: return ""
        u, f = QURL[tid]
        return f' <a href="{e(u)}" rel="noopener" style="white-space:nowrap">{e(f or "Quelle")} ↗</a>'
    for p, cfg in IDX.items():
        k = kh[(cfg["index_id"], MONTH)]
        mine = [t for t in tzs if t["item_id"].startswith(p + "-")]
        c = collections.Counter(); brl = []; okl = []; bel = []
        for t in mine:
            s, cl = status(t, ST); c[cl] += 1
            if cl == "br": brl.append((t, s))
            if cl == "ok": okl.append((t, s))
            if cl == "be": bel.append((t, s))
            if t["typ_zusage"] == "Bestand": c["B"] += 1
            if t["typ_zusage"] == "Bestand" and cl == "ok": c["Bok"] += 1
        stat[p] = dict(tl=mine, kpi=float(k["actual_exact"]), rund=k["actual"], n=len(mine), k=int(k["erfuellt"]), items=int(k["items"]), c=c, br=brl, ok=okl, be=bel,
                       start=float(kh[(cfg["index_id"], months[0])]["actual_exact"]), status=k["status"])

    # Reihenfolge: führende Partei (höherer Index) zuerst
    ORD = sorted(IDX, key=lambda q: -stat[q]["kpi"])
    global LEAD_SLUG; LEAD_SLUG = IDX[ORD[0]]["slug"] + ".html"
    # Strukturierte Daten (schema.org) für Suchmaschinen: Website-Name, Schreibweisen, Datensatz
    global JSONLD
    ld = [{"@context": "https://schema.org", "@type": "WebSite", "name": "DeliverPolitics",
           "alternateName": ["Deliver Politics", "DeliverPolitics Delivery Index", "Delivery Index"],
           "url": f"https://{DOMAIN}/", "inLanguage": "de"},
          {"@context": "https://schema.org", "@type": "Dataset", "name": "Delivery Index – Umsetzung der Wahlprogramme von SPD und CDU/CSU (21. Wahlperiode)",
           "alternateName": "DeliverPolitics Delivery Index",
           "description": "Monatlicher Index, wie viele Zusagen aus den Wahlprogrammen 2025 von SPD und CDU/CSU umgesetzt sind – jede Teilzusage mit Prüfmaßstab und amtlichem Beleg; dazu ein zweiter Index für die Kernversprechen, die die Parteien selbst herausgestellt haben. " + ", ".join(f"{IDX[q]['name']} {pct(stat[q]['kpi'])} %" for q in ORD) + f" (Stand {STD}).",
           "url": f"https://{DOMAIN}/", "inLanguage": "de", "creator": {"@type": "Person", "name": "Hajo Warmbier"},
           "temporalCoverage": f"2025-02-23/{ST}", "spatialCoverage": "Deutschland", "isAccessibleForFree": True,
           "keywords": ["Wahlversprechen", "Wahlprogramm", "Bundestag", "SPD", "CDU/CSU", "Umsetzung", "Delivery Index"],
           "distribution": [{"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": f"https://{DOMAIN}/daten/{f}"} for f in ("teilzusagen.csv", "kpi_history.csv", "kernversprechen.csv")]}]
    JSONLD = "".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in ld)

    _LS = ['stroke-width="2.5"', 'stroke-width="2" stroke-dasharray="5 4"', 'stroke-width="2" stroke-dasharray="1 4"']
    _PS = ['stroke-width="2.5"', 'stroke-width="2" stroke-dasharray="6 5"', 'stroke-width="2" stroke-dasharray="1 4"']
    STYLE = {q: _LS[i % 3] for i, q in enumerate(IDX)}; PSTYLE = {q: _PS[i % 3] for i, q in enumerate(IDX)}

    def kpicard(p, link=True, size=72):
        cfg, s = IDX[p], stat[p]
        inner = f"""<div style="display:flex;justify-content:space-between;gap:12px"><span class="label">Delivery Index</span><span class="mono" style="font-size:12px;color:var(--mut)">Stand {STD}</span></div>
<div style="display:flex;align-items:baseline;gap:16px;margin-top:12px;flex-wrap:wrap"><span class="big xl" style="font-size:{size}px">{s['rund']} %</span><span class="mono" style="font-size:13px;color:var(--mut)">{s['k']} von {s['n']} Teilzusagen erfüllt</span></div>
<div class="serif" style="font-size:24px;font-weight:600;margin-top:16px">{e(cfg['name'])}</div>
<div style="font-size:14px;color:var(--ink2);margin-top:4px">{proglink(cfg)} · vollständige Fassung</div>
<div class="facts" style="margin-top:16px;padding-top:12px;border-top:1px solid var(--line)"><span>{s['n']} Teilzusagen</span><span>{s['c']['ok']} erfüllt, davon {s['c']['Bok']} Bestand</span><span>{s['c']['be']} beschlossen, noch nicht geltend</span><span><a class="brlink" href="{cfg['slug']}.html#gebrochen">{s['c']['br']} gebrochen oder Frist verfehlt</a></span></div>"""
        if link:
            # schlanke Karte für die Startseite
            w = round(100 * s['k'] / s['n'], 1)
            br = (f'<a class="brlink" href="{cfg["slug"]}.html#gebrochen">{s["c"]["br"]} gebrochen oder Frist verfehlt</a>' if s['c']['br'] else '')
            return f'''<div class="card"><div class="serif" style="font-size:24px;font-weight:600">{e(cfg['name'])}</div>
<div class="big xl" style="font-size:{size}px;margin-top:10px">{s['rund']} %</div>
<div style="height:8px;background:var(--line);margin-top:16px" aria-hidden="true"><div style="width:{w}%;height:100%;background:var(--ok)"></div></div>
<div style="display:flex;flex-wrap:wrap;justify-content:space-between;gap:4px 16px;margin-top:10px;font-size:14.5px;color:var(--ink2)"><a href="{cfg["slug"]}.html#erfuellt">{s['k']} von {s['n']} Zusagen erfüllt</a>{br}</div>
<div style="margin-top:18px;font-size:14.5px"><a href="{cfg["slug"]}.html">Zum Index →</a></div></div>'''
        # Karte auf der Indexseite: Statusbalken über das ganze Programm
        c = s['c']; offen = s['n'] - c['ok'] - c['be'] - c['br']
        seg = [(c['ok'], 'var(--ok)'), (c['be'], 'var(--be)'), (offen, 'var(--line)'), (c['br'], 'var(--br)')]
        balken = "".join(f'<span style="flex:{n} 1 0;background:{col}"></span>' for n, col in seg if n)
        leg = lambda n, col, txt, href: (f'<span style="display:inline-flex;align-items:center;gap:7px"><span style="width:10px;height:10px;background:{col}"></span>'
                                         + (f'<a href="{href}">{n} {txt}</a>' if href else f'{n} {txt}') + '</span>')
        legende = "".join([leg(c['ok'], 'var(--ok)', f"erfüllt (davon {c['Bok']} Bestand)", '#erfuellt'),
                           leg(c['be'], 'var(--be)', 'beschlossen, gilt noch nicht', '#beschlossen' if c['be'] else ''),
                           leg(offen, 'var(--line2)', 'offen', ''),
                           leg(c['br'], 'var(--br)', 'gebrochen oder Frist verfehlt', '#gebrochen' if c['br'] else '')])
        return f'''<div class="card"><div style="display:flex;justify-content:space-between;gap:12px"><span class="label">Delivery Index</span><span style="font-size:12.5px;color:var(--mut)">Stand {STD}</span></div>
<div style="display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;margin-top:12px"><span class="big xl" style="font-size:{size}px">{s['rund']} %</span><span style="font-size:14.5px;color:var(--ink2)">{s['k']} von {s['n']} Zusagen erfüllt</span></div>
<div style="margin-top:18px">{gbalken(zrows(s['tl']), 12)}</div>
<div style="display:flex;flex-direction:column;gap:5px;margin-top:14px;font-size:14px;color:var(--ink2)">{legende}</div></div>'''

    def bestand_note(p):
        o = "SPD" if p == "CDU" else "CDU"
        s, so = stat[p], stat[o]
        return (f"„Bestand“ = Zusage, einen Zustand zu erhalten oder etwas fortzuführen („bleibt“, „wird fortgesetzt“, „kein …“). Sie zählt ab dem Wahltag als erfüllt, solange kein geltender Rechtsakt den Zustand ändert; ein Bruch ist endgültig (E23, E32, E33). "
                f"{s['c']['B']} von {s['n']} Teilzusagen ({round(100 * s['c']['B'] / s['n'])} %) sind Bestandszusagen; sie tragen den Startwert von {pct(s['start'])} % im Februar 2025 "
                f"({IDX[o]['name']}: {round(100 * so['c']['B'] / so['n'])} %, Start {pct(so['start'])} %).")

    # ---------- Vorhaben-Seiten und Index-Seiten
    changes = collections.defaultdict(list)
    for p, cfg in IDX.items():
        rows = []
        # Rang nach Anteil (für die sortierte Ansicht ohne JavaScript)
        mi_ = [i for i in items if i["item_id"].startswith(p + "-")]
        rang = {i["item_id"]: r for r, i in enumerate(sorted(mi_, key=lambda i: (
            -(float(ih[(i["item_id"], MONTH)]["value"]) if i["status"] == "aktiv" else -1),
            -(int(ih[(i["item_id"], MONTH)]["erfuellt"]) if i["status"] == "aktiv" else 0), i["item_id"])))}
        for it in mi_:
            iid = it["item_id"]; slug = iid.lower()
            tl = [t for t in tzs if t["item_id"] == iid]
            if it["status"] != "aktiv":
                rows.append(f"""<details class="v" style="--o:{rang[iid]}"><summary><span class="id" style="color:var(--mut)">{e(iid)}</span><span style="font-size:16px;font-weight:500">{e(it['title_de'])}</span><span class="mono" style="font-size:13.5px">–</span><span>{meter(None)} <span class="mono" style="font-size:13px">ausgeschlossen</span></span><span class="sign mono" aria-hidden="true"></span></summary>
<div class="vbody"><p style="font-size:14.5px;color:var(--ink2)">{e(it['justification_de'] or 'Kapitel ohne wertbare Zusage.')} ({e(it['fundstelle'])})</p></div></details>""")
                continue
            h = ih[(iid, MONTH)]; v = float(h["value"])
            tzrows, cards, prev = [], [], ""
            for t in tl:
                s, cl = status(t, ST); n = t["tz_id"].rsplit("-", 1)[1]
                typ = '<span class="typ">Bestand</span>' if t["typ_zusage"] == "Bestand" else ""
                tzrows.append(f'<div class="tz {cl}"><span class="id" style="color:var(--mut)">{n}</span><span>{e(t["text_de"])}{typ}{kmark(t["tz_id"])}</span><span class="st">{e(s)}</span></div>')
                b = beleg(t, prev); prev = b.split(";")[0] if not b.startswith("Kein") else prev
                BELEG[t["tz_id"]] = b
                cards.append(f"""<details class="tzd {cl}" id="{n.lower()}"><summary><span class="id" style="color:var(--mut)">{n}</span>
<span><span style="font-size:15.5px;font-weight:500">{e(t['text_de'])}{typ}{kmark(t['tz_id'])}</span><br><span style="font-size:13.5px;color:var(--mut)">{e(b)}{qlink(t["tz_id"])}</span></span>
<span class="st">{e(s)}</span><span class="sign" aria-hidden="true"></span></summary>
<div class="tzbody"><span class="label">Prüfmaßstab</span> {e(t['pruefmassstab'][:1].upper() + t['pruefmassstab'][1:])}</div></details>""")
                # Änderungen
                if t["typ_zusage"] == "Handlung" and t["erfuellt_ab"] and t["erfuellt_ab"] <= ST:
                    changes[t["erfuellt_ab"][:7]].append((t["erfuellt_ab"], t["tz_id"], t["text_de"], "erfüllt", b))
                if t["entfallen_ab"] and t["entfallen_ab"] <= ST:
                    changes[t["entfallen_ab"][:7]].append((t["entfallen_ab"], t["tz_id"], t["text_de"], "dauerhaft gebrochen" if t["typ_zusage"] == "Bestand" else "entfallen", b))
            rows.append(f"""<details class="v" id="{slug}" style="--o:{rang[iid]}"><summary><span class="id" style="color:var(--mut)">{e(iid)}</span><span style="font-size:16px;font-weight:500">{e(it['title_de'])}</span><span class="mono" style="font-size:13.5px">{h['erfuellt']} von {h['gesamt']}</span><span><span class="gw" style="width:72px">{gbalken(zrows(tl), 8)}</span> <span class="mono" style="font-size:13.5px">{num(v)}</span></span><span class="sign mono" aria-hidden="true"></span></summary>
<div class="vbody"><div class="label tz" style="border-bottom:1px solid var(--line)"><span>TZ</span><span>Teilzusage</span><span>Status am {STD}</span></div>{''.join(tzrows)}
<p style="margin:14px 0 0;font-size:14px"><a href="vorhaben/{slug}.html">Prüfmaßstäbe, Belege und Zitierhilfe</a></p></div></details>""")
            # Vorhaben-Seite
            hist = [float(ih[(iid, m)]["value"]) for m in months]
            nh = len(hist)
            pts = " ".join(f"{k * 100 / nh:.2f},{48 - x * 46:.2f} {(k + 1) * 100 / nh:.2f},{48 - x * 46:.2f}" for k, x in enumerate(hist))
            spark = (f'<svg viewBox="0 0 100 50" preserveAspectRatio="none" style="width:100%;height:50px;display:block;border-bottom:1px solid var(--line2)" role="img" aria-label="Verlauf des Kapitelwerts von {num(hist[0])} ({mlabel(months[0])}) auf {num(hist[-1])} ({mlabel(MONTH)})">'
                     f'<line x1="0" y1="2" x2="100" y2="2" stroke="#E6EAEC" vector-effect="non-scaling-stroke"></line>'
                     f'<polygon points="0,48 {pts} 100,48" fill="var(--ok)" fill-opacity=".12"></polygon>'
                     f'<polyline points="{pts}" fill="none" stroke="var(--ok)" stroke-width="2" vector-effect="non-scaling-stroke"></polyline></svg>')
            body = f"""<nav class="crumb" aria-label="Pfad"><a href="../gesamtprogramm.html">Gesamtprogramm</a><span>/</span><a href="../{cfg['slug']}.html">{e(cfg['name'])}</a><span>/</span><span style="color:var(--ink)">{e(iid)}</span></nav>
<section class="grid2" style="padding-top:26px;align-items:start">
<div><div class="label">Vorhaben {e(iid)} · {e(it['fundstelle'])}</div><h1 class="serif" style="font-size:38px;line-height:1.1;margin:10px 0 12px">{e(it['title_de'])}</h1>
<p class="lead" style="font-size:15.5px">{len(tl)} Teilzusagen{(lambda b: '' if b == 0 else f', davon {b} Bestandszusage' + ('' if b == 1 else 'n'))(sum(1 for t in tl if t['typ_zusage'] == 'Bestand'))}. Stand {STD}: {h['erfuellt']} von {h['gesamt']} erfüllt.</p></div>
<div class="plain"><div style="display:flex;justify-content:space-between;gap:12px"><span class="label">Erfüllt im Kapitel</span><span class="mono" style="font-size:12px;color:var(--mut)">Stand {STD}</span></div>
<div style="display:flex;align-items:center;gap:16px;margin-top:12px"><span class="big" style="font-size:52px">{num(v)}</span><span class="gw" style="flex:1;max-width:240px">{gbalken(zrows(tl), 12, "../")}</span></div>
<div style="margin-top:18px">{spark}</div>
<div class="mono" style="display:flex;justify-content:space-between;font-size:11px;color:var(--mut);margin-top:4px"><span>{mlabel(months[0])}</span><span>{mlabel(MONTH)}</span></div></div>
</section>
<section style="margin-top:64px"><div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:8px 16px;margin-bottom:14px"><h2 class="serif" style="font-size:24px">Teilzusagen und Belege</h2><span style="font-size:14px;color:var(--mut)">Zeile öffnen: Prüfmaßstab.</span></div>
<div style="border-top:1px solid var(--line2)">{''.join(cards)}</div>
<p class="note" style="margin-top:14px">Prüfmaßstäbe wurden vor der Recherche festgelegt (E22, E24). Maßgeblich ist, ab wann eine Vorschrift gilt, nicht der Beschluss (E14). Programmstelle: {proglink(cfg, '../')}, {e(it['fundstelle'])}.</p></section>
<section id="zitieren" class="plain" style="margin-top:64px"><div class="label">Zitierhilfe</div>
<p class="mono" style="font-size:13.5px;margin:10px 0 0">DeliverPolitics ({MONTH[:4]}): {e(cfg['name'])}, Vorhaben {e(iid)} „{e(it['title_de'])}“, Wert {num(v)} ({h['erfuellt']} von {h['gesamt']} Teilzusagen erfüllt). Stand {STD}. {DOMAIN}/{PDIR}/vorhaben/{slug}.html</p></section>"""
            open(os.path.join(OUT, "vorhaben", slug + ".html"), "w", encoding="utf-8").write(page(f"{iid} {it['title_de']}", body, "../", "vorhaben"))
        other = "SPD" if p == "CDU" else "CDU"
        gebrochen_html = "".join(
            f'<div class="tz br" style="grid-template-columns:110px minmax(0,1fr) 250px"><a class="id" href="vorhaben/{t["item_id"].lower()}.html#{t["tz_id"].rsplit("-", 1)[1].lower()}">{e(t["tz_id"].rsplit("-", 1)[0] + " " + t["tz_id"].rsplit("-", 1)[1])}</a>'
            f'<span>{e(t["text_de"])}{" <span class=typ>Bestand</span>" if t["typ_zusage"] == "Bestand" else ""}{kmark(t["tz_id"])}<br><span style="font-size:13px;color:var(--mut)">{e(beleg(t, ""))}</span></span><span class="st">{e(st_)}</span></div>'
            for t, st_ in stat[p]["br"]) or '<p class="note">Keine.</p>'
        def tzliste(lst, cl):
            return "".join(
                f'<div class="tz {cl}" style="grid-template-columns:110px minmax(0,1fr) 250px"><a class="id" href="vorhaben/{t["item_id"].lower()}.html#{t["tz_id"].rsplit("-", 1)[1].lower()}">{e(t["tz_id"].rsplit("-", 1)[0] + " " + t["tz_id"].rsplit("-", 1)[1])}</a>'
                f'<span>{e(t["text_de"])}{kmark(t["tz_id"])}<br><span style="font-size:13px;color:var(--mut)">{e(BELEG.get(t["tz_id"], ""))}{qlink(t["tz_id"])}</span></span><span class="st">{e(st_)}</span></div>' for t, st_ in lst)
        okh = sorted([x for x in stat[p]["ok"] if x[0]["typ_zusage"] == "Handlung"], key=lambda x: (x[0]["erfuellt_ab"], x[0]["tz_id"]), reverse=True)
        okb = sorted([x for x in stat[p]["ok"] if x[0]["typ_zusage"] == "Bestand"], key=lambda x: x[0]["tz_id"])
        erfuellt_html = f"""<section id="erfuellt" style="margin-top:64px"><h2 class="serif" style="font-size:26px">Erfüllt</h2>
<p class="note" style="margin-top:6px">{len(okh)} Teilzusagen durch Handeln erfüllt, neueste zuerst; dazu {len(okb)} erfüllte Bestandszusagen (E23).</p>
<div style="margin-top:12px;border-top:1px solid var(--line2)">{tzliste(okh, "ok")}</div>
<details style="margin-top:8px"><summary style="cursor:pointer;padding:12px 0;font-size:15px;color:var(--acc)">{len(okb)} erfüllte Bestandszusagen anzeigen</summary>
<div style="border-top:1px solid var(--line2)">{tzliste(okb, "ok")}</div></details></section>"""
        bes = sorted(stat[p]["be"], key=lambda x: (x[0]["erfuellt_ab"] or "9999", x[0]["tz_id"]))
        beschlossen_html = f"""<section id="beschlossen" style="margin-top:64px"><h2 class="serif" style="font-size:26px">Beschlossen, noch nicht geltend</h2>
<p class="note" style="margin-top:6px">Diese Teilzusagen zählen erst ab dem Tag, an dem die Vorschrift gilt (E14); nächste zuerst.</p>
<div style="margin-top:12px;border-top:1px solid var(--line2)">{tzliste(bes, "be") or '<p class="note">Keine.</p>'}</div></section>"""
        body = f"""<nav class="crumb" aria-label="Pfad"><a href="gesamtprogramm.html">Gesamtprogramm</a><span>/</span><span style="color:var(--ink)">{e(cfg['name'])}</span></nav>
<section class="grid2" style="padding-top:28px;align-items:center">
<div><div class="label">Gesamtprogramm</div><h1 class="serif hero" style="font-size:48px;line-height:1.05;margin:6px 0 10px">{e(cfg['name'])}</h1><p class="lead" style="font-size:16px">{proglink(cfg)}</p>
<div style="display:flex;gap:8px;margin-top:18px">{''.join(f'<a class="btn{" on" if q == p else ""}" href="{IDX[q]["slug"]}.html"{" aria-current=page" if q == p else ""}>{IDX[q]["name"]}</a>' for q in ORD)}</div></div>
{kpicard(p, link=False, size=64)}
</section>
<section style="margin-top:64px"><div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:8px 16px"><h2 class="serif" style="font-size:26px">Vorhaben</h2><span style="font-size:14px;color:var(--mut)">Zeile öffnen: Teilzusagen mit Status am Stichtag.{' <span class="typ kern">Kern</span> = Kernversprechen.' if KERN else ''}</span></div>
<input type="radio" name="sort" id="s-kap" class="sr" checked><input type="radio" name="sort" id="s-ant" class="sr">
<div class="sortbar" role="group" aria-label="Sortierung"><span>Sortieren:</span><label for="s-kap">nach Kapitel</label><label for="s-ant">nach Anteil</label></div>
<div class="scroll" style="margin-top:10px;border-top:1px solid var(--line2)"><div style="min-width:680px">
<div class="label thead"><span>Nr.</span><span>Kapitel</span><span>Erfüllt</span><span>Anteil</span><span></span></div>
<div class="vlist">{''.join(rows)}</div>
</div></div>
<p class="note" style="margin-top:14px">Welche Programmteile zählen und wie Bestandszusagen bewertet werden, steht unter <a href="methodik.html#programmgrundlage">So messen wir</a>.</p></section>
<section id="gebrochen" style="margin-top:64px"><h2 class="serif" style="font-size:26px">Gebrochen oder Frist verfehlt</h2>
<p class="note" style="margin-top:6px">Diese Teilzusagen gelten dauerhaft als nicht erfüllt, auch wenn sie später noch umgesetzt werden (E21, E23).</p>
<div style="margin-top:12px;border-top:1px solid var(--line2)">{gebrochen_html}</div></section>
{erfuellt_html}
{beschlossen_html}
<section class="grid2" style="margin-top:64px">
<div class="plain"><div class="label">Daten</div><p style="font-size:14.5px;color:var(--ink2)">Alle Vorhaben, Teilzusagen, Prüfmaßstäbe und Quellen als CSV.</p><a href="daten.html">Zu den Daten</a></div>
<div class="plain"><div class="label">Zitierhilfe</div><p class="mono" style="font-size:13px;margin:10px 0 0">DeliverPolitics ({MONTH[:4]}): Delivery Index {e(cfg['name'])}, {e(PARL['name'])}, {PARL['wahlperiode']}. Wahlperiode. Stand {STD}. {DOMAIN}/{PDIR}/{cfg['slug']}.html</p></div>
</section>"""
        open(os.path.join(OUT, cfg["slug"] + ".html"), "w", encoding="utf-8").write(page(f"Gesamtprogramm {cfg['name']}", body, "", cfg["slug"] + ".html"))

    # ---------- Verlauf (SVG)
    def mi(m): return (int(m[:4]) - int(months[0][:4])) * 12 + int(m[5:]) - int(months[0][5:])
    NM = mi(ENDE_WP) + 1  # Monate auf der Achse
    X = lambda k: k * 640 / NM
    def poly(i):
        pts = []
        for k, m in enumerate(months):
            y = 160 - float(kh[(i, m)]["actual_exact"]) * 1.6
            pts += [f"{X(k):.1f},{y:.1f}", f"{X(k + 1):.1f},{y:.1f}"]
        return " ".join(pts)
    xstand = X(len(months))
    tickm = [months[0]] + [f"{y}-01" for y in range(int(months[0][:4]) + 1, int(ENDE_WP[:4]))] + [ENDE_WP]
    ticks = "".join(f'<span style="position:absolute;left:{100 * X(mi(m)) / 640:.2f}%;transform:translateX({"0" if j == 0 else ("-100%" if j == len(tickm) - 1 else "-50%")});white-space:nowrap">{f"{int(m[5:])}/{m[:4]}" if j in (0, len(tickm) - 1) else m[:4]}</span>' for j, m in enumerate(tickm))
    H = 160
    def verlauf(titel, ids, werte, notiz="", hl=3):
        # ids: Partei -> index_id; werte: Partei -> (start, kpi, rund)
        lab = sorted(((H * (1 - werte[q][1] / 100), q) for q in ORD))
        if len(lab) == 2 and lab[1][0] - lab[0][0] < 20:
            mid = (lab[0][0] + lab[1][0]) / 2; lab = [(mid - 10, lab[0][1]), (mid + 10, lab[1][1])]
        labels = "".join(f'<span style="position:absolute;left:calc({100 * xstand / 640:.2f}% + 10px);top:{y:.0f}px;transform:translateY(-50%);display:inline-flex;align-items:center;gap:6px;font-size:13.5px;white-space:nowrap"><svg width="18" height="8" aria-hidden="true"><line x1="0" y1="4" x2="18" y2="4" stroke="#16191C" {STYLE[q]}></line></svg><b style="font-weight:600">{IDX[q]["name"]}</b> {werte[q][2]} %</span>' for y, q in lab)
        aria = ", ".join(f"{IDX[q]['name']} von {pct(werte[q][0])} % auf {pct(werte[q][1])} %" for q in ORD)
        linien = "\n".join(f'<polyline fill="none" stroke="#16191C" {PSTYLE[q]} vector-effect="non-scaling-stroke" points="{poly(ids[q])}"></polyline>' for q in IDX)
        return f"""<div class="plain"><h{hl} class="serif" style="font-size:20px">{titel}</h{hl}>
<div style="display:grid;grid-template-columns:40px 1fr;gap:8px;margin-top:18px"><div class="mono" style="position:relative;height:{H}px;font-size:11px;color:var(--mut);text-align:right"><span style="position:absolute;right:0;top:0;transform:translateY(-50%)">100 %</span><span style="position:absolute;right:0;top:50%;transform:translateY(-50%)">50 %</span><span style="position:absolute;right:0;bottom:0;transform:translateY(50%)">0 %</span></div>
<div><div style="position:relative"><svg viewBox="0 0 640 {H}" preserveAspectRatio="none" role="img" aria-label="Verlauf {titel}: {aria}" style="width:100%;height:{H}px;display:block;border-bottom:1px solid var(--line2);overflow:visible">
<line x1="0" y1="0" x2="640" y2="0" stroke="#E6EAEC" stroke-width="1" vector-effect="non-scaling-stroke"></line>
<line x1="0" y1="{H // 2}" x2="640" y2="{H // 2}" stroke="#E6EAEC" stroke-width="1" vector-effect="non-scaling-stroke"></line>
<line x1="{xstand:.1f}" y1="0" x2="{xstand:.1f}" y2="{H}" stroke="#BFC9CE" stroke-width="1" stroke-dasharray="3 3" vector-effect="non-scaling-stroke"></line>
{linien}</svg>{labels}</div>
<div class="mono" style="position:relative;height:16px;font-size:11px;color:var(--mut);margin-top:6px">{ticks}</div></div></div>{notiz}</div>"""
    G_IDS = {q: IDX[q]["index_id"] for q in IDX}; K_IDS = {q: IDX[q]["index_id"] + "-KERN" for q in IDX}
    G_W = {q: (stat[q]["start"], stat[q]["kpi"], stat[q]["rund"]) for q in IDX}
    chart = f"""<section style="margin-top:64px"><h2 class="serif" style="font-size:26px">Verlauf in der Wahlperiode</h2>
<div class="grid2" style="margin-top:18px">{verlauf("Gesamtprogramm", G_IDS, G_W)}@@KVERLAUF@@</div>
<p class="note" style="margin:12px 0 0">Monatswerte seit der Wahl; die Achse reicht bis zum voraussichtlichen Ende der Wahlperiode ({MONL[int(ENDE_WP[5:]) - 1]} {ENDE_WP[:4]}).</p></section>"""

    # ---------- Änderungen
    allc = sorted([c for m in changes for c in changes[m]], reverse=True)
    secs = []
    for m in sorted(changes, reverse=True):
        i = months.index(m); pm = months[i - 1] if i else m
        def kv(p):
            a_ = float(kh[(IDX[p]["index_id"], m)]["actual_exact"]); b_ = float(kh[(IDX[p]["index_id"], pm)]["actual_exact"]); d = a_ - b_
            return f"{pct(a_)} % ({'± 0' if abs(d) < .05 else ('+ ' if d > 0 else '− ') + pct(abs(d))})"
        def chquelle(tid, b):
            kurz = (re.search(r"BGBl\. \d{4} I Nr\. \d+[a-z]?", b) or [b[:70]])[0]
            if tid in QURL:
                u, f = QURL[tid]
                return f'<a href="{e(u)}" rel="noopener">{e(f or kurz)} ↗</a>'
            return e(kurz)
        rr = "".join(f'<div class="ch"><span class="mono" style="font-size:13px;color:var(--mut)">{de(d)}</span><a class="id" href="vorhaben/{tid.rsplit("-", 1)[0].lower()}.html#{tid.rsplit("-", 1)[1].lower()}">{e(tid.rsplit("-", 1)[0] + " " + tid.rsplit("-", 1)[1])}</a><span>{e(x)} – {e(art)}</span><span style="font-size:13px;color:var(--ink2)">{chquelle(tid, b)}</span></div>' for d, tid, x, art, b in sorted(changes[m]))
        secs.append(f'<section id="m{m}" style="margin-top:32px"><div style="display:flex;flex-wrap:wrap;gap:6px 24px;align-items:baseline"><h2 class="serif" style="font-size:22px">{MONL[int(m[5:]) - 1]} {m[:4]}</h2><span class="mono" style="font-size:13px;color:var(--ink2)">{" · ".join(IDX[q]["name"] + " " + kv(q) for q in ORD)}</span></div><div style="margin-top:8px;border-top:1px solid var(--line2)">{rr}</div></section>')
    MK = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
    jahre = sorted({m[:4] for m in changes}, reverse=True)
    jump = "".join(f'<div style="display:flex;flex-wrap:wrap;gap:4px 14px;align-items:baseline"><span style="font-weight:600;min-width:44px">{j}</span>'
                   + "".join(f'<a href="#m{m}">{MK[int(m[5:]) - 1]}</a>' for m in sorted((m for m in changes if m[:4] == j), reverse=True)) + '</div>' for j in jahre)
    body = f"""<section style="padding-top:40px"><h1 class="serif" style="font-size:44px;margin-bottom:12px">Updates</h1><p class="lead">Jede Statusänderung einer Zusage, mit dem Tag, ab dem sie gilt, und dem Beleg. Korrekturen und Änderungen der Methodik stehen unter <a href="methodik.html#korrekturen">So messen wir</a>.</p></section>
<nav aria-label="Monate" style="display:flex;flex-direction:column;gap:6px;margin-top:20px;font-size:15px">{jump}</nav>
{''.join(secs)}
"""
    KORR = """<section id="korrekturen" class="plain" style="margin-top:48px;max-width:76ch"><h2 class="serif" style="font-size:24px;margin-bottom:8px">Korrekturen</h2>
<p style="font-size:15px;color:var(--ink2);margin:0">Die Werte bis September 2026 sind rückwirkend berechnet, ab Oktober 2026 werden sie monatlich festgestellt. Korrekturen und Änderungen der Methodik erscheinen hier mit Datum und Begründung.</p>
<div class="ch" style="grid-template-columns:110px minmax(0,1fr);margin-top:12px"><span class="mono" style="font-size:13px;color:var(--mut)">08.11.2026</span><span><b>Methodik:</b> Zusagen zählen jetzt unabhängig davon, ob EU, Bund oder Länder sie beschließen müssen; erfüllt, wenn der Rechtsakt gilt (<a href="methodik.html#e40">E40</a>). Bisher zählten Maßnahmen, die nur die EU beschließen kann, nicht (<a href="methodik.html#e27">E27</a>). Dadurch kommen 17 Teilzusagen hinzu (CDU/CSU 11, SPD 6), Werte rückwirkend ab Februar 2025. Oktober 2026 korrigiert: CDU/CSU 28,4 → 30,1 %, SPD 36,9 → 37,4 %. Kernversprechen unverändert.</span></div>
<div class="ch" style="grid-template-columns:110px minmax(0,1fr);margin-top:12px"><span class="mono" style="font-size:13px;color:var(--mut)">21.10.2026</span><span><b>Methodik:</b> zweiter Index <a href="kernversprechen.html">Kernversprechen</a> eingeführt (<a href="methodik.html#e36">E36</a>), Werte rückwirkend ab Februar 2025. Die Werte des Gesamtprogramms ändern sich dadurch nicht.</span></div></section>"""
    open(os.path.join(OUT, "aenderungen.html"), "w", encoding="utf-8").write(page(f"Updates {PARL['name']}", body, "", "aenderungen.html"))

    SAND = sanduhr(ST, 24, 40)
    # ---------- Start
    # Demnächst wirksam: beschlossene Zusagen beider Parteien, nächste zuerst
    bald = sorted(((t, IDX[q]) for q in ORD for t, _ in stat[q]["be"]), key=lambda x: (x[0]["erfuellt_ab"] or "9999-99-99", x[0]["tz_id"]))
    def baldzeile(t, cfg):
        tid = t["tz_id"]; kurz = tid.rsplit("-", 1)[0] + " " + tid.rsplit("-", 1)[1]
        dat = de(t["erfuellt_ab"]) if t["erfuellt_ab"] else "offen"
        zus = "" if t["erfuellt_ab"] else ' <span style="color:var(--mut)">· Verkündung ausstehend</span>'
        return (f'<div class="lc be"><span style="font-size:13px;color:var(--be);font-weight:600">{dat}</span>'
                f'<a class="id" href="vorhaben/{t["item_id"].lower()}.html#{tid.rsplit("-", 1)[1].lower()}">{e(kurz)}</a>'
                f'<span>{e(t["text_de"])}{kmark(tid)}{zus}</span></div>')
    bald_html = "".join(baldzeile(t, c) for t, c in bald[:6])
    bald_mehr = " · ".join(f'<a href="{IDX[q]["slug"]}.html#beschlossen">{IDX[q]["name"]} ({len(stat[q]["be"])})</a>' for q in ORD if stat[q]["be"])
    last = "".join(f'<div class="lc"><span class="mono" style="font-size:13px;color:var(--mut)">{de(d)}</span><span class="id">{e(tid.rsplit("-", 1)[0] + " " + tid.rsplit("-", 1)[1])}</span><span>{e(x)} <span style="color:var(--mut)">· {e(art)}</span></span></div>' for d, tid, x, art, b in allc[:4])
    # Kernversprechen (E36): Teilmenge des Gesamtprogramms; ein Abschnitt je Kernversprechen im Balken
    TZM = {t["tz_id"]: t for t in tzs}
    KVROWS = list(csv.DictReader(open(os.path.join(D, "kernversprechen.csv"), encoding="utf-8")))
    KVTXT = {"ok": "erfüllt", "be": "beschlossen", "br": "gebrochen oder Frist verfehlt", "": "noch offen"}
    def tzlink(tid):
        t = TZM[tid]; return f'vorhaben/{t["item_id"].lower()}.html#{tid.rsplit("-", 1)[1].lower()}'
    KS = {}
    khk = lambda kid, m: kh.get((kid, m), {"actual_exact": "0", "actual": "0"})
    for q, cfg in IDX.items():
        kid = cfg["index_id"] + "-KERN"
        rows = [dict(k, cl=status(TZM[k["tz_id"]], ST)[1], st=status(TZM[k["tz_id"]], ST)[0]) for k in KVROWS if k["index_id"] == kid]
        rows.sort(key=lambda k: (["ok", "be", "", "br"].index(k["cl"]), k["kv_id"]))
        c = collections.Counter(k["cl"] for k in rows)
        KS[q] = dict(id=kid, rows=rows, n=len(rows), c=c, k=c["ok"], kpi=float(khk(kid, MONTH)["actual_exact"]), rund=khk(kid, MONTH)["actual"],
                     start=float(khk(kid, months[0])["actual_exact"]), B=sum(1 for k in rows if TZM[k["tz_id"]]["typ_zusage"] == "Bestand" and k["cl"] == "ok"))
    def statusbalken(c, n, h=14):
        w = lambda x: f"{100 * x / n:.3f}%"
        return (f'<div class="sbar" style="height:{h}px" role="img" aria-label="{c["ok"]} erfüllt, {c["be"]} beschlossen, {n - c["ok"] - c["be"] - c["br"]} offen, {c["br"]} gebrochen oder Frist verfehlt">'
                f'<span class="ok" style="width:{w(c["ok"])}"></span><span class="be" style="width:{w(c["be"])}"></span><span style="flex:1"></span><span class="br" style="width:{w(c["br"])}"></span></div>')
    def kernbalken(q, h=14):
        return gbalken([(k["tz_id"], k["satz"], k["st"], k["cl"]) for k in KS[q]["rows"]], h)
    def kernbalken_alt(q, h=14):
        rows = KS[q]["rows"]; n = len(rows); segs = []
        for j, k in enumerate(rows):
            pos = "l" if j < n / 3 else ("r" if j >= n * 2 / 3 else "")
            segs.append(f'<a class="{k["cl"] or "of"} {pos}" href="{tzlink(k["tz_id"])}" aria-label="{e(k["satz"])}: {KVTXT[k["cl"]]}"><span class="tip" aria-hidden="true">{e(k["satz"])}<b>{e(k["st"])}</b></span></a>')
        return f'<div class="kbar" style="height:{h}px">{"".join(segs)}</div>'
    def kernliste(q):
        return "".join(f'<li><span class="kvd {k["cl"] or "of"}"></span><a href="{tzlink(k["tz_id"])}">{e(k["satz"])}</a> <span style="color:var(--mut)">· {e(k["st"])}</span></li>' for k in KS[q]["rows"])
    def zlink(n, txt, href, cls=""):
        # Zähler mit Link auf die passende Liste; bei 0 ohne Link
        return f'<a{" class=" + chr(34) + cls + chr(34) if cls else ""} href="{href}">{n} {txt}</a>' if n else f"{n} {txt}"
    def gnote(q, extra=""):
        cfg, c = IDX[q], stat[q]["c"]
        return (zlink(c["be"], "beschlossen", f'{cfg["slug"]}.html#beschlossen') + " · "
                + zlink(c["br"], "gebrochen oder Frist verfehlt", f'{cfg["slug"]}.html#gebrochen', "brlink") + extra)
    def knote(q, extra=""):
        cfg, c = IDX[q], KS[q]["c"]
        return (zlink(c["be"], "beschlossen", f'kernversprechen.html#{cfg["slug"]}-beschlossen') + " · "
                + zlink(c["br"], "gebrochen oder Frist verfehlt", f'kernversprechen.html#{cfg["slug"]}-gebrochen', "brlink") + extra)
    def bilanzkarte(q):
        cfg, s, k = IDX[q], stat[q], KS[q]
        kernlink = f"""<a href="kernversprechen.html#{cfg['slug']}">Kernversprechen {e(cfg['name'])} →</a>""" if KERN else ""
        kernblock = f"""<div class="bz"><div class="bkopf"><span class="label">Kernversprechen <span class="lsub">· von der Partei selbst herausgestellt · <a href="kernversprechen.html">was zählt?</a></span></span><span class="big" style="font-size:36px">{k['rund']} %</span><span class="bsub">{zlink(k['k'], f"von {k['n']} Kernversprechen erfüllt", f"kernversprechen.html#{cfg['slug']}-erfuellt")}</span></div>
{kernbalken(q)}<div class="bnote">{knote(q, '<span class="hovtip"> · auf einen Abschnitt zeigen für die Versprechen</span>')}</div>{f'<div class="bnote">Bei {k["n"]} Kernversprechen verändert jedes den Wert um {pct(100 / k["n"]).replace(",0", "")} Punkte.</div>' if k["n"] < 20 else ""}
<details class="kvl"><summary>Alle {k['n']} Kernversprechen als Liste</summary><ul>{kernliste(q)}</ul></details></div>
""" if KERN else ""
        return f"""<div class="card bil"><div class="serif" style="font-size:26px;font-weight:600">{e(cfg['name'])}</div>
<div class="bz"><div class="bkopf"><span class="label">Gesamtprogramm <span class="lsub">· alle Zusagen des Wahlprogramms</span></span><span class="big xl" style="font-size:60px">{s['rund']} %</span><span class="bsub"><a href="{cfg['slug']}.html#erfuellt">{s['k']} von {s['n']} Zusagen erfüllt</a></span></div>
{gbalken(zrows(s['tl']))}<div class="bnote">{gnote(q, '<span class="hovtip"> · auf einen Abschnitt zeigen für die Zusagen</span>')}</div></div>
{kernblock}<div style="display:flex;flex-wrap:wrap;gap:6px 24px;margin-top:16px;font-size:14.5px"><a href="{cfg['slug']}.html">Gesamtprogramm {e(cfg['name'])} →</a>{kernlink}</div></div>"""
    chart = chart.replace("@@KVERLAUF@@", verlauf("Kernversprechen", K_IDS, {q: (KS[q]["start"], KS[q]["kpi"], KS[q]["rund"]) for q in IDX}) if KERN else "")
    s1, s2 = stat[ORD[0]], stat[ORD[1]]; n1, n2 = IDX[ORD[0]]["name"], IDX[ORD[1]]["name"]
    hs, ls = sorted(ORD, key=lambda q: -stat[q]["start"]); sh, sl = stat[hs], stat[ls]
    HERO = f"""<section style="padding:48px 0 8px"><h1 class="serif hero" style="font-size:60px;line-height:1.04;letter-spacing:-.015em;margin-bottom:16px">Versprochen. Gehalten?</h1>
<p class="lead" style="font-size:18px">Wie viel haben die Parteien von ihrem Wahlprogramm umgesetzt? DeliverPolitics prüft jede Zusage gegen geltendes Recht – Zusage für Zusage, Monat für Monat.</p>
<p style="font-size:15px;margin:10px 0 0"><a href="ueber.html#warum">Warum dieser Index? →</a></p></section>"""
    BUNDBLOCK = f"""<div class="metaz"><span class="mono">{e(PARL['name'])} · {PARL['wahlperiode']}. Wahlperiode · Wahltag {de(WAHLTAG)} · Stand {STD}</span><span class="sandz">{SAND[0]}<span>{SAND[1]} von {SAND[2]} Monaten der Wahlperiode vergangen</span></span></div>
<section style="margin-top:28px;display:flex;flex-direction:column;gap:20px">{''.join(bilanzkarte(q) for q in ORD)}</section>
<div class="legz"><span><span class="kvd ok"></span>erfüllt</span><span><span class="kvd be"></span>beschlossen</span><span><span class="kvd of"></span>offen</span><span><span class="kvd br"></span>gebrochen oder Frist verfehlt</span></div>"""
    SOENTSTEHT = f"""<section style="margin-top:64px"><h2 class="serif" style="font-size:26px;margin-bottom:18px">So entsteht die Zahl</h2>
<div class="steps"><div><div class="label">1 · Zerlegen</div><p>Das Wahlprogramm wird in überprüfbare Zusagen zerlegt.</p></div>
<div><div class="label">2 · Prüfen</div><p>Für jede Zusage steht vorab fest, wann sie erfüllt ist. Maßgeblich ist geltendes Recht.</p></div>
<div><div class="label">3 · Zählen</div><p>Der Index ist der Anteil erfüllter Zusagen. Jede zählt gleich.</p></div></div>
<p style="font-size:15px;margin-top:16px"><a href="methodik.html">So messen wir →</a></p></section>"""
    # ---------- Themen nach CAP-Codebuch (E38): je Thema ein Balken je Partei
    CAPNAME = {1: "Wirtschaftspolitik & Steuern", 2: "Bürgerrechte", 3: "Gesundheit", 4: "Landwirtschaft", 5: "Arbeit", 6: "Bildung", 7: "Umwelt & Klima", 8: "Energie",
               9: "Migration", 10: "Verkehr", 12: "Recht & Kriminalität", 13: "Soziales & Rente", 14: "Wohnen & Stadtentwicklung", 15: "Wirtschaft, Finanzmarkt & Sport",
               16: "Verteidigung", 17: "Wissenschaft & Technologie", 18: "Außenhandel", 19: "Außenpolitik & Europa", 20: "Staat & Verwaltung",
               21: "Denkmäler & öffentliche Flächen", 23: "Kultur"}
    THEMEN_HTML = ""
    pcap = os.path.join(D, "themen_cap.csv")
    if os.path.exists(pcap) and {r["tz_id"] for r in csv.DictReader(open(pcap, encoding="utf-8"))} & {t["tz_id"] for t in tzs}:
        TL = collections.defaultdict(list)
        CAPM = {r["tz_id"]: int(r["cap_major"]) for r in csv.DictReader(open(pcap, encoding="utf-8"))}
        TC = collections.defaultdict(collections.Counter); TP = collections.defaultdict(collections.Counter)
        for t in tzs:
            if t["tz_id"] not in CAPM: continue
            m = CAPM[t["tz_id"]]; cl = status(t, ST)[1]; TC[m][cl] += 1; TP[(m, pk(t["tz_id"]))][cl] += 1; TL[(m, pk(t["tz_id"]))].append(t)
        haupt = [m for m in TC if sum(TC[m].values()) >= 10]; weitere = sorted(m for m in TC if m not in haupt)
        def tsum(ms, q=None):
            c = collections.Counter()
            for m in ms: c.update(TP[(m, q)] if q else TC[m])
            return c
        reihen = sorted(haupt, key=lambda m: (-TC[m]["ok"] / sum(TC[m].values()), CAPNAME[m])) + (["w"] if weitere else [])
        def tzeile(m):
            name = CAPNAME[m] if m != "w" else "Weitere Themen"
            zz = ""
            for q in ORD:
                c = tsum(weitere, q) if m == "w" else TP[(m, q)]; n = sum(c.values())
                wert = (f'<span class="tw{" klein" if n < 5 else ""}"><b>{round(100 * c["ok"] / n)} %</b> {c["ok"]} von {n}</span>' if n else '<span class="tw klein">keine Zusage</span>')
                zz += f'<div class="tp"><span class="tpn">{e(IDX[q]["name"])}</span>{gbalken(zrows([t for mm in (weitere if m == "w" else [m]) for t in TL[(mm, q)]]), 12)}{wert}</div>'
            return f'<div class="tz2"><div class="tzn">{e(name)}</div><div>{zz}</div></div>'
        THEMEN_HTML = f"""<section style="margin-top:64px" id="themen"><h2 class="serif" style="font-size:26px">Nach Themen</h2>
<p class="note" style="margin-top:6px">Alle Zusagen des Gesamtprogramms, nach Themen des internationalen Codebuchs des Comparative Agendas Project; sortiert nach dem Anteil erfüllter Zusagen beider Parteien zusammen. Prozent = erfüllte Zusagen.</p>
<div style="margin-top:14px;border-top:1px solid var(--line2)">{"".join(tzeile(m) for m in reihen)}</div>
<p class="note" style="margin-top:10px">Weitere Themen: {", ".join(CAPNAME[m] for m in weitere)} (je unter 10 Zusagen). Nicht fett gesetzte Werte: unter 5 Zusagen, wenig aussagekräftig. Sport gehört im CAP-Codebuch zum Hauptthema „Wirtschaft, Finanzmarkt &amp; Sport“ (Domestic Commerce). Jede Zusage wurde zweifach unabhängig codiert (Übereinstimmung {CAP_UEB[PDIR]} %); die Themen ändern keinen Indexwert. <a href="methodik.html#e38">Regel E38 →</a></p></section>"""
    # ---------- Übersicht des Parlaments
    PNOTE = "" if KERN else (f'<p class="note" style="margin-top:14px">Für {e(PARL["name"])} gibt es nur den Index Gesamtprogramm. Die Wahlprogramme enthalten keine Kurzfassung, '
                             f'aus der sich Kernversprechen ergeben (<a href="methodik.html#e36">E36</a>).</p>')
    # Programmgrundlage auf der Übersicht eines Landesparlaments: Programme mit Link und PDF-Kopie, darunter der Hinweis zu Absichtssätzen
    PGRUND = "" if HAUPT else (f'<section id="programmgrundlage" style="margin-top:64px"><h2 class="serif" style="font-size:26px">Programmgrundlage</h2>'
                               f'<ul style="font-size:15px;color:var(--ink2);margin:12px 0 0;padding-left:18px">'
                               + "".join(f"<li style='margin-bottom:6px'>{e(IDX[q]['name'])}: {proglink(IDX[q])}. {e(IDX[q]['basis'])}</li>" for q in ORD)
                               + f'</ul><div class="plain" style="margin-top:18px;max-width:76ch"><h3 class="serif" style="font-size:20px">Warum manche konkreten Vorhaben nicht zählen</h3>{w_hinweis(PDIR)}'
                               f'<p class="note" style="margin:10px 0 0">Regeln: <a href="methodik.html#teilzusage">Was als Teilzusage zählt</a> (E5, E29).</p></div></section>')
    bald_kopf = f'<span style="font-size:14px">Alle beschlossenen: {bald_mehr}</span>' if bald_mehr else ""
    bald_liste = bald_html or '<p class="note" style="margin-top:10px">Derzeit keine.</p>'
    body = f"""<section style="padding-top:36px"><div class="label">{e(PARL['langname'])}</div><h1 class="serif" style="font-size:48px;margin:6px 0 4px">{e(PARL['name'])}</h1></section>
{BUNDBLOCK}{PNOTE}{PGRUND}
{chart}
{THEMEN_HTML}
<section style="margin-top:64px"><div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:8px"><h2 class="serif" style="font-size:26px">Demnächst wirksam</h2>{bald_kopf}</div>
<p class="note" style="margin-top:6px">Beschlossen, aber am Stichtag noch nicht geltend. Diese Zusagen zählen ab dem Tag, an dem die Vorschrift gilt.</p>
<div style="margin-top:10px;border-top:1px solid var(--line2)">{bald_liste}</div></section>
<section style="margin-top:64px"><div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:8px"><h2 class="serif" style="font-size:26px">Zuletzt geändert</h2><a href="aenderungen.html" style="font-size:14px">Alle Updates nach Monat</a></div>
<div style="margin-top:14px;border-top:1px solid var(--line2)">{last}</div></section>"""
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(page(f"{PARL['name']} · {PARL['wahlperiode']}. Wahlperiode", body, "", "index.html"))

    # ---------- Aktuell (Startseite): Bund groß, Spotlight und Monatsliste, Länder, So entsteht die Zahl
    BF = json.load(open(os.path.join(D, "befunde.json"), encoding="utf-8")) if os.path.exists(os.path.join(D, "befunde.json")) else []
    if not HAUPT: BF = []  # Spotlights gehören zum Hauptlauf
    spot = max((b for b in BF if b["stand"] <= MONTH), key=lambda b: b["id"], default=None)
    mon_name = f"{MONL[int(MONTH[5:]) - 1]} {MONTH[:4]}"
    im_monat = sorted(changes.get(MONTH, []), key=lambda c: (c[1] not in KERNSET, c[0], c[1]))
    def mzeile(c):
        d, tid, x, art, b = c
        return (f'<div class="mz"><span class="ptag">{e(PARL["kurz"])}</span><span><a href="vorhaben/{tid.rsplit("-", 1)[0].lower()}.html#{tid.rsplit("-", 1)[1].lower()}">{e(x)}</a>{kmark(tid)}'
                f'<br><span style="font-size:13px;color:var(--mut)">{e(IDX[pk(tid)]["name"])} · {e(art)} ab {de(d)}</span></span></div>')
    MAXM = 8
    if not im_monat:
        mliste = f'<p class="note">Im {mon_name} keine Statusänderung.</p>'
    elif len(im_monat) <= MAXM:
        mliste = "".join(mzeile(c) for c in im_monat)
    else:
        z = collections.Counter(c[3] for c in im_monat)
        mliste = f'<p style="font-size:15px">{e(PARL["name"])}: ' + ", ".join(f"{n} {a}" for a, n in z.items()) + f' · <a href="aenderungen.html#m{MONTH}">alle ansehen →</a></p>'
    if any(x["monat"] for x in EXTERN):
        def mz_ext(x, c):
            d, tid, txt, art, b = c
            cfg = x["IDX"][max((k for k in x["IDX"] if tid.startswith(k + "-")), key=len)]
            return (f'<div class="mz"><span class="ptag">{e(x["P"]["kurz"])}</span><span><a href="{x["P"]["parlament_id"]}/vorhaben/{tid.rsplit("-", 1)[0].lower()}.html#{tid.rsplit("-", 1)[1].lower()}">{e(txt)}</a>'
                    f'<br><span style="font-size:13px;color:var(--mut)">{e(cfg["name"])} · {e(art)} ab {de(d)}</span></span></div>')
        alle_m = ([((c[1] not in KERNSET, c[0], 0, c[1]), mzeile(c)) for c in im_monat]
                  + [((True, c[0], 1, c[1]), mz_ext(x, c)) for x in EXTERN for c in x["monat"]])
        if len(alle_m) <= MAXM:
            mliste = "".join(h for _, h in sorted(alle_m))
        else:
            def msum(name, lst, href):
                z = collections.Counter(c[3] for c in lst)
                return f'<p style="font-size:15px">{e(name)}: ' + ", ".join(f"{n} {a}" for a, n in z.items()) + f' · <a href="{href}#m{MONTH}">alle ansehen →</a></p>'
            mliste = ((msum(PARL["name"], im_monat, "aenderungen.html") if im_monat else "")
                      + "".join(msum(x["P"]["name"], x["monat"], x["P"]["parlament_id"] + "/updates.html") for x in EXTERN if x["monat"]))
    if spot:
        spot_html = (f'<a class="spotbild" href="befunde/{spot["id"]}.html" aria-label="Spotlight: {e(spot["titel"])}"><img src="befunde/{spot["id"]}-quer.png" alt="{e(spot["titel"])}" width="1200" height="630"></a>'
                     f'<p style="font-size:15px;color:var(--ink2);margin:14px 0 0">{e(spot["einleitung"])}</p>'
                     f'<p style="font-size:14.5px;margin:12px 0 0"><a href="befunde/{spot["id"]}.html">Zum Spotlight →</a> · <a href="befunde.html">Alle Spotlights →</a></p>')
    else:
        spot_html = '<p class="note">Noch kein Spotlight.</p>'
    body = f"""{HERO}
<section style="margin-top:28px"><div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:8px"><h2 class="serif" style="font-size:30px">{e(PARL['name'])}</h2><a href="index.html" style="font-size:15px">Alles zum {e(PARL['name'])} →</a></div>
{BUNDBLOCK}</section>
<section style="margin-top:64px"><h2 class="serif" style="font-size:26px">Spotlight {e(spot['monat']) if spot else e(mon_name)}</h2>
<div class="spotgrid" style="margin-top:18px"><div>{spot_html}</div>
<div class="plain"><h3 class="serif" style="font-size:20px">Im {mon_name} geändert</h3><p class="note" style="margin:4px 0 10px">Alle Statusänderungen des Monats aus allen Parlamenten, Kernversprechen zuerst.</p>{mliste}</div></div></section>
@@LAENDER@@
{SOENTSTEHT}"""
    open(os.path.join(OUT, "_aktuell.html"), "w", encoding="utf-8").write(page("DeliverPolitics – Versprochen. Gehalten?", body, "", "_aktuell.html"))

    # ---------- Länder (Übersicht); Länder „in Vorbereitung“ ohne Werte
    LORD = sorted(LAENDER, key=lambda r: (r["wahltag"], r["name"]))
    EX = {x["P"]["parlament_id"]: x for x in EXTERN}
    def lkarte(r):
        kopf = (f'<div class="serif" style="font-size:21px;font-weight:600">{e(r["name"])}</div>'
                f'<div style="font-size:14px;color:var(--ink2);margin-top:2px">{e(r["langname"])}</div>'
                f'<div style="font-size:14px;color:var(--mut);margin-top:2px">{r["wahlperiode"]}. Wahlperiode · Wahltag {de(r["wahltag"])}</div>')
        x = EX.get(r["parlament_id"])
        if not x:
            return f'<div class="lk">{kopf}<span class="lstatus">{e(r["status"])}</span></div>'
        pd = r["parlament_id"]
        zeilen = "".join(
            f'<div style="margin-top:12px"><div style="display:flex;justify-content:space-between;align-items:baseline;gap:10px"><a href="{pd}/{x["IDX"][q]["slug"]}.html" style="font-weight:600">{e(x["IDX"][q]["name"])}</a>'
            f'<span class="mono" style="font-size:13.5px;color:var(--ink2)"><b style="font-size:17px;color:var(--ink)">{x["stat"][q]["rund"]} %</b> · {x["stat"][q]["k"]} von {x["stat"][q]["n"]}</span></div>'
            f'<div style="height:6px;background:var(--line);margin-top:5px" aria-hidden="true"><div style="width:{100 * x["stat"][q]["k"] / x["stat"][q]["n"]:.1f}%;height:100%;background:var(--ok)"></div></div></div>'
            for q in x["ORD"])
        return f'<div class="lk">{kopf}{zeilen}<div style="margin-top:14px;font-size:14.5px"><a href="{pd}/index.html">Alles zu {e(r["name"])} →</a></div></div>'
    LHINWEIS = ("„In Vorbereitung“ heißt: Die Wahlprogramme der Parteien, die die Landesregierung bilden, werden in überprüfbare Zusagen zerlegt und gegen geltendes Recht geprüft. "
                "Gemessen werden nur die Regierungsparteien, nach denselben Regeln wie im Bund (E37). Die Werte erscheinen, sobald die Regierung gebildet und die Prüfung abgeschlossen ist.")
    body = f"""<section style="padding-top:40px;max-width:76ch"><h1 class="serif" style="font-size:48px;margin-bottom:12px">Länder</h1>
<p class="lead">Was die Regierungsparteien in den Ländern versprochen haben – und was sie davon umsetzen. Aufgenommen werden die Länder, die 2026 gewählt haben.</p></section>
<section class="lgrid" style="margin-top:28px">{"".join(lkarte(r) for r in LORD)}</section>
<p class="note" style="margin-top:16px;max-width:76ch">{LHINWEIS} <a href="methodik.html#e37">Regel E37 →</a></p>"""
    open(os.path.join(OUT, "laender.html"), "w", encoding="utf-8").write(page("Länder", body, "", "laender.html"))
    akt = open(os.path.join(OUT, "_aktuell.html"), encoding="utf-8").read()
    lsek = (f'<section style="margin-top:64px"><div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:8px"><h2 class="serif" style="font-size:26px">Länder</h2><a href="laender.html" style="font-size:15px">Alle Länder →</a></div>'
            f'<div class="lgrid kompakt" style="margin-top:16px">{"".join(lkarte(r) for r in LORD)}</div></section>') if LORD else ""
    open(os.path.join(OUT, "_aktuell.html"), "w", encoding="utf-8").write(akt.replace("@@LAENDER@@", lsek))


    # ---------- Seite Kernversprechen (beide Parteien, nach Kernwert geordnet)
    ORDK = sorted(IDX, key=lambda q: (-KS[q]["kpi"], IDX[q]["name"]))
    NICHT = list(csv.DictReader(open(os.path.join(D, "kernversprechen_nicht_gezaehlt.csv"), encoding="utf-8")))
    GRUPPEN = [("ok", "Erfüllt"), ("be", "Beschlossen, noch nicht geltend"), ("", "Offen"), ("br", "Gebrochen oder Frist verfehlt")]
    def kvzeile(k):
        t = TZM[k["tz_id"]]; tid = k["tz_id"]
        return (f'<div class="tz {k["cl"]}" style="grid-template-columns:110px minmax(0,1fr) 250px"><a class="id" href="{tzlink(tid)}">{e(tid.rsplit("-", 1)[0] + " " + tid.rsplit("-", 1)[1])}</a>'
                f'<span><b style="font-weight:500">{e(k["satz"])}</b> <span style="color:var(--mut);font-size:13px">({e(k["seite"])})</span>{" <span class=typ>Bestand</span>" if t["typ_zusage"] == "Bestand" else ""}<br>'
                f'<span style="font-size:13px;color:var(--mut)">Teilzusage: {e(t["text_de"])}. {e(BELEG.get(tid, ""))}{qlink(tid)}</span></span><span class="st">{e(k["st"])}</span></div>')
    def kvabschnitt(q):
        cfg, k = IDX[q], KS[q]
        grp = "".join(f'<h3 class="serif" id="{cfg["slug"]}-{ {"ok": "erfuellt", "be": "beschlossen", "": "offen", "br": "gebrochen"}[cl] }" style="font-size:19px;margin:18px 0 8px">{ti} ({sum(1 for r in k["rows"] if r["cl"] == cl)})</h3><div style="border-top:1px solid var(--line2)">{"".join(kvzeile(r) for r in k["rows"] if r["cl"] == cl)}</div>'
                      for cl, ti in GRUPPEN if any(r["cl"] == cl for r in k["rows"]))
        nicht = [x for x in NICHT if x["index_id"] == k["id"]]
        nh = "".join(f'<div class="ch" style="grid-template-columns:minmax(0,1fr) minmax(0,1fr)"><span>{e(x["satz"])}</span><span style="color:var(--mut)">{e(x["grund"])}</span></div>' for x in nicht)
        quelle = "Kurzfassung des Programms" if q == "CDU" else "Einleitung „Worauf es jetzt ankommt“ (S. 5) und „Unser Versprechen“ (S. 66)"
        return f"""<section id="{cfg['slug']}" style="margin-top:56px"><div class="card"><h2 class="serif" style="font-size:28px;font-weight:600">{e(cfg['name'])}</h2>
<div class="bkopf" style="margin-top:12px"><span class="label">Kernversprechen</span><span class="big xl" style="font-size:56px">{k['rund']} %</span><span class="bsub">{zlink(k['k'], f"von {k['n']} Kernversprechen erfüllt", f"#{cfg['slug']}-erfuellt")}</span></div>
{kernbalken(q, 16)}<div class="bnote">{knote(q, '<span class="hovtip"> · auf einen Abschnitt zeigen für die Versprechen</span>')}</div>
<p style="font-size:14.5px;color:var(--ink2);margin:14px 0 0">Grundlage: {quelle} ({proglink(cfg)}). Zum Vergleich das <a href="{cfg['slug']}.html">Gesamtprogramm</a>: {stat[q]['rund']} % ({stat[q]['k']} von {stat[q]['n']}).</p></div>
<details class="auf"><summary><span class="pm" aria-hidden="true"></span>Alle {k['n']} Kernversprechen mit Status und Beleg</summary>{grp}</details>
<details class="auf"><summary><span class="pm" aria-hidden="true"></span>{len(nicht)} Sätze der Verdichtung, die nicht als Kernversprechen zählen, mit Grund</summary><div style="border-top:1px solid var(--line2)">{nh}</div></details></section>"""
    body = f"""<section style="padding-top:40px;max-width:76ch"><div class="label">Delivery Index</div><h1 class="serif" style="font-size:48px;margin:6px 0 12px">Kernversprechen</h1>
<p class="lead">Was jede Partei selbst als Kern ihres Programms herausgestellt hat, und was daraus geworden ist.</p></section>
<div class="plain" style="margin-top:20px"><div class="label">So werden die Kernversprechen bestimmt</div><ul style="font-size:15px;color:var(--ink2);margin:8px 0 0;padding-left:18px">
<li style="margin-bottom:6px"><b>Die Partei wählt aus.</b> Grundlage sind die Abschnitte, mit denen sie ihr Programm selbst zusammenfasst: bei der CDU/CSU die Kurzfassung, bei der SPD, die keine Kurzfassung hat, die Einleitung (S. 5) und „Unser Versprechen“ (S. 66).</li>
<li style="margin-bottom:6px"><b>Nur genannte Maßnahmen zählen.</b> Ein Satz zählt, wenn er selbst eine prüfbare Maßnahme nennt. Ziele ohne Maßnahme wie „günstige Energiepreise“ oder „stabile Rente“ zählen nicht als Kernversprechen; die zugehörigen Maßnahmen zählen im Gesamtprogramm.</li>
<li style="margin-bottom:6px"><b>Ein Satz, mehrere Versprechen.</b> Nennt ein Satz mehrere Maßnahmen, zählt jede einzeln. Deshalb gibt es mehr Kernversprechen als Sätze.</li>
<li style="margin-bottom:6px"><b>Teil des Gesamtprogramms.</b> Jedes Kernversprechen ist eine Zusage des Gesamtprogramms, mit demselben Prüfmaßstab, Beleg und Status. Hauptzahl bleibt das Gesamtprogramm.</li>
<li><b>Kleine Zahlen.</b> Bei wenigen Kernversprechen verändert schon eines den Wert deutlich.</li></ul>
<p class="note" style="margin:10px 0 0">Regel und Begründung: <a href="methodik.html#e36">E36</a>. Liste als CSV: <a href="daten.html">Daten</a>.</p></div>
<section style="margin-top:40px"><div class="grid2">{verlauf("Verlauf seit der Wahl", K_IDS, {q: (KS[q]["start"], KS[q]["kpi"], KS[q]["rund"]) for q in IDX}, hl=2) if KERN else ""}<div class="plain"><h2 class="serif" style="font-size:20px">Auf einen Blick</h2><div style="margin-top:14px">{"".join(f'<p style="font-size:15px;margin:0 0 10px"><a href="#{IDX[q]["slug"]}"><b>{IDX[q]["name"]}</b></a>: {zlink(KS[q]["k"], f'von {KS[q]["n"]} erfüllt', f'#{IDX[q]["slug"]}-erfuellt')} ({KS[q]["rund"]} %), {zlink(KS[q]["c"]["be"], "beschlossen", f'#{IDX[q]["slug"]}-beschlossen')}, {zlink(KS[q]["c"]["br"], "gebrochen oder Frist verfehlt", f'#{IDX[q]["slug"]}-gebrochen', "brlink")}.</p>' for q in ORDK)}</div></div></div></section>
{"".join(kvabschnitt(q) for q in ORDK)}
<div class="legz" style="margin-top:24px"><span><span class="kvd ok"></span>erfüllt</span><span><span class="kvd be"></span>beschlossen</span><span><span class="kvd of"></span>offen</span><span><span class="kvd br"></span>gebrochen oder Frist verfehlt</span></div>"""
    open(os.path.join(OUT, "kernversprechen.html"), "w", encoding="utf-8").write(page(f"Kernversprechen {PARL['name']}", body, "", "kernversprechen.html"))

    # ---------- Übersicht Gesamtprogramm (nach Gesamtwert geordnet)
    def gkarte(q):
        cfg, s_ = IDX[q], stat[q]
        return f"""<div class="card"><div class="serif" style="font-size:26px;font-weight:600">{e(cfg['name'])}</div>
<div class="bkopf" style="margin-top:12px"><span class="label">Gesamtprogramm</span><span class="big xl" style="font-size:56px">{s_['rund']} %</span><span class="bsub">{zlink(s_['k'], f"von {s_['n']} Zusagen erfüllt", f"{cfg['slug']}.html#erfuellt")}</span></div>
{gbalken(zrows(s_['tl']), 16)}<div class="bnote">{gnote(q, f" · {s_['items']} Kapitel")}</div>
<p style="font-size:14.5px;color:var(--ink2);margin:14px 0 0">{proglink(cfg)}</p>
<div style="margin-top:14px;font-size:14.5px"><a href="{cfg['slug']}.html">Zum vollständigen Index {e(cfg['name'])} →</a></div></div>"""
    body = f"""<section style="padding-top:40px;max-width:76ch"><div class="label">Delivery Index</div><h1 class="serif" style="font-size:48px;margin:6px 0 12px">Gesamtprogramm</h1>
<p class="lead">Wie viel jede Partei von ihrem ganzen Wahlprogramm umgesetzt hat. Jede Zusage zählt gleich; maßgeblich ist geltendes Recht.</p></section>
<section style="margin-top:28px" class="grid2">{"".join(gkarte(q) for q in ORD)}</section>
<div class="legz"><span><span class="kvd ok"></span>erfüllt</span><span><span class="kvd be"></span>beschlossen</span><span><span class="kvd of"></span>offen</span><span><span class="kvd br"></span>gebrochen oder Frist verfehlt</span></div>
<p class="note" style="margin-top:12px">Unterschiedliche Startwerte stammen von Zusagen, einen bestehenden Zustand zu erhalten (<a href="methodik.html#bestand">Bestandszusagen</a>).{' Welche Zusagen die Parteien selbst als Kern herausgestellt haben, zeigt die Seite <a href="kernversprechen.html">Kernversprechen</a>.' if KERN else ''}</p>
<section style="margin-top:40px">{verlauf("Verlauf seit der Wahl", G_IDS, G_W, hl=2)}</section>"""
    open(os.path.join(OUT, "gesamtprogramm.html"), "w", encoding="utf-8").write(page(f"Gesamtprogramm {PARL['name']}", body, "", "gesamtprogramm.html"))

    # ---------- Methodik (Entscheidungsprotokoll)
    import markdown
    md = open(os.path.join(BASE, "tools", "entscheidungen.md"), encoding="utf-8").read()
    md = re.sub(r"^# .*\n", "", md, count=1)
    htm = markdown.markdown(md, extensions=["tables"])
    # Übersichtstabelle: Nummern verlinken
    htm = re.sub(r"<td>(E\d+)</td>", lambda m: f'<td><a href="#{m.group(1).lower()}">{m.group(1)}</a></td>', htm)
    # Teil B: jede Entscheidung einklappbar
    kopf, _, teil_b = htm.partition("<h2>Teil B")
    if teil_b:
        teil_b = "<h2>Teil B" + teil_b
        stuecke = re.split(r"(?=<h2>E\d+)", teil_b)
        neu = [stuecke[0]]
        for st in stuecke[1:]:
            m = re.match(r"<h2>(E\d+)(.*?)</h2>(.*)", st, re.S)
            neu.append(f'<details class="dec" id="{m.group(1).lower()}"><summary><span class="id">{m.group(1)}</span>{m.group(2)}</summary><div class="decbody">{m.group(3)}</div></details>')
        htm = kopf + "".join(neu)
    PG_EXT = "".join(f"<li style='margin-bottom:6px'>{e(x['IDX'][q]['name'])} ({e(x['P']['name'])}): {proglink(x['IDX'][q])}. {e(x['IDX'][q]['basis'])}</li>" for x in EXTERN for q in x["ORD"])
    BE_EXT = "".join(f"<li>{e(x['IDX'][q]['name'])} ({e(x['P']['name'])}): {x['stat'][q]['c']['B']} von {x['stat'][q]['n']} Teilzusagen sind Bestandszusagen ({round(100 * x['stat'][q]['c']['B'] / x['stat'][q]['n'])} %), Startwert {pct(x['stat'][q]['start'])} % ({MONL[int(x['start'][5:]) - 1]} {x['start'][:4]})</li>" for x in EXTERN for q in x["ORD"])
    # Was als Teilzusage zählt (#teilzusage): allgemeine Sätze, dann je Land Beispiel und Zahlen
    W_LAND = "".join(f"<p style=\"font-size:15px;color:var(--ink2);margin:8px 0 0\"><b>{e(x['P']['name'])}:</b> {e(W_BEISPIEL[x['P']['parlament_id']])} {e(W_ZAHLEN[x['P']['parlament_id']])}</p>"
                     for x in EXTERN if x["P"]["parlament_id"] in W_BEISPIEL)
    TEILZUSAGE = (f'<div class="plain" id="teilzusage" style="margin-top:16px"><div class="label">Was als Teilzusage zählt</div>'
                  f'<p style="font-size:15px;color:var(--ink2);margin:8px 0 0">{e(W_SATZ1)}</p>{W_LAND}'
                  f'<p style="font-size:15px;color:var(--ink2);margin:8px 0 0">{e(W_SATZ3)}</p></div>')
    body = f"""<section style="padding-top:40px"><h1 class="serif" style="font-size:44px;margin-bottom:12px">So messen wir</h1>
<p class="lead">So entstehen die Indizes: oben die Kurzfassung, darunter das vollständige Regelwerk mit Begründungen.</p>
<div class="card" style="margin-top:20px"><div class="label">Kurzfassung</div><p style="font-size:15px;color:var(--ink2);margin:8px 0 0">Grundlage ist das vollständige Wahlprogramm (E25). Jedes Kapitel ist ein Vorhaben. Gezählt werden Handlungs- und Bestandszusagen mit benanntem Instrument (E5, E20, E23); Ziele, Absichten, Beispiele und Zwischenüberschriften zählen nicht (E28–E30). Für jede Teilzusage gilt ein vorab festgelegter Prüfmaßstab (E22, E24). Erfüllt ist eine Zusage ab Geltung der Vorschrift (E4, E14), auch wenn EU oder Länder sie beschließen müssen (E40). Index = Anteil erfüllter Teilzusagen am ganzen Programm; jede Zusage zählt gleich (E3, E19, E34). Zweiter Index <b>Kernversprechen</b>: dieselben Zusagen, soweit sie in den zusammenfassenden Abschnitten der Partei mit eigenem Instrument stehen; Hauptzahl bleibt das Gesamtprogramm (E36).</p></div>
<div class="plain" id="programmgrundlage" style="margin-top:16px"><div class="label">Programmgrundlage</div><ul style="font-size:15px;color:var(--ink2);margin:8px 0 0;padding-left:18px">{''.join(f"<li style='margin-bottom:6px'>{IDX[q]['name']}: {proglink(IDX[q])}. {e(IDX[q]['basis'])}</li>" for q in ORD)}{PG_EXT}</ul><p class="note" style="margin:8px 0 0">Die Kopien sichern die Nachprüfbarkeit, falls die Parteien ihre Dokumente ändern oder entfernen. Ziele, Absichten („wir wollen“), Beispiele und Zwischenüberschriften zählen nicht (E28–E30).</p></div>
{TEILZUSAGE}
<div class="plain" id="bestand" style="margin-top:16px"><div class="label">Bestandszusagen</div><p style="font-size:15px;color:var(--ink2);margin:8px 0 0">„Bestand“ ist eine Zusage, einen Zustand zu erhalten oder etwas fortzuführen („bleibt“, „wird fortgesetzt“, „kein …“). Sie zählt ab dem Wahltag als erfüllt, solange kein geltender Rechtsakt den Zustand ändert; ein Bruch ist endgültig (E23, E32, E33). Daraus ergeben sich die unterschiedlichen Startwerte im Februar 2025:</p><ul style="font-size:15px;color:var(--ink2);margin:8px 0 0;padding-left:18px">{''.join(f"<li>{IDX[q]['name']}: {stat[q]['c']['B']} von {stat[q]['n']} Teilzusagen sind Bestandszusagen ({round(100 * stat[q]['c']['B'] / stat[q]['n'])} %), Startwert {pct(stat[q]['start'])} %</li>" for q in ORD)}{BE_EXT}</ul></div>
</section>
<section class="prose" style="margin-top:20px">{htm}</section>
{KORR}"""
    open(os.path.join(OUT, "methodik.html"), "w", encoding="utf-8").write(page("So messen wir", body, "", "methodik.html"))

    # ---------- Daten
    qs = list(csv.DictReader(open(os.path.join(D, "quellen.csv"), encoding="utf-8")))
    with open(os.path.join(OUT, "daten", "quellen.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(qs[0].keys())); w.writeheader()
        for r in qs:
            r = dict(r); r["bezeichnung"] = sauber(re.sub(r"\s*\((v1|v2)\)", "", r["bezeichnung"])); w.writerow(r)
    for f in ("indizes.csv", "items.csv", "kpi_history.csv", "item_history.csv", "kernversprechen.csv", "themen_cap.csv"):
        shutil.copy(os.path.join(D, f), os.path.join(OUT, "daten", f))
    # Teilzusagen: nur der geltende Zuschnitt; archivierte Zwischenstände bleiben intern
    src = list(csv.DictReader(open(os.path.join(D, "teilzusagen.csv"), encoding="utf-8")))
    with open(os.path.join(OUT, "daten", "teilzusagen.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(src[0].keys())); w.writeheader()
        for r in src:
            if r["status_zuschnitt"] == "archiviert": continue
            r = dict(r); r["vorgaenger"] = ""; r["rechtsakt"] = sauber(r["rechtsakt"])
            r["anmerkung"] = "; ".join(x.strip() for x in r["anmerkung"].split(";") if x.strip() and not re.match(r"(v1|v2)\b", x.strip()))
            w.writerow(r)
    dl = "".join(f'<div class="ch" style="grid-template-columns:200px minmax(0,1fr)"><a class="id" href="daten/{f}" download>{f}</a><span>{t}</span></div>' for f, t in (
        ("kpi_history.csv", "Indizes Gesamtprogramm und Kernversprechen je Partei und Monat (rekonstruiert oder festgestellt)"), ("item_history.csv", "Wert je Vorhaben und Monat"),
        ("items.csv", "Vorhaben (Kapitel) mit Fundstelle"), ("teilzusagen.csv", "Alle Teilzusagen mit Typ, Prüfmaßstab, Geltungsdatum und Beleg"),
        ("quellen.csv", "Belege"), ("kernversprechen.csv", "Kernversprechen: Satz der Verdichtung und zugehörige Teilzusage (E36)"), ("themen_cap.csv", "Thema je Teilzusage nach CAP-Codebuch, beide Codierungen und Entscheidungen (E38)"), ("indizes.csv", "Indizes und Programmgrundlage")))
    body = f"""<section style="padding-top:40px"><h1 class="serif" style="font-size:44px;margin-bottom:12px">Daten</h1><p class="lead">Alle Daten des Index als CSV (UTF-8, Komma, Datumsformat JJJJ-MM-TT). Festgestellte Monate werden nicht mehr verändert; Korrekturen erscheinen unter <a href="methodik.html#korrekturen">Korrekturen</a>.</p></section>
<section style="margin-top:24px;border-top:1px solid var(--line2)">{dl}</section>"""
    open(os.path.join(OUT, "daten.html"), "w", encoding="utf-8").write(page("Daten", body))

    # ---------- Über, Impressum, Datenschutz
    body = f"""<section id="warum" style="padding-top:40px;max-width:70ch"><h1 class="serif" style="font-size:44px;margin-bottom:16px">Warum es diesen Index gibt</h1>
<h2 class="serif" style="font-size:26px;margin:36px 0 10px">Warum Wahlversprechen zählen</h2><p class="lead" style="font-size:16.5px">Bei einer Bundestagswahl entscheiden Wählerinnen und Wähler auch zwischen Programmen. Das Wahlprogramm ist das Dokument, in dem eine Partei vor der Wahl vollständig darlegt, was sie tun will, wenn sie regiert. Ob sie es danach tut, ist eine Grundfrage demokratischer Verantwortlichkeit.</p><p class="lead" style="font-size:16.5px">Die Forschung zeichnet dabei ein besseres Bild, als viele vermuten. Eine internationale Vergleichsstudie mit über 20.000 Wahlversprechen zeigt, dass Regierungsparteien die meisten ihrer Zusagen zumindest teilweise einlösen; Parteien, die allein regieren, gelingt das deutlich häufiger als Parteien in Koalitionen. Die Bürger unterschätzen diese Bilanz erheblich: Die Große Koalition 2013–2017 hat knapp 80 % ihres Koalitionsvertrags ganz oder teilweise umgesetzt, aber nur etwa jeder Achte hat das richtig eingeschätzt. Zugleich halten 85 % der Befragten es für wichtig, dass Wahlversprechen eingehalten werden.</p><p class="lead" style="font-size:16.5px">Versprechen haben Folgen: Regierungsparteien, die mehr von ihren Zusagen einlösen, verlieren bei der nächsten Wahl seltener Stimmen. Experimente zeigen außerdem, dass gebrochene Versprechen das Urteil über eine Regierung stärker prägen als gehaltene.</p>
<h2 class="serif" style="font-size:26px;margin:36px 0 10px">Was dieser Index leisten will</h2><p class="lead" style="font-size:16.5px">Bisherige Bilanzen in Deutschland messen meist den Koalitionsvertrag. DeliverPolitics misst, was jede Partei vor der Wahl in ihrem eigenen Programm versprochen hat. Jede Zusage wird anhand des Bundesgesetzblatts und amtlicher Quellen geprüft; der Stand wird monatlich fortgeschrieben.</p><p class="lead" style="font-size:16.5px">Der Index bewertet nicht, ob ein Versprechen gute Politik war oder ob ein Bruch gerechtfertigt war, etwa durch einen Koalitionskompromiss oder eine veränderte Lage. Er macht sichtbar, was eingelöst wurde und was nicht, damit diese Debatte auf überprüfbaren Fakten stattfindet.</p><p class="lead" style="font-size:16.5px">Zur Einordnung: In einer Koalition sind niedrigere Werte zu erwarten als bei einer Alleinregierung. Und die Werte anderer Studien sind nicht direkt vergleichbar, weil diese meist den Koalitionsvertrag messen und teilweise Erfülltes mitzählen. DeliverPolitics zählt nur vollständig erfüllte Zusagen.</p><p class="lead" style="font-size:16.5px">Wer weiß, dass seine Versprechen nachgeprüft werden, hat einen Anreiz, nur zu versprechen, was er halten kann.</p>
<div class="plain" style="margin-top:28px"><div class="label">Quellen</div><ul style="font-size:13.5px;color:var(--mut);margin:8px 0 0;padding-left:18px"><li style="margin-bottom:6px">Thomson, R. u. a. (2017): The Fulfillment of Parties’ Election Pledges: A Comparative Study on the Impact of Power Sharing. American Journal of Political Science 61(3). <a href="https://ajps.org/2017/06/07/the-fulfillment-of-parties-election-pledges-a-comparative-study-on-the-impact-of-power-sharing/" rel="noopener">Link ↗</a></li><li style="margin-bottom:6px">Vehrkamp, R. / Matthieß, T. (2018): Koalitionsvertrag auf dem Prüfstand. Bertelsmann Stiftung. <a href="https://www.bertelsmann-stiftung.de/de/themen/aktuelle-meldungen/2018/februar/koalitionsvertrag-auf-dem-pruefstand-groko-hielt-zum-grossteil-ihr-wort" rel="noopener">Link ↗</a></li><li style="margin-bottom:6px">Vehrkamp, R. / Matthieß, T. (2023): Mehr Koalition wagen – Halbzeitbilanz der Ampel-Koalition. Bertelsmann Stiftung (Umfrage: Institut für Demoskopie Allensbach). <a href="https://www.uni-trier.de/fileadmin/organisation/Presse/Dokumente/Studie_Koalitionsversprechen_Halbzeitbilanz.pdf" rel="noopener">Link ↗</a></li><li style="margin-bottom:6px">Matthieß, T. (2020): Retrospective pledge voting: A comparative study of the electoral consequences of government parties’ pledge fulfilment. European Journal of Political Research 59. <a href="https://www.deutsche-digitale-bibliothek.de/item/2MGNHRA7P2YWCL4XC24PGAX7EBF7YQSM" rel="noopener">Link ↗</a></li><li style="margin-bottom:6px">Naurin, E. / Soroka, S. / Markwat, N. (2019): Asymmetric Accountability: An Experimental Investigation of Biases in Evaluations of Governments’ Election Pledges. Comparative Political Studies 52(13–14).</li></ul></div></section>
<section id="offenlegung" class="steps" style="margin-top:32px"><div><div class="label">Herausgeber</div><p>Hajo Warmbier, unabhängig: ohne Auftrag, ohne Partei, ohne Stiftung.</p></div>
<div><div class="label">Offenlegung</div><p>Parteimitgliedschaft: keine.</p><p>Finanzierung: privat aus eigenen Mitteln; keine Spenden, Werbung oder Fördermittel.</p><p>Interessen: keine beruflichen oder finanziellen Verbindungen zu Parteien, Fraktionen, Ministerien oder Interessenverbänden. Beruf: Diplom-Kaufmann, angestellt in der Privatwirtschaft.</p></div>
<div><div class="label">Beta</div><p>Die Methodik wird mit Fachpublikum geprüft. Änderungen erscheinen datiert und begründet unter <a href="methodik.html#korrekturen">Korrekturen</a>.</p></div></section>
<section id="ki" style="margin-top:64px;max-width:70ch"><h2 class="serif" style="font-size:26px;margin-bottom:10px">Einsatz künstlicher Intelligenz</h2>
<p class="lead" style="font-size:15.5px">Bei der Erstellung dieser Website wurde künstliche Intelligenz eingesetzt – in allen Bereichen: Technik (Programmierung der Seite und der Berechnung), Design, Methodik (Ausarbeitung und Prüfung der Regeln) sowie Recherche (Zerlegung der Wahlprogramme, Suche und Auswertung von Belegen).</p>
<p class="lead" style="font-size:15.5px">Die Verantwortung liegt beim Betreiber: Jede Regel der Methodik wurde von ihm entschieden und ist im <a href="methodik.html">Entscheidungsprotokoll</a> festgehalten. Jede Bewertung nennt ihren Prüfmaßstab und ihre Quelle, damit sie unabhängig nachgeprüft werden kann. Fehler, auch solche der KI, korrigieren wir nach Hinweis datiert unter <a href="methodik.html#korrekturen">Korrekturen</a> – <a href="#feedback">Feedback</a> ist ausdrücklich erwünscht.</p></section>
<section class="plain" style="margin-top:32px;max-width:82ch"><div class="label">Leitplanke für Methodikänderungen</div><p style="font-size:15px;color:var(--ink2);margin:8px 0 0">Ein Vorschlag wird übernommen, wenn er die Messung genauer macht, ohne neue Ermessensspielräume oder Sonderregeln zu schaffen. Im Zweifel gilt die einfachere Regel.</p></section>
<section id="feedback" style="margin-top:48px;max-width:70ch"><h2 class="serif" style="font-size:28px;margin-bottom:12px">Feedback</h2>
<p class="lead" style="font-size:15.5px">Hinweise auf Fehler, fehlende Belege oder Schwächen der Methodik – bitte mit Vorhaben- oder Teilzusagen-Nummer (z. B. CDU-06 T3) und möglichst mit Quelle (Bundesgesetzblatt, Drucksache, amtliche Seite). Jede Rückmeldung wird gelesen; berechtigte Korrekturen erscheinen mit Datum.</p>
<p><a class="btn on" href="mailto:{KONTAKT}?subject=DeliverPolitics%20Feedback">Feedback per E-Mail senden</a></p></section>"""
    open(os.path.join(OUT, "ueber.html"), "w", encoding="utf-8").write(page("Projekt", body, "", "ueber.html"))
    ANSCHRIFT = "Hajo Warmbier<br>c/o Autorenglück #74087<br>Albert-Einstein-Str. 47<br>02977 Hoyerswerda"
    body = f"""<section class="prose" style="padding-top:40px"><h1 class="serif" style="font-size:40px;color:var(--ink)">Impressum</h1>
<p>{ANSCHRIFT}</p>
<h2>Kontakt</h2>
<p>E-Mail: <a href="mailto:{KONTAKT}">{KONTAKT}</a></p>
<h2>Redaktionell verantwortlich</h2>
<p>{ANSCHRIFT}</p></section>"""
    open(os.path.join(OUT, "impressum.html"), "w", encoding="utf-8").write(page("Impressum", body))
    body = open(os.path.join(BASE, "tools", "datenschutz.html"), encoding="utf-8").read().replace("{KONTAKT}", KONTAKT)
    open(os.path.join(OUT, "datenschutz.html"), "w", encoding="utf-8").write(page("Datenschutz", body))
    open(os.path.join(OUT, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\n\nSitemap: https://{DOMAIN}/sitemap.xml\n")
    for f in ("favicon.svg", "favicon.ico", "apple-touch-icon.png"):
        shutil.copyfile(os.path.join(BASE, "tools", "icon", f), os.path.join(OUT, f))
        os.chmod(os.path.join(OUT, f), 0o644)
    # ---------- Befunde
    os.makedirs(os.path.join(OUT, "befunde"), exist_ok=True)
    bf = json.load(open(os.path.join(D, "befunde.json"), encoding="utf-8")) if os.path.exists(os.path.join(D, "befunde.json")) else []
    if not HAUPT: bf = []
    tzmap = {t["tz_id"]: t for t in tzs}
    karten = []
    for b in sorted(bf, key=lambda x: x["id"], reverse=True):
        kh_m = {q: kh[(IDX[q]["index_id"], b["stand"])] for q in IDX}
        ordb = sorted(IDX, key=lambda q: -float(kh_m[q]["actual_exact"]))
        izeile = "Delivery Index: " + " · ".join(f"{IDX[q]['name']} {kh_m[q]['actual']} % (Kernversprechen {kh[(IDX[q]['index_id'] + '-KERN', b['stand'])]['actual']} %)" for q in ordb)
        punkte = [(pt, IDX[pk(pt["tz"])]["name"]) for pt in b["punkte"]]
        kk_m = {q: kh[(IDX[q]["index_id"] + "-KERN", b["stand"])] for q in IDX}
        idxb = [(IDX[q]["name"], kh_m[q]["actual"], int(kh_m[q]["erfuellt"]) / int(kh_m[q]["gesamt"]), kk_m[q]["actual"]) for q in ordb]
        for fmt in ("quadrat", "story", "quer"):
            if befund_bild(os.path.join(OUT, "befunde", f"{b['id']}-{fmt}.png"), b, punkte, idxb, fmt):
                os.chmod(os.path.join(OUT, "befunde", f"{b['id']}-{fmt}.png"), 0o644)
        li = ""
        for pt, partei in punkte:
            t = tzmap.get(pt["tz"], {}); tid = pt["tz"]; kurz = tid.rsplit("-", 1)[0] + " " + tid.rsplit("-", 1)[1]
            li += (f'<div class="tz ok" style="grid-template-columns:110px minmax(0,1fr) 250px"><a class="id" href="../vorhaben/{tid.rsplit("-", 1)[0].lower()}.html#{tid.rsplit("-", 1)[1].lower()}">{e(kurz)}</a>'
                   f'<span><b style="font-weight:600">{e(pt["titel"])}</b> <span style="color:var(--mut)">· {e(partei)}</span><br><span style="font-size:14px;color:var(--ink2)">{e(pt["text"])}</span>'
                   f'<br><span style="font-size:13px;color:var(--mut)">Zusage: „{e(t.get("text_de", ""))}“ · {e(BELEG.get(tid, ""))}</span>{qlink(tid)}</span>'
                   f'<span class="st">{e(status(t, ST)[0]) if t else ""}</span></div>')
        dl = " · ".join(f'<a href="{b["id"]}-{f}.png" download>{n}</a>' for f, n in (("quadrat", "Quadrat (Instagram)"), ("story", "Story (Hochformat)"), ("quer", "Querformat (LinkedIn, WhatsApp)")))
        # Texte zum Teilen (aus befunde.json, Feld beitraege); Kopieren ohne JavaScript über markierbare Textfelder
        BT = [("linkedin", "LinkedIn", "Bild Querformat oder einfach den Link teilen, das Vorschaubild erscheint automatisch", "quer"),
              ("instagram", "Instagram", "Bild Quadrat; Links sind in Beiträgen nicht klickbar", "quadrat"),
              ("story", "Instagram-Story", "Bild Hochformat", "story"),
              ("whatsapp", "WhatsApp", "Text mit Link senden, das Vorschaubild erscheint automatisch", ""),
              ("status", "WhatsApp-Status", "Bild Hochformat", "story")]
        bt = b.get("beitraege") or {}
        felder = "".join(
            f'<div class="teil"><label for="t-{k}"><b>{n}</b> <span style="color:var(--mut)">· {e(hin)}</span>'
            + (f' · <a href="{b["id"]}-{bild}.png" download>Bild</a>' if bild else "") + '</label>'
            f'<textarea id="t-{k}" readonly rows="{min(20, sum(1 + len(z) // 105 for z in bt[k].split(chr(10))) + 1)}">{e(bt[k])}</textarea></div>'
            for k, n, hin, bild in BT if bt.get(k))
        teilen = (f'<section class="plain" id="teilen" style="margin-top:24px"><h2 class="serif" style="font-size:22px">Zum Teilen</h2>'
                  f'<p class="note" style="margin:4px 0 12px">Texte für soziale Netzwerke. Ins Feld klicken, alles markieren (Strg+A bzw. ⌘+A) und kopieren.</p>{felder}</section>') if felder else ""
        body_b = f"""<nav class="crumb" aria-label="Pfad"><a href="../_aktuell.html">Aktuell</a><span>/</span><a href="../befunde.html">Spotlight</a><span>/</span><span style="color:var(--ink)">{e(b['monat'])}</span></nav>
<section style="padding-top:26px;max-width:76ch"><div class="label">Spotlight · {e(b['monat'])}</div><h1 class="serif" style="font-size:40px;line-height:1.1;margin:10px 0 12px">{e(b['titel'])}</h1>
<p class="lead">{e(b['einleitung'])}</p></section>
<section style="margin-top:28px"><div style="border-top:1px solid var(--line2)">{li}</div>
<p class="note" style="margin-top:14px">{e(izeile)} (Stand {de(stichtag_str(b['stand']))}). Spotlights beschreiben, sie bewerten nicht. Auswahl nach festen Anlässen, siehe <a href="../befunde.html#regeln">Regeln</a> (E35).</p></section>
<section class="plain" style="margin-top:40px"><div class="label">Grafik zum Teilen</div><p style="margin:10px 0 0"><img src="{b['id']}-quer.png" alt="{e(b['titel'])}" style="max-width:100%;height:auto;border:1px solid var(--line)" width="1200" height="630"></p><p style="font-size:14px;margin:10px 0 0">Herunterladen: {dl}</p></section>
{teilen}"""
        open(os.path.join(OUT, "befunde", b["id"] + ".html"), "w", encoding="utf-8").write(
            page(f"Spotlight {b['monat']}: {b['titel']}", body_b, "../", "befunde.html", og=f"befunde/{b['id']}-quer.png", ogalt=f"{b['titel']} – {izeile}", pub=b.get("datum")))
        karten.append(f'<div class="lc" style="grid-template-columns:150px minmax(0,1fr)"><span style="font-size:13px;color:var(--mut)">{e(b["monat"])}</span><span><a href="befunde/{b["id"]}.html" style="font-weight:600">{e(b["titel"])}</a><br><span style="font-size:14px;color:var(--ink2)">{e(b["einleitung"])}</span></span></div>')
    body_a = f"""<section style="padding-top:40px;max-width:76ch"><h1 class="serif" style="font-size:44px;margin-bottom:12px">Spotlight</h1>
<p class="lead">Jeden Monat ein Ausschnitt aus dem Index – kurz, belegt und zum Teilen.</p></section>
<section style="margin-top:28px"><div style="border-top:1px solid var(--line2)">{"".join(karten) or '<p class="note">Noch keine Spotlights.</p>'}</div></section>
<section id="regeln" class="plain" style="margin-top:48px;max-width:76ch"><div class="label">Regeln für Spotlights</div>
<ul style="font-size:15px;color:var(--ink2);margin:8px 0 0;padding-left:18px"><li>Auswahl nach festen Anlässen: neu erfüllt, neu gebrochen oder Frist verfehlt, demnächst wirksam, auffällige Kapitelwerte, Kernversprechen erfüllt oder gebrochen, Monatsbilanz.</li>
<li>Alle gemessenen Parteien kommen über die Zeit etwa gleich oft vor, mit positiven wie negativen Spotlights. Das Archiv auf dieser Seite macht das nachprüfbar.</li>
<li>Spotlights beschreiben, sie bewerten nicht. Jedes Spotlight verweist auf die Teilzusagen und ihre Belege.</li></ul></section>"""
    open(os.path.join(OUT, "befunde.html"), "w", encoding="utf-8").write(page("Spotlight", body_a, "", "befunde.html"))

    global OGALT
    eintr = [(IDX[q]["name"], stat[q]["rund"], stat[q]["k"], stat[q]["n"]) for q in ORD]
    OGALT = "Delivery Index, Stand " + STD + ": " + ", ".join(f"{a} {b} %" for a, b, _, _ in eintr)
    if og_bild(os.path.join(OUT, "og.png"), eintr, STD):
        os.chmod(os.path.join(OUT, "og.png"), 0o644)
    else:
        print("Hinweis: Vorschaubild og.png nicht erzeugt (Pillow oder Schriften fehlen) – das vorhandene auf dem Server bleibt gültig.")
    # ---------- Endgültige Adressen: Seiten aus dem flachen Erzeugungs-Layout verschieben und Links umschreiben
    def ziel(rel_):
        if rel_ == "_aktuell.html": return "index.html"
        if rel_ == "aenderungen.html": return f"{PDIR}/updates.html"
        if rel_ in PARLSEITEN or rel_.startswith("vorhaben/"): return f"{PDIR}/{rel_}"
        if rel_ == "methodik.html": return "so-messen-wir.html"
        if rel_ == "ueber.html": return "projekt.html"
        if rel_ == "befunde.html": return "spotlight.html"
        if rel_.startswith("befunde/"): return "spotlight/" + rel_[len("befunde/"):]
        return rel_
    alle = [os.path.relpath(os.path.join(dp_, f), OUT).replace(os.sep, "/") for dp_, _, fs in os.walk(OUT) for f in fs]
    LINK = re.compile(r'(href|src)="([^"#:?]*)(#[^"]*)?"')
    def umschreiben(alt, h):
        def f(m):
            url, anker = m.group(2), m.group(3) or ""
            if not url or url.startswith("@@"): return m.group(0)  # Platzhalter (kanonische Adresse) nicht umschreiben
            t = posixpath.normpath(posixpath.join(posixpath.dirname(alt), url))
            neu_ = posixpath.relpath(ziel(t), posixpath.dirname(ziel(alt)) or ".")
            return f'{m.group(1)}="{neu_}{anker}"'
        h = LINK.sub(f, h)
        return h.replace(f"https://{DOMAIN}/befunde/", f"https://{DOMAIN}/spotlight/")
    inhalte = {r: open(os.path.join(OUT, r), encoding="utf-8").read() for r in alle if r.endswith(".html")}
    for r in alle:
        if ziel(r) != r:
            os.makedirs(os.path.dirname(os.path.join(OUT, ziel(r))) or OUT, exist_ok=True)
            os.replace(os.path.join(OUT, r), os.path.join(OUT, ziel(r)))
    for r, h in inhalte.items():
        open(os.path.join(OUT, ziel(r)), "w", encoding="utf-8").write(umschreiben(r, h))
    for d_ in ("vorhaben", "befunde"):
        if os.path.isdir(os.path.join(OUT, d_)) and not os.listdir(os.path.join(OUT, d_)): os.rmdir(os.path.join(OUT, d_))
    # Beschreibung je Seite für Suchmaschinen (nur Werte aus dem Index)
    ITM = {i["item_id"].lower(): i for i in items}
    SPOTS = {b_["id"]: b_ for b_ in bf}
    gw = ", ".join(f"{IDX[q]['name']} {stat[q]['rund']} %" for q in ORD)
    def beschreibung(rel_, h):
        st_ = f"Stand {STD}"
        if rel_ == "index.html":
            return f"Versprochen. Gehalten? Delivery Index ({st_}): {gw} der Zusagen aus dem eigenen Wahlprogramm erfüllt – jede Zusage gegen geltendes Recht geprüft."
        if rel_ == f"{PDIR}/index.html":
            return f"{PARL['langname']}, {PARL['wahlperiode']}. Wahlperiode: Delivery Index {gw} ({st_}), Verlauf seit der Wahl, Themen und demnächst wirksame Zusagen."
        for q in IDX:
            if rel_ == f"{PDIR}/{IDX[q]['slug']}.html":
                s_ = stat[q]
                return f"Gesamtprogramm {IDX[q]['name']}: {s_['k']} von {s_['n']} Zusagen erfüllt ({s_['rund']} %, {st_}) – alle {s_['items']} Kapitel mit Prüfmaßstab und Beleg je Zusage."
        if rel_ == f"{PDIR}/gesamtprogramm.html":
            return f"Gesamtprogramm im Vergleich: " + ", ".join(f"{IDX[q]['name']} {stat[q]['k']} von {stat[q]['n']} Zusagen erfüllt" for q in ORD) + f" ({st_})."
        if rel_ == f"{PDIR}/kernversprechen.html":
            return "Kernversprechen – was die Parteien selbst herausgestellt haben: " + ", ".join(f"{IDX[q]['name']} {KS[q]['k']} von {KS[q]['n']} erfüllt" for q in ORDK) + f" ({st_})."
        if rel_ == f"{PDIR}/updates.html":
            return f"Updates: jede Statusänderung einer Wahlprogramm-Zusage von {' und '.join(IDX[q]['name'] for q in ORD)} mit Datum der Geltung und amtlichem Beleg, Monat für Monat ({st_})."
        m_ = re.match(rf"{PDIR}/vorhaben/(.+)\.html$", rel_)
        if m_ and m_.group(1) in ITM:
            it = ITM[m_.group(1)]; iid = it["item_id"]; partei = IDX[pk(iid)]["name"]
            if it["status"] != "aktiv":
                return f"{iid} {it['title_de']} ({partei}): Kapitel ohne wertbare Zusage – Begründung und Fundstelle im Programm."
            h_ = ih[(iid, MONTH)]
            return f"{iid} {it['title_de']} ({partei}): {h_['erfuellt']} von {h_['gesamt']} Zusagen erfüllt ({num(h_['value'])}, {st_}) – Prüfmaßstab und Beleg je Zusage."
        m_ = re.match(r"spotlight/(.+)\.html$", rel_)
        if m_ and m_.group(1) in SPOTS:
            return f"Spotlight {SPOTS[m_.group(1)]['monat']}: {SPOTS[m_.group(1)]['einleitung']}"
        fest = {"spotlight.html": "Alle Spotlights des Delivery Index: monatliche Ausschnitte zum Teilen, nach festen Anlässen ausgewählt, mit Belegen.",
                "so-messen-wir.html": "So messen wir: Regelwerk des Delivery Index – Zerlegung der Wahlprogramme, Prüfmaßstäbe, Zurechnung ab Wahltag, Korrekturen.",
                "projekt.html": "Warum es den Delivery Index gibt, wer ihn herausgibt, Offenlegung von Finanzierung und Interessen, Einsatz von KI und Feedback.",
                "daten.html": "Alle Daten des Delivery Index als CSV: Indizes, Vorhaben, Teilzusagen mit Prüfmaßstab und Beleg, Quellen, Kernversprechen, Themen.",
                "laender.html": ("Länder im Delivery Index: " + ", ".join(x["P"]["name"] for x in EXTERN) + " mit Werten, weitere Landesparlamente in Vorbereitung – gemessen werden die Regierungsparteien nach denselben Regeln wie im Bund." if EXTERN else "Länder im Delivery Index: Landesparlamente in Vorbereitung – gemessen werden die Regierungsparteien nach denselben Regeln wie im Bund."),
                "impressum.html": "Impressum von DeliverPolitics.",
                "datenschutz.html": "Datenschutzerklärung von DeliverPolitics: keine Cookies, kein Tracking, keine Inhalte von Drittanbietern."}
        if rel_ in fest: return fest[rel_]
        t_ = re.search(r"<title>(.*?)</title>", h)
        return (html.unescape(t_.group(1)) if t_ else "DeliverPolitics") + f" – Delivery Index, {st_}."
    # Frühere Adressen werden nicht weitergeleitet (Entscheidung 21.10.2026); alte Dateien auf dem Server löschen.
    for dp_, _, fs in os.walk(OUT):
        for f in fs:
            if f.endswith(".html"):
                fp = os.path.join(dp_, f); rel_ = os.path.relpath(fp, OUT).replace(os.sep, "/")
                url = f"https://{DOMAIN}/" + ("" if rel_ == "index.html" else rel_)
                h = open(fp, encoding="utf-8").read().replace("@@URL@@", url)
                h = h.replace("@@OGALT@@", e(OGALT))
                h = h.replace("@@DESC@@", e(beschreibung(rel_, h)))
                open(fp, "w", encoding="utf-8").write(h)
    if not HAUPT:
        # weiteres Parlament: nur dessen Ordner (und Programmkopien) behalten; alles Übrige erzeugt der Hauptlauf
        for name in os.listdir(OUT):
            if name not in (PDIR, "programme"):
                p_ = os.path.join(OUT, name)
                shutil.rmtree(p_) if os.path.isdir(p_) else os.remove(p_)
        if not KERN and os.path.exists(os.path.join(OUT, PDIR, "kernversprechen.html")): os.remove(os.path.join(OUT, PDIR, "kernversprechen.html"))
        if fehlende_pdf: print("Hinweis – Programmkopien nicht im Build enthalten:", ", ".join(fehlende_pdf))
        return dict(P=PARL, dir=OUT, IDX=dict(IDX), ORD=list(ORD), stat=stat, monat=sorted(changes.get(MONTH, [])), start=months[0])
    for x in EXTERN:  # Ordner der weiteren Parlamente übernehmen
        shutil.copytree(x["dir"], OUT, dirs_exist_ok=True); shutil.rmtree(x["dir"])
    PRIO9 = {f"{PDIR}/index.html"} | {x["P"]["parlament_id"] + "/index.html" for x in EXTERN}
    PRIO8 = ({"spotlight.html", f"{PDIR}/kernversprechen.html", f"{PDIR}/gesamtprogramm.html"} | {f"{PDIR}/{c['slug']}.html" for c in IDX.values()}
             | {f"{x['P']['parlament_id']}/{c['slug']}.html" for x in EXTERN for c in x["IDX"].values()} | {x["P"]["parlament_id"] + "/gesamtprogramm.html" for x in EXTERN})
    # Sitemap für Suchmaschinen
    urls = []
    for dp_, _, fs in os.walk(OUT):
        for f in sorted(fs):
            if f.endswith(".html"):
                rel_ = os.path.relpath(os.path.join(dp_, f), OUT).replace(os.sep, "/")
                prio = "1.0" if rel_ == "index.html" else ("0.9" if rel_ in PRIO9 else ("0.8" if rel_ in PRIO8 else ("0.3" if rel_ in ("impressum.html", "datenschutz.html") else "0.6")))
                urls.append(f"<url><loc>https://{DOMAIN}/{'' if rel_ == 'index.html' else rel_}</loc><lastmod>{dt.date.today().isoformat()}</lastmod><priority>{prio}</priority></url>")
    open(os.path.join(OUT, "sitemap.xml"), "w", encoding="utf-8").write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(sorted(urls)) + "\n</urlset>\n")
    n = sum(len(fs) for _, _, fs in os.walk(OUT))
    print(f"Website erzeugt: {OUT} ({n} Dateien), Stand {STD}")
    ph = set()
    for dp_, _, fs in os.walk(OUT):
        for f in fs:
            if f.endswith(".html"): ph |= set(re.findall(r"\[[A-ZÄÖÜ][A-ZÄÖÜ \-]+\]", open(os.path.join(dp_, f), encoding="utf-8").read()))
    print("Offene Platzhalter:", ", ".join(sorted(ph)) or "keine")
    if fehlende_pdf:
        print("Hinweis – Programmkopien nicht im Build enthalten:", ", ".join(fehlende_pdf),
              "(liegen einmalig hochgeladen auf dem Server; beim Hochladen den Ordner programme/ dort nicht löschen)")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--stand", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if os.path.abspath(a.out).startswith(BASE + os.sep) or os.path.abspath(a.out) == BASE:
        ap.error("--out muss außerhalb des Repo-Ordners liegen (der Zielordner wird gelöscht).")
    # Weitere Parlamente (Status „aktiv“ in parlamente.csv) zuerst: ihre Kennzahlen braucht der Hauptlauf für die gemeinsamen Seiten.
    extern = []
    for P in PARLAMENTE:
        if P is not HP and P["status"] == "aktiv":
            setze(P); extern.append(lauf(a.stand, a.out.rstrip("/") + "._" + P["parlament_id"], []))
    setze(HP); lauf(a.stand, a.out, extern)

if __name__ == "__main__":
    main()
