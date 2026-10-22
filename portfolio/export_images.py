"""Render portfolio/html/*.html to 4000x3000 PNG and JPG, verifying fonts, layout and file properties.

Needs: pip install -r portfolio/requirements.txt && playwright install chromium
"""
from __future__ import annotations

import io
import json
from pathlib import Path

from PIL import Image, ImageCms
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
OUT = HERE / "exports"
OUT.mkdir(exist_ok=True)
W, H, SCALE = 1600, 1200, 2.5  # CSS px x device scale = 4000 x 3000
MAX_BYTES = 5 * 1024 * 1024
SRGB = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()

JS_BOXES = """() => {
  const out = [], walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n; while ((n = walker.nextNode())) {
    if (!n.textContent.trim()) continue;
    const cs = getComputedStyle(n.parentElement), fs = parseFloat(cs.fontSize);
    const lh = cs.lineHeight === 'normal' ? fs * 1.2 : parseFloat(cs.lineHeight);
    const r = document.createRange(); r.selectNodeContents(n);
    for (const b of r.getClientRects()) {          // one rect per rendered line, clamped to the line box
      if (b.width < 1) continue;
      const cy = (b.top + b.bottom) / 2, h = Math.min(b.height, lh);
      out.push({t: n.textContent.trim().slice(0, 40), x0: b.left, y0: cy - h / 2, x1: b.right, y1: cy + h / 2, fs});
    }
  }
  const clipped = [...document.querySelectorAll('*')].filter(e => e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflow !== 'visible'
      && e.tagName !== 'HTML' && e.tagName !== 'BODY').map(e => e.className || e.tagName);
  return {boxes: out, clipped};
}"""


def custom_fonts_only(cdp) -> dict:
    """Ask Chromium which fonts it really used for every element that holds text."""
    tree = cdp.send("DOM.getDocument", {"depth": -1, "pierce": True})["root"]
    used: dict[str, int] = {}
    bad: list[str] = []

    def walk(node):
        kids = node.get("children", [])
        if node.get("nodeType") == 1 and any(k.get("nodeType") == 3 and k["nodeValue"].strip() for k in kids):
            for f in cdp.send("CSS.getPlatformFontsForNode", {"nodeId": node["nodeId"]})["fonts"]:
                used[f["familyName"]] = used.get(f["familyName"], 0) + f["glyphCount"]
                if not f["isCustomFont"]:
                    bad.append(f["familyName"])
        for k in kids:
            walk(k)

    walk(tree)
    return {"glyphs_by_family": used, "fallback_fonts_used": sorted(set(bad))}


def main() -> None:
    report = []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--force-color-profile=srgb", "--font-render-hinting=none"])
        ctx = browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=SCALE)
        for html_path in sorted((HERE / "html").glob("*.html")):
            page = ctx.new_page()
            page.goto(html_path.as_uri())
            page.evaluate("document.fonts.ready")
            statuses = page.evaluate("Array.from(document.fonts).map(f => f.status)")
            cdp = ctx.new_cdp_session(page)
            cdp.send("DOM.enable")
            cdp.send("CSS.enable")
            fonts = custom_fonts_only(cdp)
            lay = page.evaluate(JS_BOXES)
            boxes = lay["boxes"]
            overlaps = []
            for i, a in enumerate(boxes):
                for b in boxes[i + 1:]:
                    ox = min(a["x1"], b["x1"]) - max(a["x0"], b["x0"])
                    oy = min(a["y1"], b["y1"]) - max(a["y0"], b["y0"])
                    if ox > 3 and oy > 6:
                        overlaps.append([a["t"], b["t"]])
            min_margin = min(min(b["x0"], b["y0"], W - b["x1"], H - b["y1"]) for b in boxes)
            png = page.screenshot(type="png", clip={"x": 0, "y": 0, "width": W, "height": H})
            page.close()
            im = Image.open(io.BytesIO(png)).convert("RGB")
            assert im.size == (4000, 3000), im.size
            stem = html_path.stem
            im.save(OUT / f"{stem}.png", icc_profile=SRGB, dpi=(300, 300), optimize=True)
            im.save(OUT / f"{stem}.jpg", quality=100, subsampling=0, optimize=True, icc_profile=SRGB, dpi=(300, 300))
            chk = Image.open(OUT / f"{stem}.png")
            row = {"image": stem, "pixels": list(chk.size), "dpi": [round(x) for x in chk.info["dpi"]],
                   "srgb_profile_embedded": bool(chk.info.get("icc_profile")),
                   "png_bytes": (OUT / f"{stem}.png").stat().st_size, "jpg_bytes": (OUT / f"{stem}.jpg").stat().st_size,
                   "within_5MB": max((OUT / f"{stem}.png").stat().st_size, (OUT / f"{stem}.jpg").stat().st_size) <= MAX_BYTES,
                   "font_load_errors": sum(1 for s_ in statuses if s_ == "error"), **fonts,
                   "overlapping_text_pairs": overlaps, "clipped_elements": lay["clipped"],
                   "min_text_margin_css_px": round(min_margin, 1), "smallest_text_css_px": min(b["fs"] for b in boxes)}
            report.append(row)
            print(json.dumps(row))
        browser.close()
    (OUT / "export-report.json").write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
