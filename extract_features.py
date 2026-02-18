#!/usr/bin/env python3
"""
PIGMENT v5 Pipeline — Step 1: Feature Extraction
Extracts 16 scalar features from a target image for policy network training.

Usage:
    python extract_features.py image.jpg
    python extract_features.py image.jpg --json
    python extract_features.py --batch samples/ --output features.csv
"""
import argparse, json, sys, os, math
import numpy as np

def load_image(path):
    """Load image as float32 RGB array [0,1]."""
    try:
        from PIL import Image
    except ImportError:
        print("[Error] Pillow required: pip install Pillow --break-system-packages", file=sys.stderr)
        sys.exit(1)
    img = Image.open(path).convert('RGB')
    return np.array(img, dtype=np.float32) / 255.0, img.size  # arr, (w,h)

def to_gray(rgb):
    return 0.299*rgb[...,0] + 0.587*rgb[...,1] + 0.114*rgb[...,2]

def to_hsv(rgb):
    r,g,b = rgb[...,0], rgb[...,1], rgb[...,2]
    maxc = np.maximum(np.maximum(r,g),b)
    minc = np.minimum(np.minimum(r,g),b)
    delta = maxc - minc
    s = np.where(maxc > 0, delta / (maxc + 1e-8), 0.0)
    v = maxc
    h = np.zeros_like(r)
    mask_r = (delta > 0) & (maxc == r)
    mask_g = (delta > 0) & (maxc == g)
    mask_b = (delta > 0) & (maxc == b)
    h[mask_r] = ((g[mask_r] - b[mask_r]) / (delta[mask_r] + 1e-8)) % 6
    h[mask_g] = (b[mask_g] - r[mask_g]) / (delta[mask_g] + 1e-8) + 2
    h[mask_b] = (r[mask_b] - g[mask_b]) / (delta[mask_b] + 1e-8) + 4
    h = h / 6.0  # normalise to [0,1]
    return h, s, v

def rgb_to_lab_approx(rgb):
    """Approximate RGB→Lab (D65, simplified)."""
    def gamma(c):
        return np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    r, g, b = gamma(rgb[...,0]), gamma(rgb[...,1]), gamma(rgb[...,2])
    X = 0.4124*r + 0.3576*g + 0.1805*b
    Y = 0.2126*r + 0.7152*g + 0.0722*b
    Z = 0.0193*r + 0.1192*g + 0.9505*b
    def f(t):
        d = 6/29
        return np.where(t > d**3, t**(1/3), t/(3*d**2) + 4/29)
    L = 116*f(Y/1.0) - 16
    a = 500*(f(X/0.9505) - f(Y/1.0))
    b_ch = 200*(f(Y/1.0) - f(Z/1.089))
    return L, a, b_ch

def entropy(gray):
    """Shannon entropy of 8-bit luminance histogram."""
    vals = (gray * 255).astype(np.uint8).flatten()
    counts = np.bincount(vals, minlength=256).astype(np.float64)
    probs = counts / counts.sum()
    probs = probs[probs > 0]
    return float(-np.sum(probs * np.log2(probs)))

def edge_density(gray):
    """Mean Sobel magnitude as fraction of max possible."""
    from scipy.ndimage import sobel
    sx = sobel(gray, axis=1)
    sy = sobel(gray, axis=0)
    mag = np.sqrt(sx**2 + sy**2)
    return float(mag.mean() / (255.0 * math.sqrt(2) / 255.0))

def edge_density_numpy(gray):
    """Sobel without scipy — pure numpy."""
    # 3x3 Sobel kernels via convolution
    padded = np.pad(gray, 1, mode='edge')
    kx = np.array([[-1,0,1],[-2,0,2],[-1,0,1]], dtype=np.float32)
    ky = kx.T
    h, w = gray.shape
    sx = np.zeros_like(gray)
    sy = np.zeros_like(gray)
    for i in range(3):
        for j in range(3):
            sx += kx[i,j] * padded[i:i+h, j:j+w]
            sy += ky[i,j] * padded[i:i+h, j:j+w]
    mag = np.sqrt(sx**2 + sy**2)
    return float(mag.mean())

def color_temperature(rgb):
    """
    Warm/cool score: positive = warm (more red than blue in Lab a/b space).
    Returns float in roughly [-50, +50].
    """
    L, a, b = rgb_to_lab_approx(rgb)
    # b channel: positive = yellow/warm, negative = blue/cool
    return float(b.mean())

def saturation_stats(rgb):
    _, s, _ = to_hsv(rgb)
    return float(s.mean()), float(s.std())

def brightness_stats(rgb):
    gray = to_gray(rgb)
    return float(gray.mean()), float(gray.std())

def contrast(gray):
    return float(gray.std())

def texture_frequency(gray):
    """
    Dominant spatial frequency via 2D FFT magnitude spectrum.
    Returns the centroid of energy in frequency space (0=DC, 1=Nyquist).
    """
    h, w = gray.shape
    # Downsample for speed
    step = max(1, min(h, w) // 128)
    g = gray[::step, ::step]
    F = np.fft.fft2(g)
    F = np.fft.fftshift(F)
    mag = np.abs(F)
    mag[mag.shape[0]//2, mag.shape[1]//2] = 0  # zero DC
    # Frequency coordinates
    fy = np.fft.fftfreq(mag.shape[0])
    fx = np.fft.fftfreq(mag.shape[1])
    fx = np.fft.fftshift(fx)
    fy = np.fft.fftshift(fy)
    FX, FY = np.meshgrid(fx, fy)
    freq = np.sqrt(FX**2 + FY**2)
    total = mag.sum() + 1e-8
    centroid = float((mag * freq).sum() / total)
    return centroid

def hue_diversity(rgb):
    """Number of distinct 30° hue buckets with >2% pixel coverage."""
    h, s, v = to_hsv(rgb)
    # Only count pixels that are sufficiently saturated and bright
    mask = (s > 0.15) & (v > 0.10)
    if mask.sum() < 100:
        return 0
    h_masked = h[mask]
    n_buckets = 12  # 360°/30°
    bucket_idx = (h_masked * n_buckets).astype(int) % n_buckets
    counts = np.bincount(bucket_idx, minlength=n_buckets)
    threshold = 0.02 * mask.sum()
    return int((counts > threshold).sum())

def local_contrast_variance(gray, patch_size=16):
    """
    Variance of per-patch standard deviations.
    High value = image has regions of very different contrast.
    """
    h, w = gray.shape
    stds = []
    for y in range(0, h - patch_size, patch_size):
        for x in range(0, w - patch_size, patch_size):
            patch = gray[y:y+patch_size, x:x+patch_size]
            stds.append(patch.std())
    if not stds:
        return 0.0
    return float(np.var(stds))

def face_confidence(rgb):
    """
    Heuristic face confidence using skin-tone pixel ratio in portrait region.
    Returns 0-1. Not a true face detector but fast and parameter-free.
    """
    # Portrait: check upper-center region
    h, w, _ = rgb.shape
    cy, cx = h // 2, w // 2
    region = rgb[cy//4:3*cy//2, cx//4:3*cx//4]
    if region.size == 0:
        return 0.0
    r, g, b = region[...,0], region[...,1], region[...,2]
    # Skin tone heuristic (Kovac et al.)
    rule1 = (r > 0.35) & (g > 0.2) & (b > 0.1)
    rule2 = (r > g) & (r > b)
    rule3 = abs(r - g) > 0.05
    skin_mask = rule1 & rule2 & rule3
    return float(skin_mask.mean())

def symmetry_scores(gray):
    """
    Horizontal and vertical symmetry as normalized cross-correlation
    between the image and its mirror. Returns (h_sym, v_sym) in [0,1].
    """
    h, w = gray.shape
    # Horizontal symmetry (left vs right flip)
    left = gray[:, :w//2]
    right = np.fliplr(gray[:, w//2:2*(w//2)])
    if left.shape == right.shape and left.size > 0:
        diff = np.abs(left - right)
        h_sym = float(1.0 - diff.mean() * 4)  # scale so perfect=1, random≈0
        h_sym = max(0.0, min(1.0, h_sym))
    else:
        h_sym = 0.5
    # Vertical symmetry (top vs bottom flip)
    top = gray[:h//2, :]
    bottom = np.flipud(gray[h//2:2*(h//2), :])
    if top.shape == bottom.shape and top.size > 0:
        diff = np.abs(top - bottom)
        v_sym = float(1.0 - diff.mean() * 4)
        v_sym = max(0.0, min(1.0, v_sym))
    else:
        v_sym = 0.5
    return h_sym, v_sym

def color_clusters(rgb, k=6):
    """Count of distinct color clusters using k-means (mini version)."""
    try:
        from sklearn.cluster import MiniBatchKMeans
        pixels = rgb.reshape(-1, 3)
        # Sample for speed
        idx = np.random.choice(len(pixels), min(5000, len(pixels)), replace=False)
        km = MiniBatchKMeans(n_clusters=k, n_init=3, random_state=42)
        km.fit(pixels[idx])
        labels = km.labels_
        counts = np.bincount(labels, minlength=k)
        # Count clusters with >5% coverage
        return int((counts > 0.05 * len(idx)).sum())
    except ImportError:
        # Fallback: quantize to 4-bit per channel and count unique colors
        q = (rgb * 16).astype(int)
        q = q.reshape(-1, 3)
        idx = np.random.choice(len(q), min(5000, len(q)), replace=False)
        unique = len(set(map(tuple, q[idx])))
        # Map to 1-k range
        return min(k, max(1, unique // 50))

def extract_features(path):
    """
    Extract 16 features from an image file.
    Returns dict of feature_name → float.
    """
    rgb, (w, h) = load_image(path)
    gray = to_gray(rgb)

    # Attempt scipy sobel, fallback to numpy
    try:
        ed = edge_density(gray)
    except ImportError:
        ed = edge_density_numpy(gray) / 255.0

    sat_mean, sat_var = saturation_stats(rgb)
    bright_mean, bright_var = brightness_stats(rgb)
    h_sym, v_sym = symmetry_scores(gray)

    features = {
        # Low-level
        'entropy':              entropy(gray),
        'edge_density':         ed,
        'color_temperature':    color_temperature(rgb),
        'saturation_mean':      sat_mean,
        'saturation_variance':  sat_var,
        'brightness_mean':      bright_mean,
        'brightness_variance':  bright_var,
        'contrast':             contrast(gray),
        # Frequency / texture
        'texture_frequency':    texture_frequency(gray),
        'hue_diversity':        float(hue_diversity(rgb)),
        'local_contrast_var':   local_contrast_variance(gray),
        # High-level / structural
        'face_confidence':      face_confidence(rgb),
        'horizontal_symmetry':  h_sym,
        'vertical_symmetry':    v_sym,
        'color_clusters':       float(color_clusters(rgb)),
        'aspect_ratio':         float(w) / float(h),
    }
    return features

FEATURE_NAMES = [
    'entropy', 'edge_density', 'color_temperature',
    'saturation_mean', 'saturation_variance',
    'brightness_mean', 'brightness_variance', 'contrast',
    'texture_frequency', 'hue_diversity', 'local_contrast_var',
    'face_confidence', 'horizontal_symmetry', 'vertical_symmetry',
    'color_clusters', 'aspect_ratio',
]

def main():
    ap = argparse.ArgumentParser(description='PIGMENT v5 — Image Feature Extractor')
    ap.add_argument('image', nargs='?', help='Image file to analyze')
    ap.add_argument('--json', action='store_true', help='Output as JSON')
    ap.add_argument('--batch', metavar='DIR', help='Process a directory of images')
    ap.add_argument('--output', '-o', metavar='CSV', help='Output CSV path (for --batch)')
    args = ap.parse_args()

    if args.batch:
        import csv, glob
        exts = ('*.jpg', '*.jpeg', '*.png', '*.webp', '*.bmp')
        paths = []
        for ext in exts:
            paths += glob.glob(os.path.join(args.batch, ext))
            paths += glob.glob(os.path.join(args.batch, '**', ext), recursive=True)
        paths = sorted(set(paths))
        if not paths:
            print(f"[Error] No images found in {args.batch}", file=sys.stderr)
            sys.exit(1)
        out_path = args.output or 'features.csv'
        with open(out_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['image_path'] + FEATURE_NAMES)
            writer.writeheader()
            for i, p in enumerate(paths):
                try:
                    feats = extract_features(p)
                    feats['image_path'] = p
                    writer.writerow(feats)
                    print(f"[{i+1}/{len(paths)}] {os.path.basename(p)}: entropy={feats['entropy']:.2f} face={feats['face_confidence']:.2f}")
                except Exception as e:
                    print(f"[WARN] Skipping {p}: {e}", file=sys.stderr)
        print(f"\n[PIGMENT] ✓ Features saved → {out_path} ({len(paths)} images)")
        return

    if not args.image:
        ap.print_help()
        sys.exit(0)

    feats = extract_features(args.image)

    if args.json:
        print(json.dumps(feats, indent=2))
        return

    # Pretty print
    print(f"\n{'─'*52}")
    print(f"  PIGMENT Feature Vector: {os.path.basename(args.image)}")
    print(f"{'─'*52}")
    groups = [
        ('Low-level', ['entropy','edge_density','color_temperature','saturation_mean','saturation_variance','brightness_mean','brightness_variance','contrast']),
        ('Texture / Frequency', ['texture_frequency','hue_diversity','local_contrast_var']),
        ('Structure', ['face_confidence','horizontal_symmetry','vertical_symmetry','color_clusters','aspect_ratio']),
    ]
    for group_name, keys in groups:
        print(f"\n  {group_name}:")
        for k in keys:
            v = feats[k]
            bar = '█' * int(min(20, max(0, v if v <= 1 else v/10) * 20))
            print(f"    {k:<24} {v:>8.4f}  {bar}")
    print(f"\n{'─'*52}")
    print(f"  Total features: {len(feats)}")
    print()

if __name__ == '__main__':
    main()
