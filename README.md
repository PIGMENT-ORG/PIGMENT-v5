# PIGMENT v5 — ML-Optimized Compiler Pipeline

## What's New in v5

The compiler (`pigment.py`) now accepts `--param` overrides for all major rendering parameters.
The pipeline scripts collect training data by sweeping those parameters across your evolved samples,
then train a policy network that predicts optimal parameters from image statistics.

---

## Quick Start

### 1. Compile with manual parameter overrides

```bash
python pigment.py painting.pg \
  --param craquelure.density=0.8 \
  --param sfumato.kernel=1.4 \
  --param sss.radius=0.5 \
  --param illumination.weight=1.2 \
  --param age_shift.intensity=0.6 \
  --param color_temp.offset=0.3
```

### 2. Extract features from a target image

```bash
python extract_features.py target.jpg
python extract_features.py target.jpg --json > features.json
python extract_features.py --batch ./images/ --output features.csv
```

### 3. Sweep parameter combinations for one sample

```bash
python sweep_compile.py painting.pg --output-dir ./sweep_out/
python sweep_compile.py --list-grid   # Show all 216 combinations
python sweep_compile.py painting.pg --single 42  # One combo only
```

### 4. Score rendered variants against target

```bash
python score_renders.py \
  --manifest sweep_out/painting_manifest.json \
  --target target.jpg \
  --output scores.csv
```

### 5. Run the full pipeline on your sample library

```bash
# Samples directory: each subdir has painting.pg + target.jpg
python build_dataset.py \
  --samples-dir ./samples/ \
  --output-dir ./pipeline_out/ \
  --workers 8

# Or step by step:
python build_dataset.py --samples-dir ./samples/ --output-dir ./pipeline_out/ --features-only
python build_dataset.py --samples-dir ./samples/ --output-dir ./pipeline_out/ --sweep-only
python build_dataset.py --samples-dir ./samples/ --output-dir ./pipeline_out/ --score-only
python build_dataset.py --train-only --output-dir ./pipeline_out/
```

### 6. Compile with ML-optimized parameters

```bash
python optimize.py \
  --model pipeline_out/models/pigment_policy.pkl \
  --image target.jpg \
  painting.pg

# Explain predictions:
python optimize.py --model model.pkl --image target.jpg --explain painting.pg

# Just print params without compiling:
python optimize.py --model model.pkl --image target.jpg --params-only
```

---

## Parameter Reference

| Parameter | Range | Default | Effect |
|-----------|-------|---------|--------|
| `craquelure.density` | 0.1–3.0 | 1.0 | Crack pattern density (0.2=sparse, 1.2=dense) |
| `sss.radius` | 0.0–3.0 | 1.0 | Subsurface scattering radius |
| `sfumato.kernel` | 0.1–5.0 | 1.0 | Edge softness multiplier |
| `illumination.weight` | 0.0–2.0 | 1.0 | Face lighting drama (0.7=flat, 1.3=dramatic) |
| `age_shift.intensity` | 0.0–3.0 | 1.0 | Varnish/aging amount |
| `color_temp.offset` | -1.0–1.0 | 0.0 | Warm (+) or cool (-) color shift |

---

## Feature Vector (16 dimensions)

| Feature | Description |
|---------|-------------|
| `entropy` | Shannon entropy of luminance histogram |
| `edge_density` | Mean Sobel magnitude |
| `color_temperature` | Lab b-channel mean (warm vs cool) |
| `saturation_mean` | Mean HSV saturation |
| `saturation_variance` | Variance of HSV saturation |
| `brightness_mean` | Mean luminance |
| `brightness_variance` | Variance of luminance |
| `contrast` | Std dev of luminance |
| `texture_frequency` | FFT energy centroid |
| `hue_diversity` | Distinct hue buckets (30° each, >2% coverage) |
| `local_contrast_var` | Variance of per-patch contrast |
| `face_confidence` | Skin-tone heuristic score |
| `horizontal_symmetry` | Left/right mirror similarity |
| `vertical_symmetry` | Top/bottom mirror similarity |
| `color_clusters` | Distinct color cluster count |
| `aspect_ratio` | Width / height |

---

## The Loop

```
Evolutionary painter  →  .pg genome
     ↓
extract_features.py   →  16-dim image vector
     ↓
sweep_compile.py      →  216 HTML variants per sample
     ↓
score_renders.py      →  SSIM score per variant → optimal params
     ↓
build_dataset.py      →  (features, optimal_params) training dataset
     ↓
GradientBoosting      →  pigment_policy.pkl
     ↓
optimize.py           →  new image → predicted params → compiled shader
     ↓
Back to evolutionary painter with better rendering quality
```

---

## Dependencies

```bash
pip install numpy Pillow scikit-image scikit-learn pandas playwright --break-system-packages
playwright install chromium
```

Optional (faster SSIM): `pip install scikit-image --break-system-packages`
Optional (faster clusters): `pip install scikit-learn --break-system-packages`
