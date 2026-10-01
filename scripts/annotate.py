#!/usr/bin/env python3
"""Red box + label on a screenshot (Phase 7 evidence; used from Phase 6 on).

  annotate.py <screenshot.png> --label "BUG-03: expected company name, got empty"
              [--hierarchy h.json (--id TESTID | --text REGEX)] [--bounds x1,y1,x2,y2]
              [--missing "Company name"] [--out path]

Target, first match wins:
  --id / --text  element found in a Maestro hierarchy dump (bounds in points)
  --bounds       region in points (e.g. where Figma places a missing element)
  --missing      no element: a red banner "MISSING: <text>" across the top
Points → pixels: scale = screenshot width / hierarchy root width (3.0 on an @3x iPhone). Without a
hierarchy, --bounds need an explicit --scale.
Prints JSON {out, scale, box}. Output defaults to <name>_annotated.png beside the input.
"""
import argparse
import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RED = (230, 0, 0)


def nums(b):
    return [int(x) for x in re.findall(r'-?\d+', b or '')]


def find(h, test_id=None, text_re=None):
    """Smallest element whose id equals test_id or whose text/accessibility text matches text_re."""
    rx = re.compile(text_re) if text_re else None
    best = None

    def walk(n):
        nonlocal best
        a = n.get('attributes', {})
        b = nums(a.get('bounds'))
        hit = (test_id and a.get('resource-id') == test_id) or (
            rx and (rx.search(a.get('text', '') or '') or rx.search(a.get('accessibilityText', '') or '')))
        if hit and len(b) == 4 and b[2] > b[0] and b[3] > b[1]:
            area = (b[2] - b[0]) * (b[3] - b[1])
            if best is None or area < best[0]:
                best = (area, b)
        for c in n.get('children', []):
            walk(c)
    walk(h)
    return best[1] if best else None


def root_width(h):
    stack = [h]
    while stack:
        n = stack.pop(0)
        b = nums(n.get('attributes', {}).get('bounds'))
        if len(b) == 4 and b[2] > 0:
            return b[2]
        stack.extend(n.get('children', []))
    return None


def font(size):
    for f in ('/System/Library/Fonts/Supplemental/Arial Bold.ttf', '/System/Library/Fonts/Helvetica.ttc',
              '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'):
        try:
            return ImageFont.truetype(f, size)
        except Exception:
            continue
    return ImageFont.load_default(size=size)


def label_box(draw, img, xy, text, fnt):
    pad = 10
    tw, th = draw.textbbox((0, 0), text, font=fnt)[2:]
    x, y = xy
    x = max(0, min(x, img.width - tw - 2 * pad))
    y = y - th - 2 * pad if y - th - 2 * pad > 0 else y
    draw.rectangle([x, y, x + tw + 2 * pad, y + th + 2 * pad], fill=RED)
    draw.text((x + pad, y + pad - 2), text, fill='white', font=fnt)



def check_label(label):
    """Pillow draws Arabic unshaped (disconnected, reversed) without libraqm; labels are English."""
    from PIL import features
    if re.search(r'[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]', label or '') and not features.check('raqm'):
        raise SystemExit(json.dumps({'error': 'label contains Arabic; write it in English (quote the UI text in the '
                                              'finding instead) — Pillow here cannot shape Arabic'}))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('screenshot')
    ap.add_argument('--label', required=True)
    ap.add_argument('--hierarchy'); ap.add_argument('--id'); ap.add_argument('--text')
    ap.add_argument('--bounds'); ap.add_argument('--missing'); ap.add_argument('--scale', type=float)
    ap.add_argument('--out')
    a = ap.parse_args()
    check_label(a.label)

    img = Image.open(a.screenshot).convert('RGB')
    draw = ImageDraw.Draw(img)
    stroke = max(4, img.width // 160)
    fnt = font(max(24, img.width // 30))
    h = json.load(open(a.hierarchy)) if a.hierarchy else None
    scale = a.scale or (img.width / root_width(h) if h and root_width(h) else None)

    box = None
    if h and (a.id or a.text):
        box = find(h, a.id, a.text)
        if box is None and not (a.bounds or a.missing):
            print(json.dumps({'error': 'element not found', 'id': a.id, 'text': a.text}))
            sys.exit(1)
    if box is None and a.bounds:
        box = nums(a.bounds)
    if box is not None:
        if not scale:
            print(json.dumps({'error': 'no scale: pass --hierarchy or --scale'}))
            sys.exit(1)
        px = [int(v * scale) for v in box]
        draw.rectangle(px, outline=RED, width=stroke)
        label_box(draw, img, (px[0], px[1]), a.label, fnt)
    elif a.missing:
        bh = int(img.height * 0.06)
        top = int(img.height * 0.06)  # below the status bar
        draw.rectangle([0, top, img.width, top + bh], fill=RED)
        txt = f'MISSING: {a.missing} · {a.label}'
        draw.text((stroke * 3, top + (bh - fnt.size) // 2), txt, fill='white', font=fnt)
        draw.rectangle([0, 0, img.width - 1, img.height - 1], outline=RED, width=stroke)
    else:
        print(json.dumps({'error': 'give --id/--text with --hierarchy, --bounds, or --missing'}))
        sys.exit(2)

    out = a.out or str(Path(a.screenshot).with_name(Path(a.screenshot).stem + '_annotated.png'))
    img.save(out)
    print(json.dumps({'out': out, 'scale': scale, 'box': box}, ensure_ascii=False))


if __name__ == '__main__':
    main()
