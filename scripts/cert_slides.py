"""Build an animated slideshow (SVG) of the certificates in assets/certificates.

Every PDF in the folder becomes one slide (first page, rendered as an image).
Captions come from assets/certificates/certificates.json (optional):
    [{"file": "google-data-analytics.pdf", "title": "...", "issuer": "...", "date": "..."}]
Runs in the "Update profile images" GitHub Action. Local use:
    pip install pymupdf
    python scripts/cert_slides.py --out dist
"""
import argparse
import base64
import io
import json
import os
from xml.sax.saxutils import escape

import pymupdf  # PyMuPDF
from PIL import Image

BLUE, LIGHT, PINK, TXT, DIM = "#5d73a2", "#8ea3d4", "#f4a7c4", "#e6e6e6", "#9aa4ae"
FONT = "Cascadia Mono, Cascadia Code, Consolas, 'Fira Code', 'DejaVu Sans Mono', monospace"
SECONDS_PER_SLIDE = 5


def render_pdf(path, width):
    doc = pymupdf.open(path)
    page = doc[0]
    zoom = width / page.rect.width
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=74, optimize=True)
    return img.size, base64.b64encode(buf.getvalue()).decode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="assets/certificates")
    ap.add_argument("--out", default="dist")
    a = ap.parse_args()

    meta = {}
    meta_path = os.path.join(a.src, "certificates.json")
    if os.path.exists(meta_path):
        with open(meta_path, encoding="utf-8") as f:
            meta = {m["file"]: m for m in json.load(f)}
    order = list(meta)  # json order first, then any other PDFs alphabetically
    pdfs = order + sorted(p for p in os.listdir(a.src) if p.lower().endswith(".pdf") and p not in meta)
    pdfs = [p for p in pdfs if os.path.exists(os.path.join(a.src, p))]
    if not pdfs:
        raise SystemExit("No PDFs found in " + a.src)

    W, PAD, TOP, BOTTOM = 900, 22, 44, 64
    slide_w = W - 2 * PAD
    slides = [render_pdf(os.path.join(a.src, p), int(slide_w * 1.4)) for p in pdfs]  # extra resolution for sharpness
    slide_h = max(round(h * slide_w / w) for (w, h), _ in slides)
    H = TOP + slide_h + BOTTOM
    n = len(pdfs)
    total = n * SECONDS_PER_SLIDE

    # Fade in/out keyframes for one slide; each slide is delayed by its index.
    on = 100 / n
    fade = min(4, on / 4)
    css = ""
    if n > 1:
        css = (f"@keyframes show{{0%{{opacity:0}}{fade:.2f}%{{opacity:1}}{on - fade:.2f}%{{opacity:1}}{on:.2f}%{{opacity:0}}100%{{opacity:0}}}}"
               f".s{{opacity:0;animation:show {total}s infinite}}")
        for i in range(n):
            css += f".s{i}{{animation-delay:{i * SECONDS_PER_SLIDE}s}}"
        # progress bar under the slide
        css += f"@keyframes bar{{from{{width:0}}to{{width:{slide_w}px}}}}.bar{{animation:bar {SECONDS_PER_SLIDE}s linear infinite}}"

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Certificates slideshow">',
         f"<style>text{{font-family:{FONT};}}{css}</style>",
         f'<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="12" fill="#1b2026" stroke="{BLUE}" stroke-opacity=".8"/>',
         f'<text x="{PAD}" y="28" fill="{DIM}" font-size="14">&gt;_</text>',
         f'<text x="{PAD+28}" y="28" fill="{TXT}" font-size="14">kami@certs: ~/certificates</text>',
         f'<text x="{W-PAD}" y="28" text-anchor="end" fill="{LIGHT}" font-size="14">{n} certificate{"s" if n != 1 else ""}</text>']

    for i, (p, ((w, h), b64)) in enumerate(zip(pdfs, slides)):
        m = meta.get(p, {})
        title = m.get("title") or os.path.splitext(p)[0].replace("-", " ").title()
        sub = " · ".join(x for x in [m.get("issuer"), m.get("date")] if x)
        ih = round(h * slide_w / w)
        cls = f' class="s s{i}"' if n > 1 else ""
        o.append(f"<g{cls}>")
        o.append(f'<image x="{PAD}" y="{TOP + (slide_h - ih) / 2}" width="{slide_w}" height="{ih}" '
                 f'href="data:image/jpeg;base64,{b64}" xlink:href="data:image/jpeg;base64,{b64}"/>')
        o.append(f'<text x="{PAD}" y="{TOP + slide_h + 28}" fill="{LIGHT}" font-size="16" font-weight="700">{escape(title)}</text>')
        if sub:
            o.append(f'<text x="{PAD}" y="{TOP + slide_h + 49}" fill="{DIM}" font-size="13">{escape(sub)}</text>')
        o.append(f'<text x="{W-PAD}" y="{TOP + slide_h + 28}" text-anchor="end" fill="{PINK}" font-size="14">{i + 1} / {n}</text>')
        o.append("</g>")

    if n > 1:
        o.append(f'<rect x="{PAD}" y="{TOP + slide_h + 4}" width="{slide_w}" height="2" fill="{BLUE}" fill-opacity=".3"/>')
        o.append(f'<rect class="bar" x="{PAD}" y="{TOP + slide_h + 4}" width="0" height="2" fill="{PINK}"/>')
    o.append("</svg>")

    os.makedirs(a.out, exist_ok=True)
    out = os.path.join(a.out, "certificates.svg")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(o))
    print(f"wrote {out} with {n} slide(s)")


if __name__ == "__main__":
    main()
