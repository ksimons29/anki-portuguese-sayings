# Card Images / Icons (Always‑On Visual Cue)

This feature adds a consistent visual anchor to every Anki note produced by **GPT Vocabulary Automater**. Images are stored in Anki’s `collection.media` (via AnkiConnect) and sync to iOS/Android. If no suitable picture is found, the pipeline falls back to an emoji “tile”, so you **always** see a visual.

---

## Why visuals?
- Stronger memory encoding through dual‑coding (text + image).
- Faster card scanning and nicer UI on mobile.
- Works completely offline after Anki sync (media is embedded).

---

## One‑time setup in Anki

1. **Create fields** on the note type *GPT Vocabulary Automater*  
   Tools → Manage Note Types → GPT Vocabulary Automater → **Fields…**
   - `Image`  *(enable “Use HTML editor by default”)*
   - `ImageCredit` *(optional; “Collapse by default”)*

2. **Update card templates**

### Card Type 1 — EN→PT

**Front Template**
```html
{{#Image}}<div class="image-wrap">{{Image}}</div>{{/Image}}
<div class="term">{{word_en}}</div>
```

**Back Template**
```html
{{FrontSide}}<hr id="answer">
<div class="answer">
  <div class="term-pt">{{word_pt}}</div>
  <div class="sent pt">{{sentence_pt}}</div>
  <div class="tts">{{tts pt_PT voices=Joana:sentence_pt}}</div>
  <div class="sent en">/ {{sentence_en}}</div>
</div>
{{#ImageCredit}}<div class="credit">{{ImageCredit}}</div>{{/ImageCredit}}
```

### Card Type 2 — PT→EN

**Front Template**
```html
{{#Image}}<div class="image-wrap">{{Image}}</div>{{/Image}}
<div class="term">{{word_pt}}</div>
```

**Back Template**
```html
{{FrontSide}}<hr id="answer">
<div class="answer">
  <div class="term-en">{{word_en}}</div>
  <div class="sent pt">{{sentence_pt}}</div>
  <div class="tts">{{tts pt_PT voices=Joana:sentence_pt}}</div>
  <div class="sent en">/ {{sentence_en}}</div>
</div>
{{#ImageCredit}}<div class="credit">{{ImageCredit}}</div>{{/ImageCredit}}
```

> `{{FrontSide}}` already brings the image to the back, so do **not** place a second image block there.

3. **Styling** (paste in the *Styling* tab of this note type)
```css
/* ---------- Modern, legible defaults ---------- */
:root {
  --fg: #0f172a;
  --bg: #ffffff;
  --muted: #6b7280;
  --radius: 14px;
  --shadow: 0 10px 28px rgba(0,0,0,.08);
}
@media (prefers-color-scheme: dark) {
  :root { --fg:#e5e7eb; --bg:#0b0f16; --muted:#9ca3af; --shadow:0 12px 32px rgba(0,0,0,.35); }
}
.card {
  color: var(--fg);
  background: var(--bg);
  font-family: ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,"Apple Color Emoji","Segoe UI Emoji";
  font-size: 22px; line-height: 1.55; padding: 18px 18px 22px; text-align: center;
  -webkit-font-smoothing: antialiased; text-rendering: optimizeLegibility;
}
.term { font-size: 38px; font-weight: 750; letter-spacing: .2px; margin: 8px 0 0; }
.term-pt, .term-en { font-size: 30px; font-weight: 700; margin: 6px 0 2px; }
.sent { margin-top: 8px; }
.sent.pt { font-size: 20px; }
.sent.en { font-size: 18px; color: var(--muted); }
.tts { margin: 6px 0 2px; }
.image-wrap { margin: 0 auto 12px; }
.image-wrap img {
  width: auto; height: auto; max-width: min(92%, 560px); display: block; margin: 0 auto;
  border-radius: var(--radius); box-shadow: var(--shadow);
}
#answer { border: 0; height: 1px; margin: 14px 0 12px;
  background: linear-gradient(90deg, transparent, rgba(0,0,0,.18), transparent); }
.credit { font-size: 12px; color: var(--muted); text-align: center; margin-top: 12px; line-height: 1.35; }
@media (max-width: 480px) {
  .card { font-size: 20px; }
  .term { font-size: 34px; }
  .term-pt, .term-en { font-size: 26px; }
  .sent.pt { font-size: 19px; }
  .sent.en { font-size: 17px; }
  .image-wrap img { max-width: 96%; }
}
.sent, .term, .term-pt, .term-en { text-wrap: pretty; -webkit-hyphens:auto; -ms-hyphens:auto; hyphens:auto; }
```

---

## Pipeline Integration (AnkiConnect)

Add these helpers to your Python transform and call `ensure_image_for_term(...)` when building each note.

```python
import base64, json, re, urllib.request, urllib.parse, urllib.error

ANKI_CONNECT = "http://127.0.0.1:8765"

def anki_invoke(action: str, **params):
    payload = json.dumps({"action": action, "version": 6, "params": params}).encode("utf-8")
    req = urllib.request.Request(ANKI_CONNECT, data=payload, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode("utf-8"))
    if data.get("error"):
        raise RuntimeError(f"AnkiConnect error: {data['error']}")
    return data.get("result")

def store_media_file(filename: str, raw_bytes: bytes) -> str:
    b64 = base64.b64encode(raw_bytes).decode("ascii")
    return anki_invoke("storeMediaFile", filename=filename, data=b64)

def _download_bytes(url: str, timeout: int = 12) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "anki-tools/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def _slug(s: str) -> str:
    s = re.sub(r"\s+", "_", s.strip().lower())
    s = re.sub(r"[^a-z0-9_]+", "", s)
    return s or "img"

def wikimedia_thumb(term: str, size: int = 512):
    # 1) Wikipedia REST summary → thumbnail
    try:
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(term)}"
        with urllib.request.urlopen(url, timeout=10) as r:
            summary = json.loads(r.read().decode("utf-8"))
        thumb = summary.get("thumbnail", {}).get("source")
        title = summary.get("title")
        page_url = summary.get("content_urls", {}).get("desktop", {}).get("page")
        if thumb:
            img = _download_bytes(thumb)
            credit = f'<a href="{page_url}">{title}</a> (Wikipedia)'
            return img, credit
    except Exception:
        pass
    # 2) MediaWiki search → pageimage
    try:
        qurl = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
            "action":"query","list":"search","format":"json","srlimit":1,"srsearch":term
        })
        with urllib.request.urlopen(qurl, timeout=10) as r:
            js = json.loads(r.read().decode("utf-8"))
        hits = js.get("query", {}).get("search", [])
        if not hits: return None, None
        page_title = hits[0]["title"]
        pi_url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
            "action":"query","prop":"pageimages|info","inprop":"url",
            "format":"json","pithumbsize":size,"titles":page_title
        })
        with urllib.request.urlopen(pi_url, timeout=10) as r:
            js2 = json.loads(r.read().decode("utf-8"))
        pages = js2.get("query", {}).get("pages", {})
        for _, p in pages.items():
            thumb = p.get("thumbnail", {}).get("source")
            fullurl = p.get("fullurl")
            if thumb:
                img = _download_bytes(thumb)
                credit = f'<a href="{fullurl}">{page_title}</a> (Wikipedia)'
                return img, credit
        return None, None
    except Exception:
        return None, None

def emoji_for(term: str) -> str:
    if re.search(r"\b(comer|beber|cozinhar)\b", term, re.I): return "🍽️"
    if re.search(r"\b(andar|correr|saltar|ir)\b", term, re.I): return "🏃"
    if re.search(r"\b(casa|quarto|cozinha|rua)\b", term, re.I): return "🏠"
    if re.search(r"\b(cão|gato|pássaro|peixe)\b", term, re.I): return "🐾"
    if re.search(r"\b(amor|feliz|triste|medo)\b", term, re.I): return "💛"
    return "🧠"

def ensure_image_for_term(term: str):
    """
    Returns (image_field_html, credit_html). If an image is found, we upload it
    to collection.media and return <img src="...">. Otherwise returns an emoji block.
    """
    img_bytes, credit = wikimedia_thumb(term)
    if img_bytes:
        fname = f"pt_{_slug(term)}.jpg"
        stored = store_media_file(fname, img_bytes)
        return f'<img src="{stored}">', (credit or "")
    em = emoji_for(term)
    return f'<div style="font-size:72px; text-align:center; line-height:1">{em}</div>', ""
```

**When constructing the note**
```python
image_html, credit_html = ensure_image_for_term(word_pt)  # or another lemma/gloss

note = {
  "deckName": "Portuguese (pt-PT)",
  "modelName": "GPT Vocabulary Automater",
  "fields": {
    "word_en": word_en,
    "word_pt": word_pt,
    "sentence_pt": sentence_pt,
    "sentence_en": sentence_en,
    "date_added": date_str,
    "Image": image_html,
    "ImageCredit": credit_html,
  },
  "options": {"allowDuplicate": False},
  "tags": ["pt","anki-tools"]
}
anki_invoke("addNotes", notes=[note])
```

---

## Test Checklist
1. Launch Anki (AnkiConnect enabled).  
2. Run the transform for a single term (e.g. `maçã`).  
3. Preview the card → image shows on the front.  
4. Sync to mobile and test offline.  
5. If no picture exists, you should see a large emoji tile.

## Licensing
Most Wikimedia images are CC‑BY/CC‑BY‑SA or public domain. We include a small credit on the back of the card when available.

## Troubleshooting
- **Image only on front?** Ensure the back template starts with `{{FrontSide}}`.  
- **No image at all?** Check AnkiConnect is running and your script called `storeMediaFile`.  
- **Duplicates in media folder?** Use deterministic filenames like `pt_<slug>.jpg`.
