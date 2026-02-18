#!/usr/bin/env python3
"""
PIGMENT v5 Pipeline — Orchestrator
Runs the complete feature extraction + parameter sweep + scoring pipeline
across a directory of (.pg, target_image) pairs.

Directory structure expected:
    samples/
        sample_001/
            painting.pg
            target.jpg
        sample_002/
            painting.pg
            target.png
        ...

Or flat layout with matching names:
    samples/
        foo.pg
        foo.jpg      (or foo.png)

Usage:
    python build_dataset.py --samples-dir ./samples --output-dir ./pipeline_out
    python build_dataset.py --samples-dir ./samples --output-dir ./pipeline_out --workers 8
    python build_dataset.py --resume --output-dir ./pipeline_out  # Skip already-done samples
    python build_dataset.py --train-only --output-dir ./pipeline_out  # Just train the model
"""
import argparse, sys, os, json, glob, csv, time, subprocess
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

# ── Sample discovery ─────────────────────────────────────────────────────────

IMAGE_EXTS = ['.jpg', '.jpeg', '.png', '.webp', '.bmp']

def find_samples(samples_dir):
    """
    Discover (.pg, target_image) pairs from a samples directory.
    Returns list of dicts with 'id', 'pg', 'target'.
    """
    samples = []
    seen_ids = set()
    base = Path(samples_dir)

    # Pattern 1: subdirectory per sample
    for subdir in sorted(base.iterdir()):
        if not subdir.is_dir():
            continue
        pg_files = list(subdir.glob('*.pg'))
        if not pg_files:
            continue
        pg = pg_files[0]
        target = None
        for ext in IMAGE_EXTS:
            for name in ['target', 'original', 'source', pg.stem]:
                candidate = subdir / f"{name}{ext}"
                if candidate.exists():
                    target = candidate
                    break
            if target:
                break
        # Also try any image in the subdir
        if not target:
            for ext in IMAGE_EXTS:
                imgs = list(subdir.glob(f'*{ext}'))
                if imgs:
                    target = imgs[0]
                    break
        if target:
            sid = subdir.name
            if sid not in seen_ids:
                seen_ids.add(sid)
                samples.append({'id': sid, 'pg': str(pg), 'target': str(target)})

    # Pattern 2: flat layout — foo.pg + foo.jpg
    pg_files = sorted(base.glob('*.pg'))
    for pg in pg_files:
        target = None
        for ext in IMAGE_EXTS:
            candidate = pg.with_suffix(ext)
            if candidate.exists():
                target = candidate
                break
        if target and pg.stem not in seen_ids:
            seen_ids.add(pg.stem)
            samples.append({'id': pg.stem, 'pg': str(pg), 'target': str(target)})

    return samples

# ── Step wrappers ─────────────────────────────────────────────────────────────

HERE = Path(__file__).parent

def run_step(script_name, args_list, timeout=300):
    """Run a pipeline script as a subprocess."""
    script = HERE / script_name
    cmd = [sys.executable, str(script)] + args_list
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, '', 'Timeout'
    except Exception as e:
        return False, '', str(e)

def extract_features_for_sample(sample, features_dir):
    """Run extract_features.py for one sample's target image."""
    feat_path = Path(features_dir) / f"{sample['id']}_features.json"
    if feat_path.exists():
        return True, str(feat_path)

    ok, out, err = run_step('extract_features.py', [sample['target'], '--json'])
    if ok:
        # Write JSON output to file
        feat_path.parent.mkdir(parents=True, exist_ok=True)
        feat_path.write_text(out)
        return True, str(feat_path)
    return False, err

def sweep_sample(sample, sweep_dir, compiler=None):
    """Run sweep_compile.py for one sample."""
    out_dir = Path(sweep_dir) / sample['id']
    manifest = out_dir / f"{sample['id']}_manifest.json"
    if manifest.exists():
        return True, str(manifest)

    args = [sample['pg'], '--output-dir', str(out_dir), '--sample-id', sample['id']]
    if compiler:
        args += ['--compiler', compiler]
    ok, out, err = run_step('sweep_compile.py', args, timeout=600)
    if manifest.exists():
        return True, str(manifest)
    return False, err

def score_sample(sample, manifest_path, scores_dir, wait_ms=500):
    """Run score_renders.py for one sample."""
    out_csv = Path(scores_dir) / f"{sample['id']}_scores.csv"
    if out_csv.exists():
        return True, str(out_csv)

    args = [
        '--manifest', manifest_path,
        '--target', sample['target'],
        '--output', str(out_csv),
        '--wait-ms', str(wait_ms),
    ]
    ok, out, err = run_step('score_renders.py', args, timeout=7200)
    if out_csv.exists():
        return True, str(out_csv)
    return False, err

# ── Policy network training ───────────────────────────────────────────────────

def train_policy_network(training_csv, output_dir):
    """
    Train per-parameter gradient boosted regressors on the assembled dataset.
    Saves models + evaluation report.
    """
    try:
        import pandas as pd
        import numpy as np
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.model_selection import cross_val_score
        from sklearn.preprocessing import StandardScaler
        import pickle
    except ImportError as e:
        print(f"[Error] Missing dependency: {e}")
        print("  pip install pandas scikit-learn --break-system-packages")
        return False

    print(f"\n[PIGMENT v5] Training policy network from {training_csv}")
    df = pd.read_csv(training_csv)
    print(f"             {len(df)} training samples loaded")

    if len(df) < 10:
        print("[Error] Need at least 10 samples to train.", file=sys.stderr)
        return False

    from extract_features import FEATURE_NAMES
    from sweep_compile import PARAM_KEYS

    feat_cols = [f'feat_{fn}' for fn in FEATURE_NAMES]
    target_cols = [f'opt_{pk}' for pk in PARAM_KEYS]

    # Drop rows with missing data
    df = df.dropna(subset=feat_cols + target_cols)
    print(f"             {len(df)} rows after dropping NaN")

    X = df[feat_cols].values.astype(np.float32)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    models = {}
    report = {'n_samples': len(df), 'feature_names': FEATURE_NAMES, 'param_names': PARAM_KEYS, 'models': {}}

    print("\n  Training per-parameter regressors:")
    for pk, col in zip(PARAM_KEYS, target_cols):
        y = df[col].values.astype(np.float32)

        model = GradientBoostingRegressor(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            min_samples_leaf=3,
            random_state=42,
        )
        # 5-fold cross-validation
        cv_scores = cross_val_score(model, X_scaled, y, cv=min(5, len(df)//2),
                                    scoring='r2', n_jobs=-1)
        model.fit(X_scaled, y)
        models[pk] = model

        # Feature importances
        importances = dict(zip(FEATURE_NAMES, model.feature_importances_))
        top3 = sorted(importances.items(), key=lambda x: -x[1])[:3]
        top3_str = ', '.join(f"{k}({v:.3f})" for k,v in top3)

        report['models'][pk] = {
            'cv_r2_mean': float(cv_scores.mean()),
            'cv_r2_std': float(cv_scores.std()),
            'top_features': top3_str,
        }

        r2_bar = '█' * max(0, int(cv_scores.mean() * 20))
        print(f"  {pk:<28} R²={cv_scores.mean():+.3f}±{cv_scores.std():.3f}  {r2_bar}")
        print(f"    top features: {top3_str}")

    # Save artifacts
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    model_path = out / 'pigment_policy.pkl'
    with open(model_path, 'wb') as f:
        pickle.dump({'models': models, 'scaler': scaler,
                     'feature_names': FEATURE_NAMES, 'param_names': PARAM_KEYS}, f)

    report_path = out / 'training_report.json'
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\n[PIGMENT v5] ✓ Policy network saved → {model_path}")
    print(f"             Report → {report_path}")
    print(f"\n  Usage: python optimize.py --model {model_path} --image target.jpg painting.pg")
    return True

# ── Main orchestrator ─────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description='PIGMENT v5 — Full Pipeline Orchestrator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    ap.add_argument('--samples-dir', '-s', help='Directory containing .pg + target image pairs')
    ap.add_argument('--output-dir', '-o', default='./pipeline_out', help='Pipeline output directory')
    ap.add_argument('--workers', type=int, default=4, help='Parallel sweep workers (default: 4)')
    ap.add_argument('--wait-ms', type=int, default=500, help='Browser wait ms per render')
    ap.add_argument('--compiler', help='Path to pigment.py')
    ap.add_argument('--resume', action='store_true', help='Skip samples that already have scores')
    ap.add_argument('--train-only', action='store_true', help='Skip data collection, just train the model')
    ap.add_argument('--features-only', action='store_true', help='Only run feature extraction')
    ap.add_argument('--sweep-only', action='store_true', help='Only run parameter sweeps')
    ap.add_argument('--score-only', action='store_true', help='Only run scoring')
    ap.add_argument('--max-samples', type=int, default=None, help='Limit number of samples (for testing)')
    args = ap.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    features_dir = out / 'features'
    sweep_dir = out / 'sweeps'
    scores_dir = out / 'scores'
    models_dir = out / 'models'
    training_csv = out / 'training_dataset.csv'

    for d in [features_dir, sweep_dir, scores_dir, models_dir]:
        d.mkdir(exist_ok=True)

    # ── Train only ──
    if args.train_only:
        if not training_csv.exists():
            print(f"[Error] No training dataset found at {training_csv}", file=sys.stderr)
            print("        Run the full pipeline first.", file=sys.stderr)
            sys.exit(1)
        train_policy_network(str(training_csv), str(models_dir))
        return

    # ── Discover samples ──
    if not args.samples_dir:
        ap.print_help()
        sys.exit(0)

    samples = find_samples(args.samples_dir)
    if not samples:
        print(f"[Error] No (.pg, image) pairs found in {args.samples_dir}", file=sys.stderr)
        sys.exit(1)

    if args.max_samples:
        samples = samples[:args.max_samples]

    print(f"\n[PIGMENT v5 Pipeline]")
    print(f"  Samples found:  {len(samples)}")
    print(f"  Output dir:     {out}")
    print(f"  Workers:        {args.workers}")
    print(f"  Combos/sample:  216")
    print(f"  Est. renders:   {len(samples) * 216:,}")
    print(f"  Est. time:      ~{len(samples) * 216 * 0.3 / args.workers / 3600:.1f} hours")
    print()

    t_start = time.time()

    # ── Step 1: Feature extraction (fast, sequential) ──
    if not args.score_only and not args.sweep_only:
        print("── Step 1: Feature Extraction ──")
        feat_results = {}
        for i, sample in enumerate(samples):
            ok, feat_path = extract_features_for_sample(sample, str(features_dir))
            if ok:
                feat_results[sample['id']] = feat_path
                print(f"  [{i+1}/{len(samples)}] {sample['id']} ✓")
            else:
                print(f"  [{i+1}/{len(samples)}] {sample['id']} ✗ {feat_path[:60]}")
        print(f"\n  ✓ {len(feat_results)}/{len(samples)} feature vectors extracted\n")

        if args.features_only:
            return

    # ── Step 2: Parameter sweep (parallel) ──
    if not args.score_only:
        print("── Step 2: Parameter Sweep ──")
        print(f"  Sweeping {len(samples)} samples × 216 combos...")

        sweep_results = {}

        def do_sweep(sample):
            return sample['id'], sweep_sample(sample, str(sweep_dir), compiler=args.compiler)

        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            futures = {ex.submit(do_sweep, s): s for s in samples}
            done = 0
            for fut in as_completed(futures):
                done += 1
                sid, (ok, manifest_or_err) = fut.result()
                if ok:
                    sweep_results[sid] = manifest_or_err
                status = '✓' if ok else '✗'
                print(f"  [{done}/{len(samples)}] {sid} {status}")

        print(f"\n  ✓ {len(sweep_results)}/{len(samples)} sweeps complete\n")

        if args.sweep_only:
            return

    # ── Step 3: Scoring ──
    if not args.features_only and not args.sweep_only:
        print("── Step 3: Render Scoring ──")
        print(f"  This is the slow step. Progress saved per sample.\n")

        # Collect manifests
        manifests = {}
        for sample in samples:
            mpath = Path(sweep_dir) / sample['id'] / f"{sample['id']}_manifest.json"
            if mpath.exists():
                manifests[sample['id']] = str(mpath)

        score_results = {}
        for i, sample in enumerate(samples):
            if sample['id'] not in manifests:
                print(f"  [{i+1}/{len(samples)}] {sample['id']} — no manifest, skipping")
                continue
            ok, csv_or_err = score_sample(sample, manifests[sample['id']], str(scores_dir), args.wait_ms)
            if ok:
                score_results[sample['id']] = csv_or_err
            status = '✓' if ok else '✗'
            elapsed = time.time() - t_start
            print(f"  [{i+1}/{len(samples)}] {sample['id']} {status} ({elapsed:.0f}s elapsed)")

        print(f"\n  ✓ {len(score_results)}/{len(samples)} samples scored\n")

    # ── Assemble training dataset ──
    print("── Assembling Training Dataset ──")
    score_csvs = sorted(scores_dir.glob('*_scores.csv'))
    feat_jsons = sorted(features_dir.glob('*_features.json'))

    if not score_csvs:
        print("[WARN] No score CSVs found — cannot assemble dataset")
        return

    # Convert per-sample feature JSONs to a combined CSV
    combined_features_csv = out / 'all_features.csv'
    from extract_features import FEATURE_NAMES
    with open(combined_features_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['image_path'] + FEATURE_NAMES)
        writer.writeheader()
        for fj in feat_jsons:
            sid = fj.stem.replace('_features', '')
            feats = json.loads(fj.read_text())
            feats['image_path'] = sid
            writer.writerow(feats)

    # Build training dataset
    from score_renders import build_training_dataset
    build_training_dataset(
        [str(s) for s in score_csvs],
        str(combined_features_csv),
        str(training_csv),
    )

    # ── Train policy network ──
    print("\n── Training Policy Network ──")
    train_policy_network(str(training_csv), str(models_dir))

    total_time = time.time() - t_start
    print(f"\n[PIGMENT v5] ✓ Pipeline complete in {total_time/3600:.2f} hours")
    print(f"             Model ready: {models_dir / 'pigment_policy.pkl'}")

if __name__ == '__main__':
    main()
