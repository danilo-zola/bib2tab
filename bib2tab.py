#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bib2tab_modified.py
Genera una pagina HTML con tabella compatta (1 riga per record) a partire da un file .bib.

Colonne:
  DOI | PDF | Autori (compatti) | Titolo | Rivista/Proceedings | Volume | Anno | Pagine

PDF link:
  - Di default, per ogni voce BibTeX cerca un PDF nella stessa directory del file .bib
    con nome: <LABEL>.pdf (LABEL = citekey BibTeX)
  - In modalità "standalone" (default) il link al PDF è un URI locale file://...
  - In modalità "web app" (es. NiceGUI) puoi passare pdf_base_url a build_rows(...)
    per generare link HTTP (es. /localpdfs/collection/<LABEL>.pdf), evitando file://.

Requisiti:
  pip install bibtexparser

Uso:
  python bib2tab_modified.py references.bib
  python bib2tab_modified.py references.bib -o out.html --no-open
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


def get_citekey(entry: Dict[str, Any]) -> str:
    """
    Restituisce la label/citekey BibTeX della voce.
    Con bibtexparser la chiave è tipicamente in entry["ID"].
    """
    for k in ("ID", "id", "key", "citekey"):
        v = entry.get(k)
        if v:
            return str(v).strip()
    v = get_field(entry, "citation_key")
    return (v or "").strip()


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
    """
    Split basato su ' and ' (standard BibTeX).
    Restituisce SEMPRE autori nel formato "Cognome Nome".
    - "Cognome, Nome" -> "Cognome Nome"
    - "Nome Cognome"  -> "Cognome Nome" (assumendo ultimo token = cognome)
    """
    parts = [a.strip() for a in author_field.split(" and ") if a.strip()]
    pretty: List[str] = []
    for a in parts:
        if "," in a:
            surname, name = [c.strip() for c in a.split(",", 1)]
            pretty.append(f"{surname} {name}".strip())
        else:
            tokens = a.split()
            if len(tokens) >= 2:
                surname = tokens[-1]
                name = " ".join(tokens[:-1])
                pretty.append(f"{surname} {name}".strip())
            else:
                pretty.append(a)
    return pretty


def extract_authors_list(entry: Dict[str, Any]) -> List[str]:
    """
    Ritorna lista autori completa. Se manca 'author', prova con 'editor'.
    """
    author = get_field(entry, "author", "authors")
    if author:
        return split_authors(author)

    editor = get_field(entry, "editor")
    if editor:
        return split_authors(editor)

    return []


def authors_compact_and_full(entry: Dict[str, Any]) -> Tuple[str, str]:
    """
    Restituisce:
    - Compact (mostrato in cella): "Primo Autore" oppure "Primo Autore et al."
    - Full (tooltip): elenco completo separato da virgole
    """
    authors = extract_authors_list(entry)
    if not authors:
        return "", ""

    full = ", ".join(authors)
    if len(authors) == 1:
        return authors[0], full

    return f"{authors[0]} et al.", full


def extract_title(entry: Dict[str, Any]) -> str:
    return (
        get_field(entry, "title")
        or get_field(entry, "booktitle")
        or get_field(entry, "maintitle")
        or ""
    )


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


# -----------------------------
# HTML helpers
# -----------------------------
def esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def make_link(href: str, label: str) -> str:
    return f'<a href="{esc(href)}" target="_blank" rel="noopener noreferrer">{esc(label)}</a>'


def make_pdf_icon_link(href: str, tooltip: str) -> str:
    """
    Link PDF mostrato come icona (niente URL esplicito in tabella).
    """
    return (
        f'<a class="pdf-ico" href="{esc(href)}" target="_blank" '
        f'rel="noopener noreferrer" title="{esc(tooltip)}" aria-label="{esc(tooltip)}">📄</a>'
    )


def td(content_html: str, full_text: str, cls: str = "") -> str:
    """
    content_html: ciò che appare nella cella
    full_text: ciò che compare nel tooltip (data-full + title)
    """
    c = f' class="{cls}"' if cls else ""
    if not content_html:
        content_html = '<span class="muted">—</span>'

    safe_full = full_text or ""
    return f'<td{c} data-full="{esc(safe_full)}" title="{esc(safe_full)}">{content_html}</td>'


# -----------------------------
# Core: build_rows con pdf_base_url
# -----------------------------
def build_rows(
    entries: List[Dict[str, Any]],
    bib_dir: Path,
    pdf_base_url: Optional[str] = None,
) -> List[Dict[str, str]]:
    """
    Costruisce le righe per la tabella.

    pdf_base_url:
      - None (default): genera link PDF come file://... (pdf_path.resolve().as_uri())
      - stringa (es. "/localpdfs/collection" o "https://host/localpdfs/collection"):
          genera link PDF come: <pdf_base_url>/<citekey>.pdf

    Nota: anche con pdf_base_url, il PDF viene linkato solo se il file esiste su disco
    (bib_dir/<citekey>.pdf). Questo evita link "morti".
    """
    rows: List[Dict[str, str]] = []
    base = (pdf_base_url.rstrip("/") if pdf_base_url else None)

    for e in entries:
        doi_raw = extract_doi(e) or ""
        doi_html = make_link(f"https://doi.org/{doi_raw}", doi_raw) if doi_raw else ""

        # ---- PDF: <citekey>.pdf nella directory del .bib
        pdf_html = ""
        pdf_full = ""

        citekey = get_citekey(e)
        if citekey:
            pdf_path = (bib_dir / f"{citekey}.pdf")
            if pdf_path.exists():
                if base:
                    href = f"{base}/{citekey}.pdf"
                else:
                    href = pdf_path.resolve().as_uri()
                pdf_html = make_pdf_icon_link(href, f"Apri PDF: {citekey}.pdf")
                pdf_full = f"{citekey}.pdf"

        authors_compact, authors_full = authors_compact_and_full(e)

        # Chiave di ordinamento: cognome del primo autore (in minuscolo)
        authors_list = extract_authors_list(e)
        authors_sort = ""
        if authors_list:
            first_tokens = authors_list[0].split()
            authors_sort = (first_tokens[0] if first_tokens else "").lower()

        title = extract_title(e)
        journal = extract_journal(e)
        volume = extract_volume(e)
        year = extract_year(e)
        pages = extract_pages(e)
        search_full = " ".join(
            s
            for s in [
                authors_full,
                title,
                journal,
                volume,
                year,
                pages,
                doi_raw,
            ]
            if s
        )

        rows.append(
            {
                # shown HTML
                "doi": doi_html,
                "pdf": pdf_html,
                "authors": esc(authors_compact),
                "title": esc(title),
                "journal": esc(journal),
                "volume": esc(volume),
                "year": esc(year),
                "pages": esc(pages),
                # tooltip text (plain)
                "doi_full": doi_raw,
                "pdf_full": pdf_full,  # mostra solo nome file, non l'URI
                "authors_full": authors_full,
                "title_full": title,
                "journal_full": journal,
                "volume_full": volume,
                "year_full": year,
                "pages_full": pages,
                "authors_sort": authors_sort,
                "search_full": search_full,
            }
        )
    return rows


def render_row(r: Dict[str, str]) -> str:
    authors_html = r["authors"] if r["authors"] else '<span class="muted">—</span>'

    return (
        f'<tr data-search="{esc(r.get("search_full", ""))}" data-year="{esc(r.get("year_full", ""))}">'
        + td(r["doi"], r["doi_full"], "c-doi")
        + td(r["pdf"], r["pdf_full"], "c-pdf")
        + f'<td class="c-authors" data-full="{esc(r["authors_full"])}" data-sort="{esc(r.get("authors_sort", ""))}" title="{esc(r["authors_full"])}">{authors_html}</td>'
        + td(r["title"], r["title_full"], "c-title")
        + td(r["journal"], r["journal_full"], "c-journal")
        + td(r["volume"], r["volume_full"], "c-volume")
        + td(r["year"], r["year_full"], "c-year")
        + td(r["pages"], r["pages_full"], "c-pages")
        + "</tr>"
    )


def render_html(rows: List[Dict[str, str]], page_title: str) -> str:
    # NB: f-string ok perché nel JS NON uso template string `${...}`
    return f"""<!doctype html>
<html lang="it">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{esc(page_title)}</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, Noto Sans, Arial, sans-serif; margin: 18px; }}
    h1 {{ font-size: 18px; margin: 0 0 12px 0; }}
    .toolbar {{ display: flex; gap: 12px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }}
    input[type="search"] {{ padding: 8px 10px; min-width: 320px; max-width: 100%; }}
    .meta {{ color: #555; font-size: 12px; }}

    table {{
      border-collapse: collapse;
      width: 100%;
      table-layout: fixed; /* ellissi/compattezza */
    }}
    th, td {{
      border: 1px solid #ddd;
      padding: 6px 8px;
      vertical-align: middle;
      white-space: nowrap;        /* NO a capo */
      overflow: hidden;           /* taglia */
      text-overflow: ellipsis;    /* … */
    }}
    th {{
      position: sticky;
      top: 0;
      background: #f7f7f7;
      text-align: left;
      user-select: none;
      z-index: 2;
    }}
    tr:nth-child(even) {{ background: #fbfbfb; }}
    .muted {{ color: #777; }}

    th.sortable {{ cursor: pointer; }}
    th .sort-ind {{ font-size: 11px; color: #666; margin-left: 6px; }}

    .c-doi    {{ width: 12rem; }}
    .c-pdf    {{ width: 4.5rem; text-align: center; }}
    .c-authors{{ width: 12rem; }}
    .c-title  {{ width: 26rem; }}
    .c-journal{{ width: 18rem; }}
    .c-volume {{ width: 6rem; }}
    .c-year   {{ width: 6rem; }}
    .c-pages  {{ width: 8rem; }}

    a {{ display: inline-block; max-width: 100%; overflow: hidden; text-overflow: ellipsis; vertical-align: bottom; }}

    /* PDF icon link */
    a.pdf-ico {{
      text-decoration: none;
      font-size: 16px;
      line-height: 1;
      padding: 2px 4px;
      border-radius: 6px;
    }}
    a.pdf-ico:hover {{
      background: rgba(0,0,0,0.06);
    }}

    /* Tooltip hover custom */
    #tip {{
      position: fixed;
      display: none;
      max-width: min(820px, 92vw);
      padding: 8px 10px;
      border: 1px solid #ccc;
      background: #fff;
      box-shadow: 0 8px 24px rgba(0,0,0,0.12);
      border-radius: 8px;
      font-size: 12px;
      line-height: 1.35;
      color: #111;
      z-index: 9999;
      pointer-events: none;
      white-space: normal; /* nel tooltip posso andare a capo */
      overflow-wrap: anywhere;
    }}
    #tip .k {{
      font-weight: 600;
      color: #333;
      margin-bottom: 4px;
      display: block;
    }}
  </style>
</head>
<body>
  <h1>{esc(page_title)}</h1>

  <div class="toolbar">
    <input id="q" type="search" placeholder="Filtra (autori, titolo, rivista, anno, DOI, ecc.). Esempio intervallo: 2015 - 2020" />
    <span class="meta">Righe: <span id="count">{len(rows)}</span></span>
    <span class="meta muted">Suggerimento: clicca sulle intestazioni per ordinare</span>
  </div>

  <table id="t">
    <thead>
      <tr>
        <th class="c-doi sortable" data-type="text">DOI<span class="sort-ind"></span></th>
        <th class="c-pdf sortable" data-type="text">PDF<span class="sort-ind"></span></th>
        <th class="c-authors sortable" data-type="text">Autori<span class="sort-ind"></span></th>
        <th class="c-title sortable" data-type="text">Titolo<span class="sort-ind"></span></th>
        <th class="c-journal sortable" data-type="text">Rivista / Proceedings<span class="sort-ind"></span></th>
        <th class="c-volume sortable" data-type="text">Volume<span class="sort-ind"></span></th>
        <th class="c-year sortable" data-type="num">Anno<span class="sort-ind"></span></th>
        <th class="c-pages sortable" data-type="text">Pagine<span class="sort-ind"></span></th>
      </tr>
    </thead>
    <tbody>
      {''.join(render_row(r) for r in rows)}
    </tbody>
  </table>

  <div id="tip" role="tooltip" aria-hidden="true"></div>

<script>
(function() {{
  const q = document.getElementById('q');
  const t = document.getElementById('t');
  const tbody = t.tBodies[0];
  const count = document.getElementById('count');
  const headers = Array.from(t.tHead.rows[0].cells);

  const tip = document.getElementById('tip');
  let tipVisible = false;

  const sortState = {{ colIndex: null, dir: 1 }};

  function normalize(s) {{
    return (s || '').toLowerCase();
  }}

  function parseYearRange(raw) {{
    const s = String(raw || '').toLowerCase();
    let m = s.match(/\\b(\\d{{4}})\\s*-\\s*(\\d{{4}})\\b/);
    if (m) {{
      const a = parseInt(m[1], 10);
      const b = parseInt(m[2], 10);
      return {{ min: Math.min(a, b), max: Math.max(a, b), matched: m[0] }};
    }}
    m = s.match(/\\btra\\s+il\\s+(\\d{{4}})\\s+e\\s+(\\d{{4}})\\b/);
    if (m) {{
      const a = parseInt(m[1], 10);
      const b = parseInt(m[2], 10);
      return {{ min: Math.min(a, b), max: Math.max(a, b), matched: m[0] }};
    }}
    m = s.match(/(?:^|\\s)-\\s*(\\d{{4}})\\b/);
    if (m) {{
      const max = parseInt(m[1], 10);
      return {{ min: null, max, matched: m[0] }};
    }}
    m = s.match(/\\b(\\d{{4}})\\s*-\\s*(?:$|\\s)/);
    if (m) {{
      const min = parseInt(m[1], 10);
      return {{ min, max: null, matched: m[0] }};
    }}
    m = s.match(/\\bfino\\s+al\\s+(\\d{{4}})\\b/);
    if (m) {{
      const max = parseInt(m[1], 10);
      return {{ min: null, max, matched: m[0] }};
    }}
    m = s.match(/\\bdal\\s+(\\d{{4}})\\b/);
    if (m) {{
      const min = parseInt(m[1], 10);
      return {{ min, max: null, matched: m[0] }};
    }}
    return null;
  }}

  function yearInRange(yearStr, range) {{
    if (!range) return true;
    const y = parseInt(String(yearStr || '').match(/\\d{{4}}/)?.[0] || '', 10);
    if (!Number.isFinite(y)) return false;
    if (range.min !== null && y < range.min) return false;
    if (range.max !== null && y > range.max) return false;
    return true;
  }}

  function applyFilter() {{
    const raw = normalize(q.value);
    const range = parseYearRange(raw);
    const needle = range
      ? normalize(raw.replace(range.matched, ' ').replace(/\\s+/g, ' ').trim())
      : raw.trim();
    const rows = tbody.rows;
    let visible = 0;
    for (const r of rows) {{
      const custom = r.getAttribute('data-search');
      const text = normalize(custom || r.innerText);
      const year = r.getAttribute('data-year');
      const yearOk = yearInRange(year, range);
      const textOk = !needle || text.includes(needle);
      const show = yearOk && textOk;
      r.style.display = show ? '' : 'none';
      if (show) visible++;
    }}
    count.textContent = visible;
  }}

  function cellValue(row, colIndex) {{
    const cell = row.cells[colIndex];
    if (!cell) return '';
    const custom = cell.getAttribute('data-sort');
    if (custom) return custom;
    return (cell.textContent || '').trim();
  }}

  function parseNum(s) {{
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
    ind.textContent = (dir === 1) ? '▲' : '▼';
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

      const cmp = av.localeCompare(bv, undefined, {{ numeric: true, sensitivity: 'base' }});
      return cmp * dir;
    }});

    for (const r of rows) tbody.appendChild(r);
    applyFilter();
  }}

  headers.forEach((th, idx) => {{
    if (!th.classList.contains('sortable')) return;

    th.addEventListener('click', () => {{
      const type = th.dataset.type || 'text';
      if (sortState.colIndex === idx) {{
        sortState.dir *= -1;
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

  function escapeHtml(s) {{
    return String(s)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }}

  function headerLabelForCell(td) {{
    const idx = td.cellIndex;
    const th = headers[idx];
    return th ? (th.textContent || '').replace(/[▲▼]/g,'').trim() : '';
  }}

  function showTip(text, label, x, y) {{
    if (!text) return;
    const safeText = escapeHtml(text);
    const safeLabel = escapeHtml(label || '');
    tip.innerHTML = label ? ('<span class="k">' + safeLabel + '</span>' + safeText) : safeText;
    tip.style.display = 'block';
    tip.setAttribute('aria-hidden', 'false');
    tipVisible = true;
    moveTip(x, y);
  }}

  function hideTip() {{
    tip.style.display = 'none';
    tip.setAttribute('aria-hidden', 'true');
    tipVisible = false;
  }}

  function moveTip(x, y) {{
    if (!tipVisible) return;
    const pad = 14;
    const rect = tip.getBoundingClientRect();
    let tx = x + pad;
    let ty = y + pad;

    if (tx + rect.width > window.innerWidth - 8) tx = window.innerWidth - rect.width - 8;
    if (ty + rect.height > window.innerHeight - 8) ty = y - rect.height - pad;

    tip.style.left = Math.max(8, tx) + 'px';
    tip.style.top  = Math.max(8, ty) + 'px';
  }}

  t.addEventListener('mousemove', (ev) => {{
    if (!tipVisible) return;
    moveTip(ev.clientX, ev.clientY);
  }});

  t.addEventListener('mouseover', (ev) => {{
    const td = ev.target.closest('td');
    if (!td) return;

    const full = td.getAttribute('data-full') || '';
    const label = headerLabelForCell(td);

    const shown = (td.textContent || '').trim();
    const isAuthorsCol = (label.toLowerCase() === 'autori');

    const isTruncated = td.scrollWidth > td.clientWidth + 2;
    const isLong = full.length > 40;
    const isDifferent = full && (full.trim() !== shown);

    if (full && (isAuthorsCol ? isDifferent : (isTruncated || isLong))) {{
      showTip(full, label, ev.clientX, ev.clientY);
    }}
  }});

  t.addEventListener('mouseout', (ev) => {{
    const related = ev.relatedTarget;
    if (!related || !t.contains(related)) {{
      hideTip();
      return;
    }}
    const fromTd = ev.target.closest && ev.target.closest('td');
    const toTd = related.closest && related.closest('td');
    if (fromTd && toTd && fromTd === toTd) return;
    hideTip();
  }});

  window.addEventListener('scroll', () => {{
    hideTip();
  }}, {{ passive: true }});

  applyFilter();
}})();
</script>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Genera una tabella HTML compatta da un file .bib e la apre nel browser.")
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
    page_title = f"Bibliografia: {bib_path.name} ({len(rows)} record)"

    html_text = render_html(rows, page_title)
    out_path.write_text(html_text, encoding="utf-8")

    print(f"HTML scritto in: {out_path}")
    if not args.no_open:
        webbrowser.open(out_path.as_uri())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
