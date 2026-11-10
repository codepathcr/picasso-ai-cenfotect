"""Parser tests against real pages saved in tests/fixtures/ (text only, no images)."""

from pathlib import Path

import pytest

from src.etl import transform as T

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# --- dates --------------------------------------------------------------------------
@pytest.mark.parametrize("raw, year, precision, qualifiers, uncertain", [
    ("Early/1907", 1907, "year", ["early"], False),
    ("[Winter~Spring]/1907", 1907, "season", [], True),
    ("[Early] [Spring] March~April/1907", 1907, "month", ["early"], True),
    ("January 14-17,1941", 1941, "day", [], False),
    ("04/28/37", 1937, "day", [], False),
])
def test_normalize_date(raw, year, precision, qualifiers, uncertain):
    d = T.normalize_date(raw)
    assert (d["year"], d["precision"], d["qualifiers"], d["uncertain"]) == (year, precision, qualifiers, uncertain)


@pytest.mark.parametrize("text, year, start, end, precision", [
    ("Early/1907", None, "1907-01-01", "1907-12-31", "year"),
    ("March~April/1907", None, "1907-03-01", "1907-04-30", "month"),
    ("January 14-17,1941", None, "1941-01-14", "1941-01-17", "day"),
    ("[Winter~Spring]/1907", None, "1907-01-01", "1907-05-31", "season"),
    ("Autumn~Winter/1907", None, "1907-09-01", "1908-02-29", "season"),
    ("Early-March", 1907, "1907-03-01", "1907-03-31", "month"),
    ("March 20", 1907, "1907-03-20", "1907-03-20", "day"),
    ("Year-Forth", 1907, "1907-01-01", "1907-12-31", "year"),
    ("Febuary", 1907, "1907-02-01", "1907-02-28", "month"),  # the site's own typo
])
def test_date_range(text, year, start, end, precision):
    assert T.date_range(text, year) == {"start": start, "end": end, "precision": precision}


def test_date_range_without_year_is_none():
    assert T.date_range("Spring") is None


def test_ranges_overlap():
    a = T.date_range("March~April/1907")
    assert T.ranges_overlap(a, T.date_range("April 10", 1907))
    assert not T.ranges_overlap(a, T.date_range("May", 1907))


# --- small helpers ------------------------------------------------------------------
def test_split_dimensions():
    assert T.split_dimensions("Oil on canvas. 81 x 60 cm.") == ("Oil on canvas", "81 x 60 cm")
    assert T.split_dimensions("Wood, carved & painted [OiC]. 25 cm") == ("Wood, carved & painted [OiC]", "25 cm")
    assert T.split_dimensions("Pencil on paper. S/U") == ("Pencil on paper", "S/U")
    assert T.split_dimensions("Pencil on paper") == ("Pencil on paper", None)


def test_split_references():
    assert T.split_references("OPP.07:005; DR:48; FM:36; etc.") == ("OPP.07:005", ["DR:48", "FM:36"])


def test_ids_and_image_names():
    assert T.safe_id("OPP.07:005") == "OPP.07_005"
    assert T.image_alpha("OPP.07:005") == "opp07-005"
    with pytest.raises(ValueError):
        T.image_alpha("DR:48")


def test_server_error_page_detection():
    assert T.is_server_error_page("<b>Warning</b>: MySQL Commands out of sync")
    assert not T.is_server_error_page(fixture("summary_1907_p1.html"))


# --- artworks -----------------------------------------------------------------------
def test_parse_yearly_catalogue():
    items = T.parse_artwork_listing(fixture("catalogue_1907_sculpture.html"))
    assert len(items) == 12
    first = items[0]
    assert first["id"] == "OPP.07:388"
    assert first["title"] == "Figure"
    assert first["place"] == "Paris"
    assert first["date_text"] == "Winter~Spring/1907"
    assert first["date"]["precision"] == "season"
    assert first["medium"].startswith("Wood, carved")
    assert first["dimensions"] == "25 cm"
    assert first["collection"] == "The Picasso Estate"
    assert "Z.IIb:608" in first["references"]
    assert first["thumbnail"] == "graphics/1907/ythumbs/yopp07-388.jpg"


def test_parse_summary_listing_flags_and_pagination():
    html = fixture("summary_1907_p1.html")
    items = T.parse_artwork_listing(html)
    assert len(items) == 30
    assert items[0]["id"] == "OPP.07:005"
    assert items[0]["has"] == ["commentary", "exhibited", "literature", "notes", "provenance", "zoom"]
    assert T.count_catalogued(html) == 240
    assert T.last_page(html) == 8


def test_parse_artwork_details():
    d = T.parse_artwork_details(fixture("artwork_details.html"))
    assert d["title"] == "Portrait de Max Jacob"
    assert d["location"] == "Paris"
    assert "OPP.07:005" in d["catalogs"]


def test_parse_provenance():
    rows = T.parse_provenance(fixture("artwork_provenance.html"))
    assert rows[0]["order"] == "1"
    assert rows[0]["owner"] == "Raoul Pellequer"
    assert rows[0]["place"] == "Paris"


def test_parse_exhibitions_and_literature():
    exh = T.parse_exhibitions(fixture("artwork_exhibitions.html"))
    assert exh[0]["codes"] == ["WO.92", "WO.92*"]
    assert exh[0]["date"] == "1992"
    lit = T.parse_literature(fixture("artwork_literature.html"))
    assert lit[0]["author"] == "Camón Aznar, José"
    assert lit[0]["codes"] == ["JC.56"]


def test_parse_note_and_commentary():
    note = T.parse_note(fixture("artwork_note.html"))
    assert note[0] == {"label": "Source", "text": "Museum Ludwig, Köln 2020"}
    remarks = T.parse_commentary(fixture("artwork_commentary.html"))
    assert len(remarks) == 9
    assert remarks[0]["label"] == "Remarks"
    assert remarks[0]["text"].startswith("Alternative measurements")


# --- biography ----------------------------------------------------------------------
def test_parse_bio_index():
    entries = T.parse_bio_index(fixture("bio_1907_p1.html"))
    assert len(entries) == 20
    assert entries[0]["date_desc"] == "Year-Forth"
    assert entries[0]["text"].startswith('"In 1907, Max Jacob lived')
    assert "BioResource" in entries[0]["links"]
    dated = [e for e in entries if "DatedArtworksSummary" in e["links"]]
    assert dated and dated[0]["links"]["DatedArtworksSummary"][0]["startYear"] == "1907"


def test_parse_bio_commentary_tree_and_resource():
    assert T.parse_bio_commentary(fixture("bio_commentary.html"))[0].startswith("The content of form")
    tree = T.parse_bio_tree(fixture("bio_tree.html"))
    assert len(tree) == 143
    assert tree[3] == {"id": "carrer-davinyo", "name": "Carrer d'Avinyó", "path": ["Places", "Europe", "Spain", "Barcelona"]}
    assert any("People" in node["path"] for node in tree)
    resource = T.parse_bio_resource(fixture("bio_resource.html"))
    assert resource["name"] == "Le Bateau-Lavoir"
    assert len(resource["photos"]) == 22


# --- writings, archives, collections, references, guide ----------------------------
def test_parse_writings():
    html = fixture("writings_1935_p1.html")
    rows = T.parse_writings_index(html)
    assert rows[0] == {"mid": "437", "year": "1935", "title": "Un peintre avait une femme",
                       "date_text": "January-December,1935"}
    assert T.count_catalogued(html) == 142
    poem = T.parse_writing(fixture("writing_437.html"))
    assert poem["title"] == "Un peintre avait une femme"
    assert len(poem["text"]) > 100


def test_parse_archives():
    rows = T.parse_archives_index(fixture("archives_1990.html"))
    assert rows[0]["title"] == "When Picasso Spooked the F.B.I."
    assert rows[0]["publisher"] == "The New York Times"
    assert rows[0]["language"] == "en"
    article = T.parse_archive_article(fixture("archive_article.html"))
    assert article["title"] == "The Tragedy of Guernica"
    assert len(article["text"]) > 500


def test_parse_collections_references_and_guide():
    collections = T.parse_collections_index(fixture("collections_A_p1.html"))
    assert len(collections) == 86
    assert collections[0]["name"] == "A. C. Mazo Collection, Paris"
    assert collections[0]["search"]["SearchIn"] == "Collection"
    references = T.parse_references_index(fixture("references_A_p1.html"))
    assert len(references) == 30
    assert references[0]["codes"]
    periods = T.parse_checkboxes(fixture("guide_periods.html"), "StyleSearch")
    assert len(periods) == 71
    assert {"param": "StyleSearch1", "value": "Blue Period"} in periods or any(p["value"] == "Blue Period" for p in periods)
