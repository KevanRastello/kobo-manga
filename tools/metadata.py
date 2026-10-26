"""Clean metadata for one chapter, before and after KCC.

    python tools/metadata.py comicinfo "One Piece 1196 - Some Title.cbz"
        Writes ComicInfo.xml (series, number, chapter title, author) into the .cbz,
        so KCC puts them into the e-book. Also prints how many pages are
        double-page spreads (wider than tall).

    python tools/metadata.py calibre "One Piece 1196 - Some Title.kepub.epub"
        Adds Calibre's series tags next to the EPUB3 ones KCC writes, so readers
        that only understand one of the two formats still see the series.

    python tools/metadata.py test
        Self-check.
"""
import io
import re
import sys
import zipfile
from xml.sax.saxutils import escape, quoteattr

AUTHOR = "Eiichiro Oda"
NAME_RE = re.compile(r"^(?P<series>.+?) (?P<number>\d+(?:\.\d+)?)(?: - (?P<title>.+))?$")


def parse_name(stem):
    """'One Piece 1196 - The Title' -> ('One Piece', '1196', 'The Title')."""
    m = NAME_RE.match(stem)
    if not m:
        raise ValueError(f"unexpected file name: {stem!r}")
    return m["series"], m["number"], m["title"] or ""


def comicinfo_xml(series, number, title):
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n<ComicInfo>\n'
        f"  <Series>{escape(series)}</Series>\n"
        f"  <Number>{escape(number)}</Number>\n"
        + (f"  <Title>{escape(title)}</Title>\n" if title else "")
        + f"  <Writer>{escape(AUTHOR)}</Writer>\n"
        f"  <Penciller>{escape(AUTHOR)}</Penciller>\n"
        "  <Manga>YesAndRightToLeft</Manga>\n"
        "  <LanguageISO>en</LanguageISO>\n"
        "</ComicInfo>\n"
    )


def count_spreads(zf):
    from PIL import Image  # installed with KCC

    spreads = 0
    for name in zf.namelist():
        if name.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".avif")):
            with Image.open(zf.open(name)) as im:
                spreads += im.width > im.height
    return spreads


def add_comicinfo(cbz_path):
    stem = re.sub(r"\.cbz$", "", cbz_path.rsplit("/", 1)[-1])
    series, number, title = parse_name(stem)
    with zipfile.ZipFile(cbz_path, "a") as zf:
        if "ComicInfo.xml" not in zf.namelist():
            zf.writestr("ComicInfo.xml", comicinfo_xml(series, number, title))
        spreads = count_spreads(zf)
    print(f"{stem}: series={series!r} number={number} title={title!r} spreads={spreads}")
    return spreads


def add_calibre_series(epub_path):
    """Rewrite the .opf inside the EPUB with calibre:series / calibre:series_index."""
    with zipfile.ZipFile(epub_path) as zf:
        entries = [(info, zf.read(info)) for info in zf.infolist()]
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as zf:
        for info, data in entries:  # keeps order, so "mimetype" stays first and uncompressed
            if info.filename.endswith(".opf"):
                data = _calibre_opf(data.decode("utf-8")).encode("utf-8")
            zf.writestr(info, data)
    with open(epub_path, "wb") as f:
        f.write(out.getvalue())


def _calibre_opf(opf):
    if "calibre:series" in opf:
        return opf
    series = re.search(r'property="belongs-to-collection"[^>]*>([^<]+)<', opf)
    index = re.search(r'property="group-position">([^<]+)<', opf)
    if not series:
        return opf
    tags = f'<meta name="calibre:series" content={quoteattr(series[1])}/>\n'
    if index:
        tags += f'<meta name="calibre:series_index" content={quoteattr(index[1])}/>\n'
    return opf.replace("</metadata>", tags + "</metadata>", 1)


def test():
    assert parse_name("One Piece 1196 - The Love of the Suicidal is Worthless") == (
        "One Piece", "1196", "The Love of the Suicidal is Worthless")
    assert parse_name("One Piece 1196") == ("One Piece", "1196", "")
    assert parse_name("One Piece 1100.5 - Extra - Part 2") == ("One Piece", "1100.5", "Extra - Part 2")
    assert "<Title>A &amp; B</Title>" in comicinfo_xml("One Piece", "1", "A & B")
    opf = ('<metadata><meta property="belongs-to-collection" id="c02">One Piece</meta>'
           '<meta refines="#c02" property="group-position">1196</meta></metadata>')
    new = _calibre_opf(opf)
    assert '<meta name="calibre:series" content="One Piece"/>' in new
    assert '<meta name="calibre:series_index" content="1196"/>' in new
    assert _calibre_opf(new) == new  # idempotent
    print("ok")


if __name__ == "__main__":
    cmd, *args = sys.argv[1:] or ["test"]
    if cmd == "test":
        test()
    elif cmd == "comicinfo":
        add_comicinfo(args[0])
    elif cmd == "calibre":
        add_calibre_series(args[0])
    else:
        sys.exit(__doc__)
