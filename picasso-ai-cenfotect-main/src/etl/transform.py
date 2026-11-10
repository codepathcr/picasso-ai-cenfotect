"""Pure HTML -> dict parsers for every page type of the Online Picasso Project.

Nothing here touches the network: every function takes an HTML string and returns
plain Python data, so the parsers can be unit-tested with saved fixtures.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from bs4 import BeautifulSoup, NavigableString, Tag

OPP_ID_RE = re.compile(r"OPP\.\d{2}:\d{3}[a-z]?")
CATALOGUED_RE = re.compile(r"([\d,]+) Catalogued (?:Items|Poems)")
ENTRIES_RE = re.compile(r"(\d+) (?:Entries|Articles|References|Collections)")
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december"]
SEASONS = {"spring": (3, 5), "summer": (6, 8), "autumn": (9, 11), "fall": (9, 11),
           "winter": (12, 2)}


# --- small helpers -------------------------------------------------------------
def soup_of(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def clean(text: str) -> str:
    """Collapse whitespace and strip surrounding punctuation noise."""
    return re.sub(r"\s+", " ", text).strip(" \n\t\xa0")


def strip_dot(text: str) -> str:
    return clean(text).strip(". ")


def params_of(href: str) -> dict[str, str]:
    """Query parameters of an `index.php?view=...` link."""
    return dict(parse_qsl(urlsplit(href.replace("\n", "")).query))


def count_catalogued(html: str) -> int | None:
    m = CATALOGUED_RE.search(html)
    return int(m.group(1).replace(",", "")) if m else None


def count_entries(html: str) -> int | None:
    m = ENTRIES_RE.search(html)
    return int(m.group(1)) if m else None


def last_page(html: str) -> int:
    pages = [int(p) for p in re.findall(r"[?&;]page=(\d+)", html)]
    return max(pages) if pages else 1


def is_server_error_page(html: str) -> bool:
    """The site occasionally answers with a bare MySQL error instead of a page."""
    return len(html) < 1500 and ("Commands out of sync" in html or "MySQL" in html)


# --- dates ---------------------------------------------------------------------
def normalize_date(raw: str) -> dict[str, Any]:
    """Turn OPP date strings into a sortable structure.

    Examples: "Early/1907", "[Winter~Spring]/1907", "[Early] [Spring] March~April/1907",
    "Pre-June/1907", "January 14-17,1941", "04/28/37", "[1890~1891] [~1892]".
    Precision is one of year, season, month, day; `uncertain` is True when the site
    wrapped part of the date in brackets.
    """
    text = clean(raw or "")
    years = [int(y) for y in re.findall(r"(?<!\d)(1[89]\d{2}|20\d{2})(?!\d)", text)]
    lowered = text.lower()
    month_hits = [i + 1 for i, m in enumerate(MONTHS) if re.search(rf"\b{m}\b", lowered)]
    season_hits = sorted((s for s in SEASONS if re.search(rf"\b{s}\b", lowered)),
                         key=lambda s: lowered.find(s))
    day = None
    m = re.search(r"\b([a-z]+) (\d{1,2})(?:[-~](\d{1,2}))?,", lowered)
    if m and m.group(1) in MONTHS:
        day = int(m.group(2))
    us_date = re.match(r"(\d{2})/(\d{2})/(\d{2})$", text)
    if us_date:
        month_hits, day = [int(us_date.group(1))], int(us_date.group(2))
        years = [1900 + int(us_date.group(3))]
    qualifiers = re.findall(r"\b(early|mid|late|end|pre|post|beginning)\b", lowered)
    if day:
        precision = "day"
    elif month_hits:
        precision = "month"
    elif season_hits:
        precision = "season"
    elif years:
        precision = "year"
    else:
        precision = "unknown"
    return {
        "raw": text,
        "year": years[0] if years else None,
        "year_end": years[-1] if years else None,
        "month_start": month_hits[0] if month_hits else (SEASONS[season_hits[0]][0] if season_hits else None),
        "month_end": month_hits[-1] if month_hits else (SEASONS[season_hits[-1]][1] if season_hits else None),
        "day": day,
        "precision": precision,
        "qualifiers": qualifiers,
        "uncertain": "[" in text,
    }


def split_dimensions(medium_dim: str) -> tuple[str, str | None]:
    """"Oil on canvas. 81 x 60 cm." -> ("Oil on canvas", "81 x 60 cm").

    The site also writes "25 cm", "74 x 60" (no unit) or "S/U" (unknown size), so the
    rule is simply: the last sentence is the size when it starts with a digit or is S/U.
    """
    parts = [strip_dot(p) for p in re.split(r"\.\s+(?=[\dS\[])", strip_dot(medium_dim))]
    parts = [p for p in parts if p]
    if len(parts) >= 2 and (parts[-1][0] in "0123456789[" or parts[-1].upper() == "S/U"):
        return ". ".join(parts[:-1]), parts[-1]
    return ". ".join(parts), None


def split_references(ids_text: str) -> tuple[str | None, list[str]]:
    """"OPP.07:005; DR:48; FM:36 ..." -> ("OPP.07:005", ["DR:48", "FM:36", ...])."""
    parts = [strip_dot(p) for p in ids_text.split(";")]
    parts = [p for p in parts if p and p.lower().rstrip(".") != "etc"]
    opp = next((p for p in parts if OPP_ID_RE.fullmatch(p)), None)
    return opp, [p for p in parts if p != opp]


# --- artworks: listings ----------------------------------------------------------
def _listing_cells(soup: BeautifulSoup) -> list[Tag]:
    """Info cells of the three listing layouts (yearly catalogue, summary, search)."""
    cells = soup.find_all("td", class_=re.compile(r"^(infoLarge[12]|Info)$"))
    return [td for td in cells if td.find("strong") and OPP_ID_RE.search(td.get_text())]


def _parse_listing_cell(td: Tag) -> dict[str, Any]:
    """Split one artwork cell into title / place / date / medium / collection / ids."""
    head, medium, collection, ids = [], "", [], []
    stage = "head"
    for child in td.children:
        if isinstance(child, Tag) and child.name == "span" and "MediumDim" in (child.get("class") or []):
            medium = child.get_text(); stage = "collection"; continue
        if isinstance(child, Tag) and child.name == "hr":
            stage = "ids"; continue
        if isinstance(child, Tag) and child.name == "br":
            continue
        text = child.get_text() if isinstance(child, Tag) else str(child)
        {"head": head, "collection": collection, "ids": ids}[stage].append(text)
    head_text = clean("".join(head))
    title_tag = td.find("strong")
    title = clean(title_tag.get_text()) if title_tag else ""
    rest = strip_dot(head_text[len(title):] if head_text.startswith(title) else head_text)
    place, date = _split_place_date(rest)
    medium_text, dimensions = split_dimensions(medium)
    coll_text = clean("".join(collection))
    coll_parts = [strip_dot(p) for p in re.split(r"\.\s+(?=[A-Z(])", coll_text) if strip_dot(p)]
    opp_id, references = split_references("".join(ids))
    return {
        "id": opp_id,
        "title": title,
        "place": place,
        "date_text": date,
        "date": normalize_date(date),
        "medium": medium_text,
        "dimensions": dimensions,
        "collection": coll_parts[0] if coll_parts else None,
        "credit_line": ". ".join(coll_parts[1:]) or None,
        "references": references,
    }


def _split_place_date(rest: str) -> tuple[str | None, str | None]:
    """"Paris. Early/1907" -> ("Paris", "Early/1907"); handles a missing place."""
    parts = [strip_dot(p) for p in re.split(r"\.\s+", rest) if strip_dot(p)]
    if not parts:
        return None, None
    if len(parts) == 1:
        return (None, parts[0]) if re.search(r"\d{4}", parts[0]) else (parts[0], None)
    return parts[0], ". ".join(parts[1:])


def parse_artwork_listing(html: str) -> list[dict[str, Any]]:
    """Artworks of a yearly catalogue (ArtworkLarge), a Summary page or a search result."""
    soup = soup_of(html)
    items = []
    for td in _listing_cells(soup):
        item = _parse_listing_cell(td)
        row = td.find_parent("tr")
        img = row.find("img", src=re.compile("thumbs")) if row else None
        item["thumbnail"] = img["src"].lstrip("./") if img else None
        if row:
            item["has"] = sorted({a.get_text(strip=True).lower() for a in row.find_all("a", class_="SmallControl")})
        items.append(item)
    return items


# --- artworks: detail pop-ups ------------------------------------------------------
def _label_rows(soup: BeautifulSoup, label_class: str) -> list[tuple[str, Tag]]:
    rows = []
    for label in soup.find_all("td", class_=label_class):
        value = label.find_next_sibling("td")
        if value is not None:
            rows.append((strip_dot(label.get_text()).rstrip(":"), value))
    return rows


def parse_artwork_details(html: str) -> dict[str, Any]:
    """The `ArtworkDetails` view: Title, Location, Date, Medium, Dimension, Collection,
    Catalogs (catalogue raisonné concordances), Books (literature), Exhibited."""
    soup = soup_of(html)
    data: dict[str, Any] = {}
    for label, value in _label_rows(soup, "InfoLabel"):
        key = label.lower()
        text = clean(value.get_text(" "))
        if key in ("catalogs", "books", "exhibited"):
            data[key] = [strip_dot(p) for p in text.split(";") if strip_dot(p)]
        else:
            data[key] = text
    return data


def parse_provenance(html: str) -> list[dict[str, Any]]:
    """The `former` view: ordered list of owners with place, date and price."""
    soup = soup_of(html)
    rows = []
    for label in soup.find_all("td", class_="Label"):
        cells = [clean(td.get_text(" ")) for td in label.find_next_siblings("td")]
        if not cells:
            continue
        rows.append({"order": strip_dot(label.get_text()).rstrip(":"),
                     "owner": cells[0], "place": cells[1] if len(cells) > 1 else None,
                     "date": cells[2] if len(cells) > 2 else None,
                     "price": cells[3] if len(cells) > 3 else None})
    return rows


def _parse_citation_list(html: str) -> list[dict[str, Any]]:
    """Shared by exhibitions, literature and the references index: one <li> per entry."""
    soup = soup_of(html)
    entries = []
    for li in soup.find_all("li"):
        entry: dict[str, Any] = {"text": clean(li.get_text(" "))}
        for span in li.find_all("span", class_=True):
            text = clean(span.get_text(" "))
            if text:
                entry.setdefault(span["class"][0].lower(), text)
        entry["codes"] = sorted(set(re.findall(r"\[([A-Z]{2}\.\d{2}[a-z]?\*?)\]", entry["text"])))
        entry["opp_ids"] = sorted(set(OPP_ID_RE.findall(entry["text"])))
        if entry["text"]:
            entries.append(entry)
    return entries


def parse_exhibitions(html: str) -> list[dict[str, Any]]:
    """The `exhibitedPrint` view."""
    return _parse_citation_list(html)


def parse_literature(html: str) -> list[dict[str, Any]]:
    """The `bibliography` view."""
    return _parse_citation_list(html)


def parse_note(html: str) -> list[dict[str, str]]:
    """The `note` view: (label, text) pairs; a new 'Source' label starts a new source."""
    soup = soup_of(html)
    return [{"label": label, "text": clean(value.get_text(" "))}
            for label, value in _label_rows(soup, "noteTitle")]


def parse_commentary(html: str) -> list[dict[str, Any]]:
    """The `commentary` view: remarks, each with the OPP ids it cross-references."""
    soup = soup_of(html)
    remarks = []
    for label, value in _label_rows(soup, "commentaryTitle"):
        text = clean(value.get_text(" "))
        remarks.append({"label": label, "text": text,
                        "related_ids": sorted(set(OPP_ID_RE.findall(text)))})
    return remarks


# --- biography -------------------------------------------------------------------
def parse_bio_index(html: str) -> list[dict[str, Any]]:
    """One yearly biography page: entries with date descriptor, narrative and links."""
    soup = soup_of(html)
    entries = []
    for duration in soup.find_all("td", class_="duration"):
        title_td = duration.find_next_sibling("td", class_="title")
        if title_td is None:
            continue
        date_desc = clean(duration.find(string=True, recursive=False) or "").rstrip(":")
        entry: dict[str, Any] = {"date_desc": date_desc, "text": "", "links": {}}
        for strip in title_td.find_all("table", class_="ImageStrip"):
            entry["images"] = [img.get("src", "").lstrip("./") for img in strip.find_all("img")]
            strip.decompose()
        entry["text"] = clean(title_td.get_text(" "))
        for a in duration.find_all("a", href=True) + title_td.find_all("a", href=True):
            p = params_of(a["href"])
            view = p.pop("view", "")
            entry["links"].setdefault(view, []).append(p)
        entry["opp_ids"] = sorted(set(OPP_ID_RE.findall(entry["text"])))
        entries.append(entry)
    return entries


def parse_bio_commentary(html: str) -> list[str]:
    soup = soup_of(html)
    return [clean(v.get_text(" ")) for _, v in _label_rows(soup, "commentaryTitle")]


def parse_bio_tree(html: str) -> list[dict[str, str]]:
    """The `bioTree` view: places and people as (id, name, path) rows."""
    soup = soup_of(html)
    rows = []
    for a in soup.find_all("a", href=re.compile("BioResource")):
        rid = params_of(a["href"]).get("id", "")
        path = [clean(x.get_text()) for x in a.find_parents("blockquote")]
        ancestors = []
        for bq in a.find_parents("blockquote"):
            prev = bq.find_previous_sibling("table")
            if prev:
                ancestors.append(clean(prev.get_text()))
        rows.append({"id": rid, "name": clean(a.get_text()), "path": list(reversed(ancestors))})
    return rows


def parse_bio_resource(html: str) -> dict[str, Any]:
    """A place or person page (`BioResource`): name, introduction, captioned photos."""
    soup = soup_of(html)
    h2 = soup.find("h2")
    intro = soup.find("div", id="Panel1")
    photos = []
    for gallery in soup.find_all("table", class_="ThumbGallery"):
        a = gallery.find("a", href=True)
        caption = gallery.find("td", class_="Biocontent")
        photos.append({"zoom": params_of(a["href"]).get("img") if a else None,
                       "caption": clean(caption.get_text(" ")) if caption else None})
    intro_text = clean(intro.get_text(" ")) if intro and not intro.find("table", class_="ThumbGallery") else ""
    return {"name": clean(h2.get_text()) if h2 else None, "introduction": intro_text, "photos": photos}


# --- writings, archives, collections, references -------------------------------------
def parse_writings_index(html: str) -> list[dict[str, Any]]:
    soup = soup_of(html)
    rows = []
    for a in soup.find_all("a", href=re.compile("WritingsInfo")):
        p = params_of(a["href"])
        duration = a.find_parent("tr").find("td", class_="duration")
        rows.append({"mid": p.get("mid"), "year": p.get("year"), "title": clean(a.get_text()),
                     "date_text": clean(duration.get_text()) if duration else None})
    return rows


def parse_writing(html: str) -> dict[str, Any]:
    soup = soup_of(html)
    title = soup.find("span", class_="poemTitle")
    duration = soup.find("span", class_="Duration")
    paragraphs = [clean(p.get_text(" ")) for p in soup.find_all("p", id="pline")]
    return {"title": clean(title.get_text()) if title else None,
            "date_text": clean(duration.get_text()) if duration else None,
            "text": "\n".join(p for p in paragraphs if p)}


def parse_archives_index(html: str) -> list[dict[str, Any]]:
    soup = soup_of(html)
    rows = []
    for a in soup.find_all("a", class_="ArticleLink"):
        tr = a.find_parent("tr")
        flag = tr.find("img", src=re.compile("languagepin"))
        pub = tr.find("td", class_="Publisher")
        date = tr.find("td", class_="Date")
        p = params_of(a["href"])
        rows.append({"id": p.get("id"), "year": p.get("year"), "title": clean(a.get_text()),
                     "language": re.search(r"languagepin-(\w+)", flag["src"]).group(1) if flag else None,
                     "publisher": clean(pub.get_text()) if pub else None,
                     "date_text": clean(date.get_text()) if date else None})
    return rows


def parse_archive_article(html: str) -> dict[str, Any]:
    soup = soup_of(html)
    container = soup.find("td", class_="Container")
    publisher = container.find("font") if container else None
    title = container.find("h2") if container else None
    date_cell = container.find("td", align="left") if container else None
    dateline = date_cell.find("i") if date_cell else None
    body = soup.find("div", id="ArticleBody")
    text = clean(body.get_text(" ")) if body else ""
    return {"publisher": clean(publisher.get_text()) if publisher else None,
            "title": clean(title.get_text()) if title else None,
            "dateline": clean(dateline.get_text()) if dateline else None,
            "text": text}


def parse_collections_index(html: str) -> list[dict[str, Any]]:
    soup = soup_of(html)
    rows = []
    for a in soup.find_all("a", href=re.compile("ListArtworkSearch")):
        count_text = a.find_next(string=re.compile(r"\d"))
        m = re.search(r"\d+", count_text or "")
        rows.append({"name": clean(a.get_text()), "count": int(m.group()) if m else None,
                     "search": params_of(a["href"])})
    return rows


def parse_references_index(html: str) -> list[dict[str, Any]]:
    return _parse_citation_list(html)


def parse_dated_artworks(html: str) -> list[str]:
    return sorted(set(OPP_ID_RE.findall(html)))


# --- helpers shared by the ETL phases -------------------------------------------------
def safe_id(opp_id: str) -> str:
    """"OPP.07:005" -> "OPP.07_005" (a file-system safe folder name)."""
    return opp_id.replace(":", "_")


def image_alpha(opp_id: str) -> str:
    """"OPP.07:005" -> "opp07-005", the name the site uses for image files."""
    m = re.fullmatch(r"OPP\.(\d{2}):(\d{3}[a-z]?)", opp_id)
    if not m:
        raise ValueError(f"OPP id inesperado: {opp_id}")
    return f"opp{m.group(1)}-{m.group(2)}"


def parse_checkboxes(html: str, prefix: str) -> list[dict[str, str]]:
    """Checkbox inputs whose name starts with `prefix` (GuideList periods / themes)."""
    soup = soup_of(html)
    return [{"param": cb["name"], "value": cb["value"]}
            for cb in soup.find_all("input", {"type": "checkbox"})
            if cb.get("name", "").startswith(prefix)]


def _month_number(word: str) -> int | None:
    """Tolerates the site's typos ("Febuary") by matching the first three letters."""
    word = word.lower()[:3]
    for i, name in enumerate(MONTHS):
        if name.startswith(word):
            return i + 1
    return None


def _days_in_month(year: int, month: int) -> int:
    import calendar
    return calendar.monthrange(year, month)[1]


def _iso(year: int, month: int, day: int) -> str:
    return f"{year:04d}-{month:02d}-{day:02d}"


def date_range(text: str, year: int | None = None) -> dict[str, Any] | None:
    """Turn an OPP date descriptor into an inclusive ISO range {start, end, precision}.

    Works for artwork dates ("Early/1907", "March~April/1907", "January 14-17,1941",
    "[Winter~Spring]/1907") and biography descriptors ("Early-March", "March 20",
    "Year-Forth", "Spring", "March ~ April") when `year` is given. Qualifiers such as
    Early/Mid/Late are kept as the whole unit (month, season or year): they describe
    the OPP's confidence, not a sharper range. Returns None without a usable year.
    """
    lowered = clean(text or "").lower()
    years = [int(y) for y in re.findall(r"(?<!\d)(1[89]\d{2}|20\d{2})(?!\d)", lowered)]
    us_date = re.search(r"(\d{2})/(\d{2})/(\d{2})\b", lowered)
    if us_date and not years:
        years = [1900 + int(us_date.group(3))]
    y0 = years[0] if years else year
    y1 = years[-1] if years else year
    if y0 is None:
        return None
    months = [_month_number(w) for w in re.findall(r"\b([a-z]{3,9})\b", lowered)]
    months = [m for m in months if m]
    seasons = sorted((s for s in SEASONS if re.search(rf"\b{s}\b", lowered)), key=lowered.find)
    day_hits = re.findall(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.? (\d{1,2})(?:\s*[-~]\s*(\d{1,2}))?", lowered)
    if us_date:
        m, d = int(us_date.group(1)), int(us_date.group(2))
        return {"start": _iso(y0, m, d), "end": _iso(y0, m, d), "precision": "day"}
    if day_hits:
        d0 = int(day_hits[0][0])
        d1 = int(day_hits[-1][1] or day_hits[-1][0])
        m0, m1 = (months[0], months[-1]) if months else (1, 12)
        try:
            return {"start": _iso(y0, m0, d0), "end": _iso(y1, m1, d1), "precision": "day"}
        except ValueError:
            pass
    if months:
        m0, m1 = months[0], months[-1]
        end_year = y1 if m1 >= m0 or y1 > y0 else y1 + 1
        return {"start": _iso(y0, m0, 1), "end": _iso(end_year, m1, _days_in_month(end_year, m1)),
                "precision": "month"}
    if seasons:
        m0 = SEASONS[seasons[0]][0]
        m1 = SEASONS[seasons[-1]][1]
        end_year = y1 if m1 >= m0 else y1 + 1
        if seasons[0] == "winter":
            m0 = 1  # the site uses Winter for the start of the year
            end_year = y1 if len(seasons) > 1 else y1
        return {"start": _iso(y0, m0, 1), "end": _iso(end_year, m1, _days_in_month(end_year, m1)),
                "precision": "season"}
    return {"start": _iso(y0, 1, 1), "end": _iso(y1, 12, 31), "precision": "year"}


def ranges_overlap(a: dict[str, Any] | None, b: dict[str, Any] | None) -> bool:
    return bool(a and b and a["start"] <= b["end"] and b["start"] <= a["end"])
