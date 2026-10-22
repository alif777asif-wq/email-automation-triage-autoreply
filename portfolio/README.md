# Portfolio images

Six 4000 x 3000 px images (4:3) built from `results/results.json` and the generated test inbox. Every figure on every image is read from
`results.json`, and every line of message text on image 2 is read from `data/test/inbox/`, `results/outputs/test/triage.csv` and the delivered
reply in `results/outputs/test/sample-replies/` (`provenance.json` lists each one with its source). The outcome shown for each message is
asserted against the triage log and the SMTP ledger when the image is built. The code excerpt on image 4 is read from `src/mailtriage/sender.py`.

```bash
pip install -r portfolio/requirements.txt && playwright install chromium
./reproduce.sh                        # writes the results the images read (skip if results/ is already there)
python portfolio/build_images.py     # results + test inbox -> portfolio/html/*.html
python portfolio/export_images.py    # html -> portfolio/exports/*.png and *.jpg (+ export-report.json)
```

`export_images.py` verifies, per image: 4000 x 3000 px, 300 DPI metadata, embedded sRGB profile, file size under 5 MB, that no
fallback font was used (asked of the browser per text node), that no text is clipped or overlapping, and the smallest text size.
`contrast-audit.json` lists WCAG contrast ratios for every text colour on its background in both themes.
`fresh-run-check.json` records the comparison of this tree's `results/results.json` with a fresh-directory `./reproduce.sh` run.

Fonts (embedded, SIL OFL 1.1): see `fonts/FONTS.md`.
