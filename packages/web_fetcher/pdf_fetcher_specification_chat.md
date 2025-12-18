## 1. Goal

Build a **PDF fetcher** that, given a paper identifier, **downloads the corresponding PDF** (when accessible) to a local directory for later object detection.

The fetcher must handle **different publishers**, **redirects**, **Cloudflare and cookies**, and cases where the PDF is only reachable via **buttons/links or inline viewers**.

---

## 2. Inputs

- **Identifiers the system must accept**:
  - **DOI** (e.g. `10.2138/am.2011.573`)
  - **DOI-URL** (e.g. `https://doi.org/10.2138/am.2011.573`)
  - **Resource URL** (publisher landing page, e.g. `https://pubs.geoscienceworld.org/ammin/article/96/5-6/946/45401`)

- **DOI normalization rules**:
  - If the input **starts with `10.`**, treat it as a DOI.
  - Clean it by:
    - Stripping whitespace.
    - Removing trailing punctuation `.,);]` and leading punctuation if present.
  - Construct `https://doi.org/{doi}` from the **original cleaned DOI** for network navigation.
  - Use a **sanitized DOI only for filenames**, never for network requests.

---

## 3. Environment / Access Assumptions

- Runs on a machine connected to a **university network** (directly or via VPN).
- Some content may be accessible because of **institutional subscriptions**.
- If the PDF is **behind a paywall we cannot transparently access**, the system **skips the DOI**, logs the failure, and does not retry indefinitely.

---

## 4. Behavior and Requirements

### 4.1 DOI and URL resolution

- If **DOI**:
  - Construct `https://doi.org/{cleaned_doi}`.
  - Follow redirects (via `requests` first; fall back to Selenium if needed) to a **landing URL**.
- If **DOI-URL**:
  - Use as-is; follow redirects to landing URL.
- If **resource URL**:
  - Treat directly as landing URL (no DOI resolution).
- Always record:
  - Input identifier.
  - Final landing URL.
  - Detected publisher (if any).

### 4.2 Publisher handling

- **Publisher detection** by domain (examples):
  - `sciencedirect.com` → Elsevier
  - `springer.com` / `springerlink.com` → Springer
  - `nature.com` → Nature
  - `wiley.com` → Wiley
  - `arxiv.org` → arXiv
  - etc.
- For each known publisher, the fetcher may have a **publisher-specific strategy**:
  - **ScienceDirect (Elsevier)**:
    - If URL matches `/science/article/pii/{PII}`, extract PII.
    - Construct direct PDF URL:
      - `https://www.sciencedirect.com/science/article/pii/{PII}/pdfft?isDTMRedir=true&download=true`
    - Attempt direct download with cookies from the browser.
    - If that fails (e.g. 403, HTML, not PDF), fall back to **generic PDF detection** on the article page.
- If no known publisher is detected, use the **generic strategy** below.

### 4.3 PDF discovery strategies (generic + publisher-specific)

On the landing page (via Selenium):

1. **Direct link strategy**:
   - Look for anchors with obvious PDF indicators:
     - `a[href*=".pdf"]`
     - `a[data-pdf-url]`, `a[pdfurl]`, `a[href*="/pdf/"]`, etc.
   - Normalize relative URLs to absolute.

2. **Button/link strategy**:
   - Find all elements that might behave as buttons:
     - `//button | //a | //*[@role='button']`
   - Extract text from:
     - Visible text, child elements (`span`, `div`, etc.), `aria-label`, `title`.
   - Match against patterns (case-insensitive):
     - `download pdf`, `view pdf`, `pdf`, `download`, `get pdf`.
   - For matching elements:
     - Scroll into view.
     - Try to extract a PDF URL from `data-` attributes or `onclick` JS.
     - If needed, click:
       - Use `WebDriverWait` + normal click.
       - Fallback to JS click if normal click fails.
       - Detect:
         - New window/tab with a PDF URL.
         - Same-window URL change to a PDF.
         - Inline PDF view (current page is a PDF).

3. **Inline PDF strategy**:
   - Check if the current `driver.current_url` or response at that URL is a PDF (via HEAD/GET + content-type, header `%PDF`).
   - If so, treat it as the PDF URL.

4. **Page-source scanning (last resort)**:
   - Regexes to find:
     - `https?://...\.pdf[^\s"']*`
     - Publisher-specific patterns (e.g. ScienceDirect PII in page source).

5. **Validation of candidate URLs**:
   - Reject obvious non-PDF URLs (e.g. homepages like `https://www.elsevier.com/`).
   - Accept if:
     - URL ends with `.pdf` or contains `/pdf`, `/pdfft`, or known publisher-specific PDF patterns.

### 4.4 Download behavior

- Use a shared **`requests.Session`**:
  - Transfer cookies from Selenium to the session before downloading.
  - Use the same User-Agent as the browser.
  - Allow redirects (`allow_redirects=True`).
- For each candidate `pdf_url`:
  - Perform a `GET` with streaming:
    - If status is 2xx:
      - Proceed to content-type/header checks.
    - If status is 4xx/5xx (especially 403/401):
      - Save response body to a temporary file and peek at the first bytes:
        - If header is `%PDF`, treat as valid PDF and save.
        - Otherwise, treat as failure (unless a retry policy says otherwise).
  - Always:
    - Write to a temp file.
    - Verify header `%PDF`.
    - Only then move to final location.
    - On any failure, delete the temp file and log the reason.

### 4.5 Paywalls and access control

- If:
  - The page clearly indicates a paywall (e.g. “purchase PDF”, “subscription required”), **or**
  - All strategies fail and HTTP responses suggest lack of access (403/401 without PDF body),
- Then:
  - Mark the DOI as `status="paywall"` (or `access_denied`).
  - Do **not** retry indefinitely.
  - Log enough details to distinguish paywall vs “PDF not found”.

---

## 5. Storage, Filenames, and Metadata

### 5.1 Filenames and directory structure

- **Flat structure**:
  - All PDFs stored in a single directory, e.g. `pdf_dir/`.
- **Sanitized filenames**:
  - For DOIs, use a sanitized filename, e.g.:
    - `10.2138/am.2011.573 -> 10.2138_am.2011.573.pdf`
  - For non-DOI inputs (only a resource URL known), derive a stable identifier (e.g. hash of URL) if no DOI is available.
- **Repeat download avoidance**:
  - Before any download, check if the sanitized filename already exists and passes a quick `%PDF` header check.
  - If yes, **skip downloading** and mark as `status="already_exists"` (or reuse).

### 5.2 Metadata

- Maintain a **JSON metadata store** (format flexible, but should include at least):
  - Original identifier (DOI, DOI-URL, or resource URL).
  - Sanitized filename.
  - Final landing URL.
  - Detected publisher.
  - Download status (`success`, `failure`, `paywall`, `already_exists`, etc.).
  - Error reason/message when not successful.
  - Timestamps (first attempted, last attempted, last successful).

You can use:
- One global `metadata.json` with a dict keyed by identifier or DOI, **or**
- One sidecar JSON file per PDF (e.g. `10.2138_am.2011.573.json`).

---

## 6. Shared Folder Monitoring

- Default assumption: browser downloads PDFs into a single folder, e.g. `~/Downloads/`.
- Requirements:
  - Monitor this folder for **new completed PDF files**:
    - Ignore partial download suffixes (`.crdownload`, `.part`, etc.).
    - A file is “complete” when:
      - Its extension is `.pdf` and
      - Its size is stable for a short interval (e.g. 2–3 seconds).
  - When a new PDF appears:
    - Optionally move it into `pdf_dir/` with the sanitized filename.
    - Update metadata accordingly.

This monitoring can be:
- Event-based (e.g. using `watchdog`), **preferred**, or
- Polling-based (simple, but less efficient).

---

## 7. Politeness, Rate Limiting, and Concurrency

- **Rate-limiting**:
  - Per-domain rate limit, e.g.:
    - ~1 request/second per domain, with random jitter (e.g. 0.5–1.5s).
  - Configurable caps.

- **Delays**:
  - Insert short random sleeps between page loads/HTTP requests to mimic human behavior and avoid triggering bot detection.

- **User-Agent**:
  - Use a realistic, recent browser UA string (matching the Selenium browser).

- **Concurrency**:
  - Allow **parallel downloads** for non-Selenium HTTP-only operations (configurable max workers).
  - **Selenium**:
    - Default assumption: single browser session at a time per process.
    - No need for fully parallel Selenium; it can be sequential.

- **robots.txt**:
  - Optionally respect `robots.txt` for crawling behavior (can be a config option).

---

## 8. Error Handling and Logging

- **Error categories**:
  - `network_error` (timeouts, connection errors, 5xx)
  - `pdf_not_found` (no PDF link discovered despite search)
  - `paywall` / `access_denied`
  - `invalid_identifier` (malformed DOI/URL)
  - `unexpected_html` instead of PDF

- **Retries**:
  - For `network_error` and some 5xx:
    - Use exponential backoff with a limited number of retries (e.g. 3).
  - For `paywall`, `pdf_not_found`, and `invalid_identifier`:
    - Do not retry (or only after a long period, depending on config).

- **Logging**:
  - Log at least:
    - Levelled messages (DEBUG/INFO/WARNING/ERROR).
    - For failures: status code, URL, and “which strategy failed where”.

---

## 9. Integration with Object Detection

- PDFs are produced into `pdf_dir/` with predictable filenames and metadata.
- Integration options (you can choose one later in implementation):
  - The object detection system:
    - Polls `pdf_dir/` and/or reads `metadata.json` for `status="success"`, or
    - Uses a simple callback/hook (e.g. the downloader calls a user-supplied function with the final path).
- The fetcher itself does **not** need to run object detection; it only prepares the PDFs and metadata.


