#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bib2browser.py
Legge un file .bib e genera una pagina HTML con una tabella (aperta nel browser)
contenente: DOI, link PDF (se presente), autori (completi), rivista, volume,
anno, pagine, abstract (se presente).

Dipendenze (consigliata):
  pip install bibtexparser

Uso:
  python bib2browser.py /percorso/al/tuo/file.bib
  python bib2browser.py refs.bib -o out.html --no-open
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# -----------------------------
# Parsing .bib (bibtexparser)
# -----------------------------
def load_bib_entries(bib_path: Path) -> List[Dict[str, Any]]:
    try:
        import bibtexparser  # type: ignore
        from bibtexparser.bparser import BibTexParser  # type: ignore
    except ImportError as e:
        raise SystemExit(
            "Errore: manca la libreria 'bibtexparser'. Installa con:\n"
            "  pip install bibtexparser\n"
        ) from e

    text = bib_path.read_text(encoding="utf-8", errors="replace")

    parser = BibTexParser(common_strings=True)
    parser.ignore_nonstandard_types = False
    db = bibtexparser.loads(text, parser=parser)

    return db.entries or []


# -----------------------------
# Estrazione campi utili
# -----------------------------
DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)

def norm_key(k: str) -> str:
    return k.strip().lower()

def get_field(entry: Dict[str, Any], *names: str) -> Optional[str]:
    lower_map = {norm_key(k): v for k, v in entry.items()}
    for n in names:
        v = lower_map.get(norm_key(n))
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return None

def extract_doi(entry: Dict[str, Any]) -> Optional[str]:
    doi = get_field(entry, "doi")
    if doi:
        doi = doi.strip()
        doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE).strip()
        m = DOI_RE.search(doi)
        return m.group(0) if m else doi

    for field in ("url", "note", "howpublished", "annote"):
        v = get_field(entry, field)
        if not v:
            continue
        m = DOI_RE.search(v)
        if m:
            return m.group(0)
    return None

def split_authors(author_field: str) -> List[str]:
    parts = [a.strip() for a in author_field.split(" and ") if a.strip()]
    pretty = []
    for a in parts:
        if "," in a:
            chunks = [c.strip() for c in a.split(",", 1)]
            if len(chunks) == 2 and chunks[1]:
                pretty.append(f"{chunks[1]} {chunks[0]}")
            else:
                pretty.append(a)
        else:
            pretty.append(a)
    return pretty

def extract_authors(entry: Dict[str, Any]) -> str:
    author = get_field(entry, "author", "authors")
    if not author:
        editor = get_field(entry, "editor")
        if editor:
            return "; ".join(split_authors(editor))
        return ""
    return "; ".join(split_authors(author))

def extract_journal(entry: Dict[str, Any]) -> str:
    return (
        get_field(entry, "journal")
        or get_field(entry, "booktitle")
        or get_field(entry, "school")
        or get_field(entry, "institution")
        or ""
    )

def extract_volume(entry: Dict[str, Any]) -> str:
    return get_field(entry, "volume") or ""

def extract_year(entry: Dict[str, Any]) -> str:
    y = get_field(entry, "year")
    if y:
        return y
    d = get_field(entry, "date")
    if d:
        m = re.search(r"\b(\d{4})\b", d)
        return m.group(1) if m else d
    return ""

def extract_pages(entry: Dict[str, Any]) -> str:
    p = get_field(entry, "pages")
    if not p:
        return ""
    return p.replace("--", "–")

def is_probable_url(s: str) -> bool:
    return s.lower().startswith(("http://", "https://"))

def extract_pdf_link(entry: Dict[str, Any], bib_dir: Path) -> Optional[Tuple[str, str]]:
    for f in ("pdf", "fulltext", "link"):
        v = get_field(entry, f)
        if v and (".pdf" in v.lower() or is_probable_url(v) or Path(v).suffix.lower() == ".pdf"):
            return normalize_pdf_target(v, bib_dir)

    url = get_field(entry, "url")
    if url and ".pdf" in url.lower():
        return normalize_pdf_target(url, bib_dir)

    file_field = get_field(entry, "file")
    if file_field:
        pdf_candidates = []
        for token in re.split(r"[;,\n]+", file_field):
            token = token.strip().strip("{}")
            if not token:
                continue
            if token.count(":") >= 2:
                maybe_path = token.split(":", 2)[1].strip()
            else:
                maybe_path = token
            if ".pdf" in maybe_path.lower():
                pdf_candidates.append(maybe_path)

        if pdf_candidates:
            return normalize_pdf_target(pdf_candidates[0], bib_dir)

    return None

def normalize_pdf_target(raw: str, bib_dir: Path) -> Tuple[str, str]:
    s = raw.strip().strip("{}")
    if is_probable_url(s):
        return s, "PDF"
    p = Path(s)
    if not p.is_absolute():
        p = (bib_dir / p).resolve()
    return p.as_uri(), "PDF"

def extract_abstract(entry: Dict[str, Any]) -> str:
    return get_field(entry, "abstract") or ""


# -----------------------------
# HTML (tabella in browser)
# -----------------------------
def esc(s: str) -> str:
    return html.escape(s or "", quote=True)

def make_link(href: str, label: str) -> str:
    return f'<a href="{esc(href)}" target="_blank" rel="noopener noreferrer">{esc(label)}</a>'

def build_rows(entries: List[Dict[str, Any]], bib_dir: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for e in entries:
        doi = extract_doi(e) or ""
        doi_link = make_link(f"https://doi.org/{doi}", doi) if doi else ""

        pdf = extract_pdf_link(e, bib_dir)
        pdf_link = make_link(pdf[0], pdf[1]) if pdf else ""

        authors = extract_authors(e)
        journal = extract_journal(e)
        volume = extract_volume(e)
        year = extract_year(e)
        pages = extract_pages(e)
        abstract = extract_abstract(e)

        rows.append(
            {
                "doi": doi_link,
                "pdf": pdf_link,
                "authors": esc(authors),
                "journal": esc(journal),
                "volume": esc(volume),
                "year": esc(year),
                "pages": esc(pages),
                "abstract": esc(abstract),
            }
        )
    return rows

def render_row(r: Dict[str, str]) -> str:
    def cell(v: str) -> str:
        return f"<td>{v if v else '<span class=\"muted\">—</span>'}</td>"
    return "<tr>" + "".join(
        [
            cell(r["doi"]),
            cell(r["pdf"]),
            cell(r["authors"]),
            cell(r["journal"]),
            cell(r["volume"]),
            cell(r["year"]),
            cell(r["pages"]),
            cell(r["abstract"]),
        ]
    ) + "</tr>"

def render_html(rows: List[Dict[str, str]], title: str) -> str:
    return f"""<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{esc(title)}</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, Arial, sans-serif; margin: 18px; }}
    h1 {{ font-size: 18px; margin: 0 0 12px 0; }}
    .toolbar {{ display: flex; gap: 12px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }}
    input[type="search"] {{ padding: 8px 10px; min-width: 320px; max-width: 100%; }}
    .meta {{ color: #555; font-size: 12px; }}

    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; vertical-align: top; }}
    th {{ position: sticky; top: 0; background: #f7f7f7; text-align: left; user-select: none; }}
    tr:nth-child(even) {{ background: #fbfbfb; }}
    .small {{ white-space: nowrap; }}
    .abstract {{ max-width: 60ch; }}
    .muted {{ color: #777; }}

    /* sort UI */
    th.sortable {{ cursor: pointer; }}
    th .sort-ind {{ font-size: 11px; color: #666; margin-left: 6px; }}
  </style>
</head>
<body>
  <h1>{esc(title)}</h1>
  <div class="toolbar">
    <input id="q" type="search" placeholder="Filtra (autori, rivista, anno, DOI, ecc.)…" />
    <span class="meta">Righe: <span id="count">{len(rows)}</span></span>
    <span class="meta muted">Suggerimento: clicca sulle intestazioni per ordinare</span>
  </div>

  <table id="t">
    <thead>
      <tr>
        <th class="small sortable" data-key="doi" data-type="text">DOI<span class="sort-ind"></span></th>
        <th class="small sortable" data-key="pdf" data-type="text">PDF<span class="sort-ind"></span></th>
        <th class="sortable" data-key="authors" data-type="text">Autori<span class="sort-ind"></span></th>
        <th class="sortable" data-key="journal" data-type="text">Rivista / Proceedings<span class="sort-ind"></span></th>
        <th class="small sortable" data-key="volume" data-type="text">Volume<span class="sort-ind"></span></th>
        <th class="small sortable" data-key="year" data-type="num">Anno<span class="sort-ind"></span></th>
        <th class="small sortable" data-key="pages" data-type="text">Pagine<span class="sort-ind"></span></th>
        <th class="abstract sortable" data-key="abstract" data-type="text">Abstract<span class="sort-ind"></span></th>
      </tr>
    </thead>
    <tbody>
      {''.join(render_row(r) for r in rows)}
    </tbody>
  </table>

<script>
(function() {{
  const q = document.getElementById('q');
  const t = document.getElementById('t');
  const tbody = t.tBodies[0];
  const count = document.getElementById('count');
  const headers = Array.from(t.tHead.rows[0].cells);

  // Stato ordinamento: {{ colIndex, dir: 1 asc | -1 desc }}
  const sortState = {{ colIndex: null, dir: 1 }};

  function normalize(s) {{
    return (s || '').toLowerCase();
  }}

  function applyFilter() {{
    const needle = normalize(q.value);
    const rows = tbody.rows;
    let visible = 0;
    for (const r of rows) {{
      const text = normalize(r.innerText);
      const show = !needle || text.includes(needle);
      r.style.display = show ? '' : 'none';
      if (show) visible++;
    }}
    count.textContent = visible;
  }}

  function cellValue(row, colIndex) {{
    // textContent è più stabile di innerText per link e span "—"
    return (row.cells[colIndex]?.textContent || '').trim();
  }}

  function parseNum(s) {{
    // estrae il primo intero (utile per year, volumi "12", "12A", ecc.)
    const m = String(s).match(/-?\\d+/);
    return m ? parseInt(m[0], 10) : Number.NEGATIVE_INFINITY;
  }}

  function clearIndicators() {{
    for (const th of headers) {{
      const ind = th.querySelector('.sort-ind');
      if (ind) ind.textContent = '';
    }}
  }}

  function setIndicator(th, dir) {{
    const ind = th.querySelector('.sort-ind');
    if (!ind) return;
    ind.textContent = dir === 1 ? '▲' : '▼';
  }}

  function sortBy(colIndex, type, dir) {{
    const rows = Array.from(tbody.rows);

    rows.sort((a, b) => {{
      const av = cellValue(a, colIndex);
      const bv = cellValue(b, colIndex);

      if (type === 'num') {{
        const an = parseNum(av);
        const bn = parseNum(bv);
        if (an === bn) return 0;
        return (an < bn ? -1 : 1) * dir;
      }}

      // testo: localeCompare con numeric aiuta per stringhe tipo "Vol 9" vs "Vol 10"
      const cmp = av.localeCompare(bv, undefined, {{ numeric: true, sensitivity: 'base' }});
      return cmp * dir;
    }});

    // riattacca in ordine
    for (const r of rows) tbody.appendChild(r);

    // riapplica filtro per mantenere conteggio coerente
    applyFilter();
  }}

  headers.forEach((th, idx) => {{
    if (!th.classList.contains('sortable')) return;

    th.addEventListener('click', () => {{
      const type = th.dataset.type || 'text';

      if (sortState.colIndex === idx) {{
        sortState.dir *= -1; // toggle
      }} else {{
        sortState.colIndex = idx;
        sortState.dir = 1;
      }}

      clearIndicators();
      setIndicator(th, sortState.dir);
      sortBy(idx, type, sortState.dir);
    }});
  }});

  q.addEventListener('input', applyFilter);
  applyFilter();
}})();
</script>
</body>
</html>
"""

# -----------------------------
# CLI
# -----------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Genera una tabella HTML da un file .bib e la apre nel browser.")
    ap.add_argument("bib", type=str, help="Percorso al file .bib")
    ap.add_argument("-o", "--out", type=str, default=None, help="File HTML di output (default: stesso nome .html)")
    ap.add_argument("--no-open", action="store_true", help="Non aprire automaticamente il browser")
    args = ap.parse_args()

    bib_path = Path(args.bib).expanduser().resolve()
    if not bib_path.exists():
        print(f"Errore: file non trovato: {bib_path}", file=sys.stderr)
        return 2

    out_path = Path(args.out).expanduser().resolve() if args.out else bib_path.with_suffix(".html")
    entries = load_bib_entries(bib_path)
    rows = build_rows(entries, bib_path.parent)
    title = f"Bibliografia: {bib_path.name} ({len(rows)} record)"

    html_text = render_html(rows, title)
    out_path.write_text(html_text, encoding="utf-8")

    print(f"HTML scritto in: {out_path}")
    if not args.no_open:
        webbrowser.open(out_path.as_uri())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

