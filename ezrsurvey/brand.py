"""Adopt an organisation's brand colours, fonts and template from its PowerPoint or Word theme. Charts and reports read the brand options this sets."""

import os
import re
import xml.etree.ElementTree as ElementTree
import zipfile

from .config import ezrsurvey_default, ezrsurvey_options
from .export import file_ext
from .rbase import warn

DRAWING_NAMESPACE = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
HEX_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$")
THEME_PATTERN = re.compile(r"(ppt|word)/theme/theme[0-9]+\.xml$")
BRAND_KEYS = [
    "brand_colors",
    "brand_color_primary",
    "brand_font_major",
    "brand_font_minor",
    "brand_template_pptx",
    "brand_template_docx",
]


def is_hex(value):
    return isinstance(value, str) and HEX_PATTERN.match(value) is not None


def extract_ooxml_theme(path):
    """The first theme part inside a .pptx or .docx, as XML text."""
    if not os.path.exists(path):
        raise ValueError(f"Template file '{path}' does not exist.")
    with zipfile.ZipFile(path) as archive:
        themes = sorted(name for name in archive.namelist() if THEME_PATTERN.search(name))
        if not themes:
            raise ValueError(f"'{path}' contains no OOXML theme part -- is it a valid .pptx / .docx file?")
        return archive.read(themes[0]).decode("utf-8")


def read_theme_colour(root, slot, fallback=None):
    node = root.find(f".//a:clrScheme/a:{slot}", DRAWING_NAMESPACE)
    if node is None:
        return fallback
    value = None
    rgb = node.find("./a:srgbClr", DRAWING_NAMESPACE)
    if rgb is not None:
        value = rgb.get("val")
    if value is None:
        system = node.find("./a:sysClr", DRAWING_NAMESPACE)
        if system is not None:
            value = system.get("lastClr")
    return fallback if value is None else "#" + value.upper()


def read_theme_font(root, slot):
    node = root.find(f".//a:fontScheme/a:{slot}/a:latin", DRAWING_NAMESPACE)
    face = None if node is None else node.get("typeface")
    if not face or face.startswith("+"):
        return None
    return face


def parse_ooxml_theme(xml_text):
    """Brand accents, dark and light colours, and heading and body typefaces from an OOXML theme."""
    if os.path.exists(str(xml_text)):
        with open(xml_text, encoding="utf-8") as handle:
            xml_text = handle.read()
    root = ElementTree.fromstring(xml_text)
    accents = []
    for i in range(1, 7):
        colour = read_theme_colour(root, f"accent{i}")
        if colour is not None:
            accents.append(colour)
    return {
        "accents": accents,
        "dark": read_theme_colour(root, "dk1", "#000000"),
        "light": read_theme_colour(root, "lt1", "#FFFFFF"),
        "font_major": read_theme_font(root, "majorFont"),
        "font_minor": read_theme_font(root, "minorFont"),
    }


def chosen_colours(accents, colors):
    """Accents and primary after the caller's own colours, invalid hex codes dropped with a warning."""
    primary = accents[0] if accents else None
    if colors is None:
        return {"accents": accents or None, "primary": primary}
    colors = [colors] if isinstance(colors, str) else list(colors)
    bad = [colour for colour in colors if not is_hex(colour)]
    if bad:
        warn("Dropping invalid hex colour(s): " + ", ".join(str(colour) for colour in bad))
        colors = [colour for colour in colors if is_hex(colour)]
    if len(colors) == 1:
        return {"accents": accents or colors, "primary": colors[0]}
    if len(colors) > 1:
        return {"accents": colors, "primary": colors[0]}
    return {"accents": accents or None, "primary": primary}


def chosen_fonts(theme, fonts):
    major = theme.get("font_major")
    minor = theme.get("font_minor")
    if isinstance(fonts, str):
        minor = fonts
    elif isinstance(fonts, dict):
        major = fonts.get("major", major)
        minor = fonts.get("minor", minor)
    elif fonts is not None:
        minor = list(fonts)[0]
    return {"major": major, "minor": minor}


def use_brand(template=None, colors=None, fonts=None, quiet=False):  # lint-style: ignore FN001
    """Adopt an organisation brand from a PowerPoint or Word template.

    Reads the colour and font theme out of your organisation's .pptx / .docx
    template and makes it the session default for everything ezrsurvey
    produces: charts pick up the brand accent colours and body font, and the
    template file itself becomes the default reference document for
    `report_new()`, `report_deck()` and `scaffold_report()`.

    Extraction reads the theme part inside the template: accent colours 1-6
    become ``brand_colors`` (first accent = ``brand_color_primary``, the default
    fill of `plot_bars()`), and the minor (body) typeface becomes the default
    font of `theme_ezrsurvey()`, but only when that font is installed on this
    machine. Set ``ezrsurvey_options(brand_fonts_enabled=False)`` to keep brand
    colours but ignore brand fonts. Everything lands in ordinary
    `ezrsurvey_options()` (``brand_*`` keys), so you can equally set the values
    by hand or persist them in a profile. Semantic palettes (``pal_rating``,
    ``pal_nps``) keep their meaning-carrying colours. Use `clear_brand()` to
    return to the neutral look.

    Parameters
    ----------
    template : str, optional
        Path to a .pptx or .docx file, registered as the default reference
        document for reports of that format. None to set colours and fonts
        directly without a template.
    colors : str or list of str, optional
        Hex colours overriding the extracted accents. A single colour sets only
        the primary; a list sets the full accent palette (first entry =
        primary). Invalid entries are dropped with a warning.
    fonts : str or dict, optional
        Typefaces overriding the extracted ones: a single body font, or
        ``{"major": ..., "minor": ...}``.
    quiet : bool
        If True, do not print the confirmation.

    Returns
    -------
    EzrsurveyBrand
        The active brand (see `brand_info()`).

    See Also
    --------
    brand_info, clear_brand, pal_brand, scale_fill_brand, report_new

    Examples
    --------
    >>> use_brand(colors=["#0B5394", "#E69138"], fonts="Georgia", quiet=True)
    >>> clear_brand()
    """
    theme = {}
    if template is not None:
        ext = file_ext(template)
        if ext not in ("pptx", "docx"):
            raise ValueError("`template` must be a .pptx or .docx file.")
        theme = parse_ooxml_theme(extract_ooxml_theme(template))
        ezrsurvey_options(**{f"brand_template_{ext}": os.path.abspath(template).replace("\\", "/")})
    if template is None and colors is None and fonts is None:
        raise ValueError("Provide a `template`, `colors`, or `fonts`.")
    colours = chosen_colours(theme.get("accents", []), colors)
    faces = chosen_fonts(theme, fonts)
    settings = {
        "brand_colors": colours["accents"],
        "brand_color_primary": colours["primary"],
        "brand_font_major": faces["major"],
        "brand_font_minor": faces["minor"],
    }
    kept = {key: value for key, value in settings.items() if value is not None}
    if kept:
        ezrsurvey_options(**kept)
    info = brand_info()
    if not quiet:
        print(repr(info))
    return info


class EzrsurveyBrand(dict):
    """The result of `brand_info()`: the brand options as a dict that prints as a short summary."""

    def __repr__(self):
        if all(value is None for value in self.values()):
            return "No brand set. See help(use_brand)."
        lines = ["ezrsurvey brand"]
        if self["colors"] is not None:
            colours = [self["colors"]] if isinstance(self["colors"], str) else self["colors"]
            lines.append("  colors:   " + " ".join(colours))
        if self["color_primary"] is not None:
            lines.append("  primary:  " + self["color_primary"])
        faces = [face for face in (self["font_major"], self["font_minor"]) if face is not None]
        if faces:
            lines.append("  fonts:    " + " / ".join(faces))
        if self["template_pptx"] is not None:
            lines.append("  pptx ref: " + self["template_pptx"])
        if self["template_docx"] is not None:
            lines.append("  docx ref: " + self["template_docx"])
        return "\n".join(lines)


def brand_info():
    """Show the active brand settings.

    Returns
    -------
    EzrsurveyBrand
        A dict with ``colors``, ``color_primary``, ``font_major``,
        ``font_minor``, ``template_pptx`` and ``template_docx``, each None when
        unset. Printing it shows a short summary.

    See Also
    --------
    use_brand, clear_brand

    Examples
    --------
    >>> brand_info()
    """
    return EzrsurveyBrand(
        colors=ezrsurvey_default("brand_colors"),
        color_primary=ezrsurvey_default("brand_color_primary"),
        font_major=ezrsurvey_default("brand_font_major"),
        font_minor=ezrsurvey_default("brand_font_minor"),
        template_pptx=ezrsurvey_default("brand_template_pptx"),
        template_docx=ezrsurvey_default("brand_template_docx"),
    )


def clear_brand():
    """Clear the active brand.

    Resets every ``brand_*`` option so charts and reports return to the neutral
    ezrsurvey defaults.

    Returns
    -------
    bool
        True.

    See Also
    --------
    use_brand

    Examples
    --------
    >>> clear_brand()
    """
    ezrsurvey_options(**{key: None for key in BRAND_KEYS})
    return True
