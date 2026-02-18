# 📚 bib2tab

`bib2tab.py` is a Python script that reads a `.bib` (BibTeX) file
and generates an interactive HTML page containing a sortable and
filterable table with key bibliographic metadata.

The generated page can optionally be opened automatically in your web
browser.

------------------------------------------------------------------------

## ✨ Features

-   Full parsing of `.bib` files
-   Automatic extraction of:
    -   DOI (even if embedded in URL or notes)
    -   PDF link (local or remote)
    -   Authors (properly formatted)
    -   Journal / Proceedings
    -   Volume
    -   Year
    -   Pages
    -   Abstract
-   HTML output with:
    -   Click-to-sort columns
    -   Real-time text filtering
    -   Dynamic visible row counter
    -   Clean, dependency-free JavaScript interface

------------------------------------------------------------------------

## 📦 Requirements

Python ≥ 3.9

Required library:

``` bash
pip install bibtexparser
```

------------------------------------------------------------------------

## 🚀 Usage

### Basic command

``` bash
python bib2tab.py /path/to/your/file.bib
```

This generates an HTML file with the same name as the `.bib` file and
opens it in your browser.

------------------------------------------------------------------------

### Specify output file

``` bash
python bib2tab.py refs.bib -o output.html
```

------------------------------------------------------------------------

### Do not open browser automatically

``` bash
python bib2tab.py refs.bib --no-open
```

------------------------------------------------------------------------

## 📄 HTML Output

The generated page includes:

-   Search field filtering across:
    -   Authors
    -   Journal
    -   Year
    -   DOI
    -   Abstract
-   Clickable sorting on each column
-   Visual indicators ▲ / ▼
-   Clickable DOI links
-   Clickable PDF links (local files converted to URI)

------------------------------------------------------------------------

## 🧠 Extraction Logic

### DOI

Extracted from: - `doi` - Or detected inside: - `url` - `note` -
`howpublished` - `annote`

Automatic normalization removes `https://doi.org/` if present.

------------------------------------------------------------------------

### PDF

Searched in priority order:

-   `pdf`
-   `fulltext`
-   `link`
-   `url` (if containing `.pdf`)
-   `file` (Zotero-style entries supported)

Supports: - HTTP/HTTPS URLs - Relative or absolute local file paths

------------------------------------------------------------------------

### Authors

-   Parses `author` field
-   Supports:
    -   `Last, First`
    -   `First Last`
-   Output separated by semicolons (`;`)

------------------------------------------------------------------------

## 🗂 Code Structure

-   `load_bib_entries()` → BibTeX parsing
-   `extract_*()` → field extraction helpers
-   `build_rows()` → table row preparation
-   `render_html()` → HTML generation
-   `main()` → CLI handling and orchestration

------------------------------------------------------------------------

## 🛠 Common Issue

### NameError in render_html

If you encounter:

    NameError: name 'colIndex' is not defined

This happens because `{ colIndex }` inside a Python f-string is
interpreted as a Python variable.

Fix by escaping braces:

``` javascript
{{ colIndex }}
```

In f-strings, literal braces must be doubled.

------------------------------------------------------------------------

## 📈 Output Columns

  DOI   PDF   Authors   Journal   Volume   Year   Pages   Abstract
  ----- ----- --------- --------- -------- ------ ------- ----------

All columns are sortable by clicking their headers.

------------------------------------------------------------------------

## 🔐 Security

-   Automatic HTML escaping to prevent injection
-   Links use `rel="noopener noreferrer"`

------------------------------------------------------------------------

## 📌 Notes

-   Compatible with standard BibTeX
-   Works offline (except for external DOI/PDF links)
-   Filtering and sorting handled entirely client-side

------------------------------------------------------------------------

## 📜 License

Free for personal and academic use.
