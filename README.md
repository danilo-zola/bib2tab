# bib2tab

A lightweight Python tool that converts a `.bib` (BibTeX) file into a
clean, compact, sortable HTML table for browsing in your web browser.

Generated on: 2026-02-18

------------------------------------------------------------------------

## ✨ Features

-   ✅ One article per single row (no multi-line rows)
-   ✅ Compact layout with ellipsis truncation
-   ✅ Custom hover tooltip showing full content
-   ✅ Authors column shows:
    -   First author only
    -   "et al." if additional co-authors exist
    -   Full author list appears on mouse hover
-   ✅ DOI clickable link
-   ✅ PDF link detection (local or URL)
-   ✅ Sortable columns
-   ✅ Live filtering search bar
-   ✅ No external JS/CSS dependencies
-   ✅ Fully self-contained HTML output

------------------------------------------------------------------------

## 📦 Requirements

-   Python 3.8+
-   `bibtexparser`

Install dependency:

``` bash
pip install bibtexparser
```

------------------------------------------------------------------------

## 🚀 Usage

Basic usage:

``` bash
python bib2tab.py references.bib
```

This generates:

    references.html

and opens it automatically in your browser.

Optional arguments:

``` bash
python bib2tab.py references.bib -o output.html --no-open
```

-   `-o` → specify output file
-   `--no-open` → do not auto-open browser

------------------------------------------------------------------------

## 📊 Output Columns

  Column                  Description
  ----------------------- -------------------------------------------------
  DOI                     Clickable DOI link
  PDF                     Direct PDF link if available
  Authors                 First author + "et al." (hover shows full list)
  Title                   Article title
  Journal / Proceedings   Publication venue
  Volume                  Volume number
  Year                    Publication year
  Pages                   Page range

------------------------------------------------------------------------

## 🖱 Hover Behavior

-   Hover over truncated cells to see full content.
-   Hover over the **Authors** column to see the complete author list.

------------------------------------------------------------------------

## 🧠 Design Philosophy

The tool is optimized for:

-   Fast visual scanning
-   Compact bibliography browsing
-   Large `.bib` files
-   Zero visual clutter
-   No vertical row expansion

All entries remain strictly on a single line.

------------------------------------------------------------------------

## 📁 Project Structure

    bib2tab.py
    README.md

The generated HTML file is fully standalone and can be hosted anywhere.

------------------------------------------------------------------------

## 📝 License

MIT License (recommended --- adjust if needed)

------------------------------------------------------------------------

## 👤 Author

Created for academic bibliography browsing and research workflows.

