#!/usr/bin/env python3
"""
PIGMENT v5 Pipeline — Step 3: Render Scoring
Renders compiled HTML files headlessly and computes SSIM against target images.
Outputs scored CSV rows for policy network training.

Requires: playwright (pip install playwright --break-system-packages && playwright install chromium)

Usage:
    python score_renders.py --manifest sweep_out/sample_manifest.json --target image.jpg
    python score_renders.py --manifest sweep_out/sample_manifest.json --target image.jpg --output scores.csv
    python score_renders.py --check   # Check dependencies
"""
import argparse, json, sys, os, csv, time, tempfile
import numpy as np
from pathlib import Path

# ── Dependency check ─────────────────────────────────────────────────────────

def check_deps(silent=False):
    ok = True
    deps = {}
    try:
        import numpy
        deps['numpy'] = numpy.__version__
    except ImportError:
        deps['numpy'] = 'MISSING'
        ok = False
    try:
        from PIL import Image
        deps['Pillow'] = Image.__version__
    except ImportError:
        deps['Pillow'] = 'MISSING'
        ok = False
    try:
        from skimage.metrics import structural_similarity
        import skimage
        deps['scikit-image'] = skimage.__version__
    except ImportError:
        deps['scikit-image'] = 'MISSING (SSIM will use fallback)'
    try:
        from playwright.sync_api import sync_playwright
        deps['playwright'] = 'OK'
    except ImportError:
        deps['playwright'] = 'MISSING'
        ok = False
    if not silent:
        print("\nDependency Status:")
        for name, ver in deps.items():
            status = '✓' if 'MISSING' not in str(ver) else '✗'
            print(f"  {status} {name}: {ver}")
        if not ok:
            print("\n  Install missing deps:")
            print("  pip install numpy Pillow scikit-image playwright --break-system-packages")
            print("  playwright install chromium")
        print()
    return ok

# ── Image utilities ───────────────────────────────────────────────────────────

def load_image_rgb(path, size=None):
    """Load image as uint8 RGB array, optionally resize."""
    from PIL import Image
    img = Image.open(path).convert('RGB')
    if size:
        img = img.resize(size, Image.LANCZOS)
    return np.array(img, dtype=np.uint8)

def compute_ssim(img_a, img_b):
    """
    Compute SSIM between two uint8 RGB arrays.
    Falls back to simple MSE-based metric if scikit-image unavailable.
    """
    try:
        from skimage.metrics import structural_similarity
        # Convert to float [0,1]
        a = img_a.astype(np.float32) / 255.0
        b = img_b.astype(np.float32) / 255.0
        ssim_val, _ = structural_similarity(a, b, channel_axis=2, data_range=1.0, full=True)
        return float(ssim_val)
    except ImportError:
        # Fallback: PSNR-derived similarity
        mse = np.mean((img_a.astype(np.float32) - img_b.astype(np.float32)) ** 2)
        if mse == 0:
            return 1.0
        psnr = 20 * np.log10(255.0 / np.sqrt(mse))
        # Normalise PSNR to [0,1]: typical range 20–45 dB
        return float(np.clip((psnr - 20) / 25.0, 0.0, 1.0))

# ── Headless rendering ────────────────────────────────────────────────────────

class HeadlessRenderer:
    """
    Renders PIGMENT HTML files using Playwright headless Chromium.
    Reuses a single browser instance for efficiency.
    """
    def __init__(self, width=400, height=600, wait_ms=800):
        self.width = width
        self.height = height
        self.wait_ms = wait_ms
        self._pw = None
        self._browser = None

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-gpu-sandbox',
                  '--enable-webgl', '--ignore-gpu-blacklist']
        )
        return self

    def __exit__(self, *_):
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    def render(self, html_path):
        """
        Render html_path and return a PIL Image (RGB) of the canvas content.
        Returns None on failure.
        """
        try:
            page = self._browser.new_page(viewport={'width': self.width, 'height': self.height})
            page.goto(f'file://{os.path.abspath(html_path)}')
            page.wait_for_timeout(self.wait_ms)

            # Try to screenshot just the canvas element
            canvas = page.query_selector('canvas')
            if canvas:
                png_bytes = canvas.screenshot()
            else:
                png_bytes = page.screenshot()
            page.close()

            from PIL import Image
            import io
            img = Image.open(io.BytesIO(png_bytes)).convert('RGB')
            return img
        except Exception as e:
            print(f"  [WARN] Render failed for {os.path.basename(html_path)}: {e}", file=sys.stderr)
            return None

# ── Scoring pipeline ─────────────────────────────────────────────────────────

def score_manifest(manifest_path, target_path, output_csv=None,
                   render_size=(200, 300), wait_ms=800,
                   keep_renders=False, workers=4):
    """
    Score all HTML files in a manifest against a target image.
    Writes results to CSV.
    Returns list of score dicts.
    """
    with open(manifest_path) as f:
        manifest = json.load(f)

    sample_id = manifest['sample_id']
    combos = [c for c in manifest['combos'] if c['compiled'] and c['html_path']]
    total = len(combos)

    if total == 0:
        print("[Error] No compiled HTML files in manifest.", file=sys.stderr)
        return []

    # Load and resize target image to match render size
    target_img = load_image_rgb(target_path, size=render_size)

    output_csv = output_csv or f"{sample_id}_scores.csv"
    fieldnames = ['sample_id', 'combo_idx', 'combo_id', 'ssim'] + manifest['param_keys']

    print(f"[PIGMENT Score] Scoring {total} renders for sample '{sample_id}'")
    print(f"               Target: {target_path} (resized to {render_size[0]}×{render_size[1]})")
    print(f"               Output: {output_csv}")
    print()

    scores = []
    t0 = time.time()

    with HeadlessRenderer(width=render_size[0], height=render_size[1], wait_ms=wait_ms) as renderer:
        with open(output_csv, 'w', newline='') as csvf:
            writer = csv.DictWriter(csvf, fieldnames=fieldnames)
            writer.writeheader()

            for i, combo_entry in enumerate(combos):
                html_path = combo_entry['html_path']
                params = combo_entry['params']
                global_idx = combo_entry['global_idx']
                cid = combo_entry['combo_id']

                rendered_img = renderer.render(html_path)
                if rendered_img is None:
                    continue

                # Resize rendered output to match target
                rendered_arr = load_image_rgb.__wrapped__(rendered_img, render_size) \
                    if hasattr(load_image_rgb, '__wrapped__') else \
                    np.array(rendered_img.resize(render_size, 1), dtype=np.uint8)

                ssim = compute_ssim(target_img, rendered_arr)

                row = {
                    'sample_id': sample_id,
                    'combo_idx': global_idx,
                    'combo_id': cid,
                    'ssim': f"{ssim:.6f}",
                }
                row.update(params)
                writer.writerow(row)
                csvf.flush()
                scores.append({'combo_idx': global_idx, 'ssim': ssim, 'params': params})

                # Clean up HTML if not keeping renders
                if not keep_renders:
                    try:
                        os.remove(html_path)
                    except OSError:
                        pass

                elapsed = time.time() - t0
                rate = (i + 1) / elapsed
                eta = (total - i - 1) / rate if rate > 0 else 0

                if (i + 1) % 10 == 0 or i == total - 1:
                    print(f"  [{i+1:>3}/{total}] SSIM={ssim:.4f}  {rate:.1f} renders/s  ETA {eta:.0f}s")

    # Find best combo
    if scores:
        best = max(scores, key=lambda x: x['ssim'])
        worst = min(scores, key=lambda x: x['ssim'])
        print(f"\n[PIGMENT Score] ✓ Complete — {len(scores)}/{total} scored")
        print(f"               Best  SSIM: {best['ssim']:.4f} (combo #{best['combo_idx']})")
        print(f"               Worst SSIM: {worst['ssim']:.4f}")
        print(f"               Range: {best['ssim']-worst['ssim']:.4f}")
        print(f"               Scores → {output_csv}")

    return scores

# ── Simplified renderer using numpy (no Playwright) ─────────────────────────

def render_via_screenshot_fallback(html_path, render_size):
    """
    Fallback renderer: reads canvas element data via JS injection.
    Only works if Playwright is available.
    """
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True,
                args=['--no-sandbox', '--enable-webgl', '--ignore-gpu-blacklist'])
            page = browser.new_page(viewport={'width': render_size[0], 'height': render_size[1]})
            page.goto(f'file://{os.path.abspath(html_path)}')
            page.wait_for_timeout(600)
            canvas = page.query_selector('canvas')
            if canvas:
                return canvas.screenshot()
            result = page.screenshot()
            browser.close()
            return result
    except Exception as e:
        return None

# ── Build training dataset from scored samples ────────────────────────────────

def build_training_dataset(score_csvs, feature_csvs, output_csv='training_dataset.csv'):
    """
    Merge per-sample scores with image features to build the final training dataset.
    For each sample, identifies the optimal parameter combination (highest SSIM)
    and creates one training row: (image_features, optimal_params, best_ssim).

    Args:
        score_csvs: list of paths to *_scores.csv files
        feature_csvs: list of paths to features.csv files (or single path)
        output_csv: output path
    """
    from sweep_compile import PARAM_KEYS

    # Load features
    features_by_path = {}
    feat_csvs = [feature_csvs] if isinstance(feature_csvs, str) else feature_csvs
    for fcsv in feat_csvs:
        with open(fcsv) as f:
            reader = csv.DictReader(f)
            for row in reader:
                features_by_path[row['image_path']] = row

    from extract_features import FEATURE_NAMES

    rows = []
    for scsv in score_csvs:
        with open(scsv) as f:
            reader = csv.DictReader(f)
            all_combos = list(reader)

        if not all_combos:
            continue

        # Find best SSIM combo for this sample
        best = max(all_combos, key=lambda r: float(r['ssim']))
        sample_id = best['sample_id']

        # Try to match to feature vector
        feat_row = None
        for path, feats in features_by_path.items():
            if sample_id in path or Path(path).stem == sample_id:
                feat_row = feats
                break

        if feat_row is None:
            print(f"[WARN] No feature vector for sample '{sample_id}' — skipping")
            continue

        row = {'sample_id': sample_id, 'best_ssim': best['ssim']}
        for fn in FEATURE_NAMES:
            row[f'feat_{fn}'] = feat_row.get(fn, '')
        for pk in PARAM_KEYS:
            row[f'opt_{pk}'] = best.get(pk, '')
        rows.append(row)

    if not rows:
        print("[Error] No rows to write.", file=sys.stderr)
        return

    fieldnames = ['sample_id', 'best_ssim'] + \
                 [f'feat_{fn}' for fn in FEATURE_NAMES] + \
                 [f'opt_{pk}' for pk in PARAM_KEYS]

    with open(output_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n[PIGMENT] ✓ Training dataset: {len(rows)} samples → {output_csv}")

# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description='PIGMENT v5 — Render Scorer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    ap.add_argument('--manifest', '-m', help='Manifest JSON from sweep_compile.py')
    ap.add_argument('--target', '-t', help='Target image to compare against')
    ap.add_argument('--output', '-o', help='Output CSV path')
    ap.add_argument('--wait-ms', type=int, default=800, help='Browser wait time per render (ms)')
    ap.add_argument('--keep-renders', action='store_true', help='Keep HTML files after scoring')
    ap.add_argument('--render-size', default='200x300', help='Render resolution WxH (default: 200x300)')
    ap.add_argument('--check', action='store_true', help='Check dependencies and exit')
    ap.add_argument('--build-dataset', nargs='+', metavar='SCORE_CSV',
        help='Build training dataset from scored CSV files (requires --features and --output)')
    ap.add_argument('--features', nargs='+', metavar='FEAT_CSV',
        help='Feature CSV files for --build-dataset')
    args = ap.parse_args()

    if args.check:
        ok = check_deps()
        sys.exit(0 if ok else 1)

    if args.build_dataset:
        if not args.features:
            print("[Error] --build-dataset requires --features", file=sys.stderr)
            sys.exit(1)
        build_training_dataset(args.build_dataset, args.features, args.output or 'training_dataset.csv')
        return

    if not args.manifest:
        ap.print_help()
        sys.exit(0)

    if not args.target:
        print("[Error] --target image is required", file=sys.stderr)
        sys.exit(1)

    w, h = map(int, args.render_size.lower().split('x'))

    score_manifest(
        manifest_path=args.manifest,
        target_path=args.target,
        output_csv=args.output,
        render_size=(w, h),
        wait_ms=args.wait_ms,
        keep_renders=args.keep_renders,
    )

# Monkey-patch for PIL array conversion
def _img_to_arr(img, size):
    from PIL import Image
    import numpy as np
    if isinstance(img, Image.Image):
        return np.array(img.resize(size, Image.LANCZOS), dtype=np.uint8)
    return img

load_image_rgb.__wrapped__ = _img_to_arr

if __name__ == '__main__':
    main()
