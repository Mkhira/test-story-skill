#!/usr/bin/env python3
"""App screenshot next to its Figma frame, for design-deviation evidence (Phase 7).

  side_by_side.py <app.png> <figma.png> --out <path> [--label "DD-01: …"]
                  [--figma-crop y1,y2]       # Figma points: the part of a long frame that matches
                                             # this app screenshot (a scroll position)
                  [--app-box x1,y1,x2,y2 --app-scale 3]   # app points → red box on the app side
                  [--figma-box x1,y1,x2,y2]               # Figma points → red box on the Figma side
                  [--figma-scale 1]          # Figma export pixels per point (1 unless exported @2x)

Both sides are scaled to the same height and labelled "App" / "Figma". Prints JSON {out}.
Pixel diffs are deliberately not computed: real data, device size and fonts always differ.
"""
import argparse
import json
import re

from PIL import Image, ImageDraw, ImageFont

RED = (230, 0, 0)


def nums(s):
    return [float(x) for x in re.findall(r'-?\d+(?:\.\d+)?', s or '')]


def font(size):
    for f in ('/System/Library/Fonts/Supplemental/Arial Bold.ttf', '/System/Library/Fonts/Helvetica.ttc',
              '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'):
        try:
            return ImageFont.truetype(f, size)
        except Exception:
            continue
    return ImageFont.load_default(size=size)


def box(img, b, scale, width):
    if b:
        d = ImageDraw.Draw(img)
        d.rectangle([int(v * scale) for v in b], outline=RED, width=width)



def check_label(label):
    """Pillow draws Arabic unshaped (disconnected, reversed) without libraqm; labels are English."""
    from PIL import features
    if re.search(r'[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]', label or '') and not features.check('raqm'):
        raise SystemExit(json.dumps({'error': 'label contains Arabic; write it in English (quote the UI text in the '
                                              'finding instead) — Pillow here cannot shape Arabic'}))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('app'); ap.add_argument('figma')
    ap.add_argument('--out', required=True); ap.add_argument('--label', default='')
    ap.add_argument('--figma-crop'); ap.add_argument('--figma-scale', type=float, default=1.0)
    ap.add_argument('--app-box'); ap.add_argument('--app-scale', type=float, default=3.0)
    ap.add_argument('--figma-box')
    a = ap.parse_args()
    check_label(a.label)

    app = Image.open(a.app).convert('RGB')
    fig = Image.open(a.figma).convert('RGB')
    box(app, nums(a.app_box) if a.app_box else None, a.app_scale, max(4, app.width // 160))
    fbox = nums(a.figma_box) if a.figma_box else None
    if a.figma_crop:
        y1, y2 = nums(a.figma_crop)
        if fbox:
            fbox = [fbox[0], fbox[1] - y1, fbox[2], fbox[3] - y1]
        fig = fig.crop((0, int(y1 * a.figma_scale), fig.width, int(y2 * a.figma_scale)))
    box(fig, fbox, a.figma_scale, max(2, fig.width // 160))

    h = 1400
    app = app.resize((int(app.width * h / app.height), h))
    fig = fig.resize((int(fig.width * h / fig.height), h))
    gap, head = 40, 90
    foot = 80 if a.label else 0
    canvas = Image.new('RGB', (app.width + fig.width + gap * 3, h + head + foot + gap), 'white')
    d = ImageDraw.Draw(canvas)
    f = font(44)
    canvas.paste(app, (gap, head)); canvas.paste(fig, (app.width + gap * 2, head))
    d.text((gap, 20), 'App', fill='black', font=f)
    d.text((app.width + gap * 2, 20), 'Figma', fill='black', font=f)
    if a.label:
        d.rectangle([0, h + head + gap // 2, canvas.width, canvas.height], fill=RED)
        d.text((gap, h + head + gap // 2 + 14), a.label, fill='white', font=font(36))
    canvas.save(a.out)
    print(json.dumps({'out': a.out}))


if __name__ == '__main__':
    main()
