"""Build the installation help - one guide covering both desktop platforms, in
English and in French:

    installation-help/Kalulu Installation Help EN.pdf
    installation-help/Kalulu Aide Installation FR.pdf

There used to be two separate documents handed out on their own: a Word file for
Windows and a PDF for macOS. A person downloading a build does not know which
one they need until they have opened it, so this merges them into a single PDF
that opens on a contents page and sends the reader to their platform.

Each file name is written in its own language and ends in the language code, so
a reader on the release page can tell which one is theirs without opening
either - "Installation Help" alone says nothing to a French reader.

The English text is transcribed from those two originals, and the French is a
translation of it that names the controls the way a French Windows or macOS
labels them. Three deliberate departures from the originals, all marked in the
source below:

  * the macOS download step also names the .zip, because that is what the
    GitHub release actually ships - the original only described the .dmg;
  * the app bundle is written "Kalulu.app", which is its real name;
  * the Windows steps start from the .zip and name Kalulu-Windows.exe, which is
    what that zip contains - the original said "Kalulu.exe".

Unlike the per-language manuals, these are not generated from the app and do
not change per release, so the built PDFs are committed next to this script
rather than left in the gitignored build/ directory: the release pipeline
attaches them to every GitHub release and has to find them in a fresh clone.

    python tools/build_installation_help.py          # both
    python tools/build_installation_help.py fr       # one
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from reportlab.lib.enums import TA_LEFT  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents  # noqa: E402

from kalulu_manual import theme  # noqa: E402

OUT_DIR = ROOT / "installation-help"

# Mulish carries no emoji and no arrows: U+26A0, U+2705, U+25B8, U+2192 and the
# non-breaking hyphen U+2011 are all absent, and ReportLab would draw nothing at
# all for them. The originals leaned on them, so their meaning is carried by
# layout and colour here instead - a callout box rather than a warning sign -
# and the one that has a real equivalent, the separator, becomes U+203A.
CHEVRON = "›"

# French puts a non-breaking space inside guillemets and before : ; ! ?. The
# narrow one typographers prefer, U+202F, is missing from Mulish too, so this is
# the ordinary U+00A0.
NBSP = "&#160;"


def guillemets(text: str) -> str:
    return f"«{NBSP}{text}{NBSP}»"


# --- content -----------------------------------------------------------------
# ("heading", text) | ("para", text) | ("steps", [text, ...])
# ("bullets", [...]) | ("code", [line, ...]) | ("callout", (title, text))
# ("note", text)

WINDOWS_EN = [
    # Departure from the original, which said "Kalulu.exe" and spoke of two
    # loose files: the release ships one zip, and the program inside it is
    # Kalulu-Windows.exe.
    ("steps", [
        "<b>Download and place the files.</b> Extract "
        "<font face='Courier'>Kalulu-Windows-&lt;version&gt;.zip</font> from the "
        "releases page. Keep the two files it contains, "
        "<font face='Courier'>Kalulu-Windows.exe</font> and "
        "<font face='Courier'>libgdsqlite.windows.template_release.x86_64.dll</font>, "
        "together in the same folder on your computer.",
        "<b>Run the program.</b> Double-click on "
        "<font face='Courier'>Kalulu-Windows.exe</font>.",
        "<b>If you get a security warning.</b> If a message appears saying the "
        "program is unrecognized or has been blocked, look for an option such as "
        "<b>&#8220;Run anyway&#8221;</b> or <b>&#8220;Allow execution&#8221;</b>, "
        "and click it to continue.",
    ]),
    ("callout", ("Done!", "The game should now launch and work correctly.")),
]

MACOS_EN = [
    ("callout", ("Important", (
        "Run Kalulu only if you fully trust its source. Messages like "
        "&#8220;The application is damaged&#8221; or &#8220;Apple cannot check it "
        "for malicious software&#8221; often mean the app is unsigned or marked as "
        "quarantined (not necessarily corrupted)."
    ))),
    ("heading2", "Download and install"),
    # Departure from the original, which only described the .dmg: the GitHub
    # release ships a .zip, so a reader following the old text looks for a file
    # they never downloaded.
    ("steps", [
        "Locate the file you downloaded, usually in <b>Downloads</b>: "
        "<font face='Courier'>Kalulu-macOS-&lt;version&gt;.zip</font> from the "
        "releases page, or <font face='Courier'>Kalulu.dmg</font>.",
        "Open it. A zip unpacks to <font face='Courier'>Kalulu.app</font>; a .dmg "
        "opens a <i>Kalulu</i> volume in the Finder.",
        "Drag <font face='Courier'>Kalulu.app</font> into <b>Applications</b>.",
        "If you opened a .dmg, eject the <i>Kalulu</i> volume from the Finder "
        "(the eject icon).",
    ]),
    ("note", "Terminal equivalent of the copy:"),
    ("code", ['cp -R "/Volumes/Kalulu/Kalulu.app" "/Applications/Kalulu.app"']),

    ("heading2", f"Method 1 {CHEVRON} Right-click, Open (recommended)"),
    ("steps", [
        "Open <b>/Applications</b>.",
        f"Right-click (or Ctrl-click) <font face='Courier'>Kalulu.app</font> "
        f"{CHEVRON} <b>Open</b>.",
        "In the &#8220;<i>from an unidentified developer</i>&#8221; dialog, click "
        "<b>Open</b>.",
    ]),
    ("note", "macOS creates a Gatekeeper exception: from the second launch, a "
             "normal double-click will work."),

    ("heading2", f"Method 2 {CHEVRON} System Settings, Privacy &amp; Security"),
    ("steps", [
        "First try a double-click on <font face='Courier'>Kalulu.app</font> - let "
        "it be blocked, then close the alert.",
        f"Go to the Apple menu {CHEVRON} <b>System Settings</b> {CHEVRON} "
        f"<b>Privacy &amp; Security</b> (older versions: <b>System Preferences</b> "
        f"{CHEVRON} <b>Security &amp; Privacy</b>).",
        "Scroll to find &#8220;<i>Kalulu.app was blocked&#8230;</i>&#8221;.",
        "Click <b>Open Anyway</b>, then confirm <b>Open</b>.",
    ]),

    ("heading2", f"Method 3 {CHEVRON} Terminal, for the &#8220;is damaged&#8221; message"),
    ("para", "That message is often caused by the quarantine attribute. Remove it "
             "using Terminal (<b>Applications</b> " + CHEVRON + " <b>Utilities</b> "
             + CHEVRON + " <b>Terminal</b>):"),
    ("code", ['xattr -dr com.apple.quarantine "/Applications/Kalulu.app"']),
    ("note", "Then relaunch Kalulu.app, ideally combined with Method 1 "
             "(right-click, Open)."),

    ("heading2", "Advanced: temporarily disable Gatekeeper (not recommended)"),
    ("para", "Use only if everything above fails."),
    ("code", [
        "# Disable Gatekeeper",
        "sudo spctl --master-disable",
        "# Open the app once",
        'open "/Applications/Kalulu.app"',
        "# Re-enable Gatekeeper",
        "sudo spctl --master-enable",
    ]),

    ("heading2", "Quick troubleshooting"),
    ("bullets", [
        "Nothing happens on double-click: use Method 1 (right-click, Open).",
        "Still shows &#8220;damaged&#8221;: run the <font face='Courier'>xattr</font> "
        "command above, then try Method 1 again.",
        "App still inside the .dmg: make sure you actually copied "
        "<font face='Courier'>Kalulu.app</font> to <b>/Applications</b>, then "
        "ejected the .dmg.",
        "Paths with spaces: keep the quotes in commands, e.g. "
        "<font face='Courier'>&quot;/Applications/Kalulu app.app&quot;</font>.",
        "No <b>Open Anyway</b> button: attempt one launch just before, then return "
        "to Privacy &amp; Security.",
        "After the first successful launch, future launches work by double-click.",
    ]),

    ("heading2", "When in doubt"),
    ("para", "If you don&#8217;t recognize the app or its origin, don&#8217;t open "
             "it and contact the publisher for a signed / notarized build."),
]

# The French follows the English block for block. Controls are named as a French
# system labels them: "Exécuter quand même" in SmartScreen, "Ouvrir quand même",
# "Réglages Système", "Confidentialité et sécurité" on macOS.

WINDOWS_FR = [
    ("steps", [
        "<b>Télécharger et placer les fichiers.</b> Décompressez "
        "<font face='Courier'>Kalulu-Windows-&lt;version&gt;.zip</font>, "
        "téléchargé depuis la page des versions. Gardez ensemble, dans le même "
        "dossier de votre ordinateur, les deux fichiers qu’il contient"
        f"{NBSP}: <font face='Courier'>Kalulu-Windows.exe</font> et "
        "<font face='Courier'>libgdsqlite.windows.template_release.x86_64.dll</font>.",
        "<b>Lancer le programme.</b> Double-cliquez sur "
        "<font face='Courier'>Kalulu-Windows.exe</font>.",
        "<b>En cas d’avertissement de sécurité.</b> Si un message indique que le "
        "programme n’est pas reconnu ou qu’il a été bloqué, cherchez une option "
        f"comme <b>{guillemets('Exécuter quand même')}</b> ou "
        f"<b>{guillemets('Autoriser l’exécution')}</b>, et cliquez dessus pour "
        "continuer.",
    ]),
    ("callout", (f"C’est prêt{NBSP}!",
                 "Le jeu devrait maintenant se lancer et fonctionner normalement.")),
]

MACOS_FR = [
    ("callout", ("Important", (
        "N’exécutez Kalulu que si vous avez entièrement confiance en sa "
        f"provenance. Des messages comme {guillemets('L’application est endommagée')} "
        f"ou {guillemets('Apple ne peut pas vérifier l’absence de logiciel malveillant')} "
        "signifient souvent que l’application n’est pas signée ou qu’elle est "
        "marquée comme mise en quarantaine (pas forcément qu’elle est corrompue)."
    ))),
    ("heading2", "Télécharger et installer"),
    ("steps", [
        "Retrouvez le fichier téléchargé, en général dans <b>Téléchargements</b>"
        f"{NBSP}: <font face='Courier'>Kalulu-macOS-&lt;version&gt;.zip</font> "
        "depuis la page des versions, ou <font face='Courier'>Kalulu.dmg</font>.",
        "Ouvrez-le. Un zip se décompresse en "
        f"<font face='Courier'>Kalulu.app</font>{NBSP}; un .dmg ouvre un volume "
        "<i>Kalulu</i> dans le Finder.",
        "Faites glisser <font face='Courier'>Kalulu.app</font> dans "
        "<b>Applications</b>.",
        "Si vous avez ouvert un .dmg, éjectez le volume <i>Kalulu</i> depuis le "
        "Finder (l’icône d’éjection).",
    ]),
    ("note", f"Pour faire la copie dans le Terminal{NBSP}:"),
    ("code", ['cp -R "/Volumes/Kalulu/Kalulu.app" "/Applications/Kalulu.app"']),

    ("heading2", f"Méthode 1 {CHEVRON} Clic droit, Ouvrir (recommandé)"),
    ("steps", [
        "Ouvrez <b>/Applications</b>.",
        "Faites un clic droit (ou Ctrl-clic) sur "
        f"<font face='Courier'>Kalulu.app</font> {CHEVRON} <b>Ouvrir</b>.",
        "Dans la fenêtre "
        f"{guillemets('<i>provient d’un développeur non identifié</i>')}, "
        "cliquez sur <b>Ouvrir</b>.",
    ]),
    ("note", f"macOS crée alors une exception Gatekeeper{NBSP}: dès le deuxième "
             "lancement, un double-clic normal suffit."),

    ("heading2", f"Méthode 2 {CHEVRON} Réglages Système, Confidentialité et sécurité"),
    ("steps", [
        "Essayez d’abord un double-clic sur "
        f"<font face='Courier'>Kalulu.app</font>{NBSP}: laissez macOS le bloquer, "
        "puis fermez l’alerte.",
        f"Allez dans le menu Pomme {CHEVRON} <b>Réglages Système</b> {CHEVRON} "
        "<b>Confidentialité et sécurité</b> (versions plus anciennes"
        f"{NBSP}: <b>Préférences Système</b> {CHEVRON} "
        "<b>Sécurité et confidentialité</b>).",
        "Faites défiler jusqu’à "
        f"{guillemets('<i>Kalulu.app a été bloqué…</i>')}.",
        "Cliquez sur <b>Ouvrir quand même</b>, puis confirmez avec <b>Ouvrir</b>.",
    ]),

    ("heading2", f"Méthode 3 {CHEVRON} Terminal, pour le message "
                 f"{guillemets('est endommagé')}"),
    ("para", "Ce message vient souvent de l’attribut de quarantaine. Supprimez-le "
             "avec le Terminal (<b>Applications</b> " + CHEVRON + " <b>Utilitaires</b> "
             + CHEVRON + f" <b>Terminal</b>){NBSP}:"),
    ("code", ['xattr -dr com.apple.quarantine "/Applications/Kalulu.app"']),
    ("note", "Relancez ensuite Kalulu.app, idéalement avec la méthode 1 "
             "(clic droit, Ouvrir)."),

    ("heading2", f"Avancé{NBSP}: désactiver temporairement Gatekeeper (déconseillé)"),
    ("para", "À n’utiliser que si tout ce qui précède a échoué."),
    ("code", [
        "# Désactiver Gatekeeper",
        "sudo spctl --master-disable",
        "# Ouvrir l'application une fois",
        'open "/Applications/Kalulu.app"',
        "# Réactiver Gatekeeper",
        "sudo spctl --master-enable",
    ]),

    ("heading2", "Dépannage rapide"),
    ("bullets", [
        f"Rien ne se passe au double-clic{NBSP}: utilisez la méthode 1 "
        "(clic droit, Ouvrir).",
        f"Le message {guillemets('endommagé')} s’affiche encore{NBSP}: lancez la "
        "commande <font face='Courier'>xattr</font> ci-dessus, puis réessayez la "
        "méthode 1.",
        f"L’application est restée dans le .dmg{NBSP}: vérifiez que vous avez bien "
        "copié <font face='Courier'>Kalulu.app</font> dans <b>/Applications</b>, "
        "puis éjecté le .dmg.",
        f"Chemins contenant des espaces{NBSP}: gardez les guillemets dans les "
        "commandes, par exemple "
        "<font face='Courier'>&quot;/Applications/Kalulu app.app&quot;</font>.",
        f"Pas de bouton <b>Ouvrir quand même</b>{NBSP}: tentez un lancement juste "
        "avant, puis revenez dans Confidentialité et sécurité.",
        "Après le premier lancement réussi, un simple double-clic suffit pour les "
        "suivants.",
    ]),

    ("heading2", "En cas de doute"),
    ("para", "Si vous ne reconnaissez pas l’application ou sa provenance, ne "
             "l’ouvrez pas et demandez à l’éditeur une version signée / notarisée."),
]

LANGUAGES = {
    "en": {
        "file": "Kalulu Installation Help EN.pdf",
        "title": "Kalulu - Installation Help",
        "subject": "Installing and launching Kalulu on Windows and macOS",
        "intro": "Installing and launching Kalulu on a desktop computer. "
                 "Read only the section for the machine you are using.",
        "contents": "Contents",
        "sections": [
            ("Windows", "Windows 10 and Windows 11", WINDOWS_EN),
            ("macOS", "macOS 10.13 and later", MACOS_EN),
        ],
    },
    "fr": {
        "file": "Kalulu Aide Installation FR.pdf",
        "title": "Kalulu - Aide à l’installation",
        "subject": "Installer et lancer Kalulu sous Windows et macOS",
        "intro": "Installer et lancer Kalulu sur un ordinateur. "
                 "Ne lisez que la section correspondant à votre machine.",
        "contents": "Sommaire",
        "sections": [
            ("Windows", "Windows 10 et Windows 11", WINDOWS_FR),
            ("macOS", "macOS 10.13 et versions ultérieures", MACOS_FR),
        ],
    },
}


# --- styles ------------------------------------------------------------------

def styles() -> dict[str, ParagraphStyle]:
    theme.register_fonts()
    body = ParagraphStyle(
        "body", fontName=theme.BODY, fontSize=10.5, leading=15,
        textColor=theme.GREY_DARK, alignment=TA_LEFT, spaceAfter=5,
    )
    return {
        "title": ParagraphStyle(
            "title", parent=body, fontName=theme.DISPLAY, fontSize=26, leading=31,
            textColor=theme.PURPLE, spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=body, fontSize=11.5, leading=16,
            textColor=theme.GREY, spaceAfter=14,
        ),
        "h1": ParagraphStyle(
            "h1", parent=body, fontName=theme.DISPLAY, fontSize=19, leading=24,
            textColor=theme.PURPLE, spaceBefore=0, spaceAfter=2,
        ),
        "h1sub": ParagraphStyle(
            "h1sub", parent=body, fontSize=10, leading=14, textColor=theme.GREY,
            spaceAfter=12,
        ),
        "h2": ParagraphStyle(
            "h2", parent=body, fontName=theme.BODY_BOLD, fontSize=12.5, leading=17,
            textColor=theme.NAVY, spaceBefore=13, spaceAfter=5, keepWithNext=1,
        ),
        "body": body,
        "note": ParagraphStyle(
            "note", parent=body, fontSize=9.8, leading=14, textColor=theme.GREY,
            leftIndent=4,
        ),
        "step": ParagraphStyle("step", parent=body, leading=15),
        "num": ParagraphStyle(
            "num", parent=body, fontName=theme.BODY_BOLD, textColor=theme.PURPLE,
            alignment=2,
        ),
        "code": ParagraphStyle(
            "code", fontName="Courier", fontSize=8.8, leading=12.5,
            textColor=theme.NAVY,
        ),
        "callout_t": ParagraphStyle(
            "callout_t", fontName=theme.BODY_BOLD, fontSize=10.5, leading=15,
            textColor=theme.PURPLE, spaceAfter=2,
        ),
        "callout_b": ParagraphStyle(
            "callout_b", fontName=theme.BODY, fontSize=10, leading=14.5,
            textColor=theme.GREY_DARK,
        ),
        "toc": ParagraphStyle(
            "toc", fontName=theme.BODY_BOLD, fontSize=13, leading=24,
            textColor=theme.NAVY,
        ),
    }


def _boxed(rows, bg, bar) -> Table:
    """A left-barred, tinted block - used for callouts and code."""
    t = Table([[""] + [rows]], colWidths=[3 * mm, theme.CONTENT_WIDTH - 3 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), bar),
        ("BACKGROUND", (1, 0), (1, -1), bg),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, -1), 0),
        ("LEFTPADDING", (1, 0), (1, -1), 8),
        ("RIGHTPADDING", (1, 0), (1, -1), 8),
        ("TOPPADDING", (1, 0), (1, -1), 7),
        ("BOTTOMPADDING", (1, 0), (1, -1), 7),
    ]))
    return t


def blocks_to_flowables(blocks, st) -> list:
    out = []
    for kind, payload in blocks:
        if kind == "heading2":
            out.append(Paragraph(payload, st["h2"]))
        elif kind == "para":
            out.append(Paragraph(payload, st["body"]))
        elif kind == "note":
            out.append(Spacer(1, 1))
            out.append(Paragraph(payload, st["note"]))
        elif kind == "steps":
            rows = [[Paragraph(f"{i}.", st["num"]), Paragraph(text, st["step"])]
                    for i, text in enumerate(payload, 1)]
            t = Table(rows, colWidths=[8 * mm, theme.CONTENT_WIDTH - 8 * mm])
            t.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (0, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            out.append(t)
        elif kind == "bullets":
            for text in payload:
                rows = [[Paragraph("&bull;", st["num"]), Paragraph(text, st["step"])]]
                t = Table(rows, colWidths=[6 * mm, theme.CONTENT_WIDTH - 6 * mm])
                t.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]))
                out.append(t)
        elif kind == "code":
            lines = [Paragraph(l.replace("&", "&amp;").replace("<", "&lt;"), st["code"])
                     for l in payload]
            out.append(Spacer(1, 3))
            out.append(_boxed(lines, theme.LAVENDER, theme.NAVY))
            out.append(Spacer(1, 5))
        elif kind == "callout":
            title, text = payload
            inner = [Paragraph(title, st["callout_t"]), Paragraph(text, st["callout_b"])]
            out.append(Spacer(1, 4))
            out.append(_boxed(inner, theme.LAVENDER, theme.PURPLE))
            out.append(Spacer(1, 6))
    return out


class HelpDoc(BaseDocTemplate):
    """Two-pass build so the contents page carries real page numbers."""

    def __init__(self, path, st, lang):
        super().__init__(
            str(path), pagesize=theme.PAGE_SIZE,
            leftMargin=theme.MARGIN_LEFT, rightMargin=theme.MARGIN_RIGHT,
            topMargin=theme.MARGIN_TOP, bottomMargin=theme.MARGIN_BOTTOM,
            title=lang["title"], author="Excello Recherche & Education",
            subject=lang["subject"],
        )
        self.st = st
        self.help_title = lang["title"]
        frame = Frame(self.leftMargin, self.bottomMargin,
                      self.width, self.height, id="body")
        self.addPageTemplates([PageTemplate(id="page", frames=[frame],
                                            onPage=self._decorate)])

    def _decorate(self, canv, doc):
        canv.saveState()
        canv.setFont(theme.BODY, 8)
        canv.setFillColor(theme.GREY)
        canv.drawString(theme.MARGIN_LEFT, 11 * mm, self.help_title)
        canv.drawRightString(theme.PAGE_SIZE[0] - theme.MARGIN_RIGHT, 11 * mm,
                             str(canv.getPageNumber()))
        canv.setStrokeColor(theme.GREY_LIGHTER)
        canv.setLineWidth(0.5)
        canv.line(theme.MARGIN_LEFT, 14 * mm,
                  theme.PAGE_SIZE[0] - theme.MARGIN_RIGHT, 14 * mm)
        canv.restoreState()

    def afterFlowable(self, flowable):
        if getattr(flowable, "_toc_key", None):
            text = flowable.getPlainText()
            key = flowable._toc_key
            self.canv.bookmarkPage(key)
            self.notify("TOCEntry", (0, text, self.page, key))
            self.canv.addOutlineEntry(text, key, level=0, closed=False)


def build(code: str) -> Path:
    lang = LANGUAGES[code]
    st = styles()
    story: list = [
        Paragraph(lang["title"], st["title"]),
        Paragraph(lang["intro"], st["subtitle"]),
    ]

    toc = TableOfContents()
    toc.levelStyles = [st["toc"]]
    story += [Paragraph(lang["contents"], st["h2"]), toc]

    for i, (name, sub, blocks) in enumerate(lang["sections"]):
        if i:
            story.append(PageBreak())
        else:
            story.append(Spacer(1, 10))
        head = Paragraph(name, st["h1"])
        head._toc_key = f"sec-{name.lower()}"
        story.append(KeepTogether([head, Paragraph(sub, st["h1sub"])]))
        story += blocks_to_flowables(blocks, st)

    out = OUT_DIR / lang["file"]
    out.parent.mkdir(parents=True, exist_ok=True)
    HelpDoc(out, st, lang).multiBuild(story)
    return out


if __name__ == "__main__":
    codes = sys.argv[1:] or list(LANGUAGES)
    unknown = [c for c in codes if c not in LANGUAGES]
    if unknown:
        sys.exit(f"unknown language: {', '.join(unknown)} (have: {', '.join(LANGUAGES)})")
    for code in codes:
        p = build(code)
        print(f"wrote {p}  ({p.stat().st_size / 1024:.0f} KB)")
