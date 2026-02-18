#!/usr/bin/env python3
"""
PIGMENT v5 — Compiler Optimizer
Uses the trained policy network to predict optimal rendering parameters
for a given target image, then compiles the .pg file with those parameters.

This closes the loop: Evolution discovers → Language describes → Compiler optimizes.

Usage:
    python optimize.py --model pipeline_out/models/pigment_policy.pkl \\
                       --image target.jpg \\
                       painting.pg

    python optimize.py --model model.pkl --image target.jpg painting.pg -o output.html
    python optimize.py --model model.pkl --image target.jpg --explain painting.pg
    python optimize.py --model model.pkl --image target.jpg --params-only
"""
import argparse, sys, os, json, subprocess
from pathlib import Path

def load_model(model_path):
    try:
        import pickle
        with open(model_path, 'rb') as f:
            return pickle.load(f)
    except ImportError:
        print("[Error] pickle unavailable (should never happen)", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"[Error] Model not found: {model_path}", file=sys.stderr)
        sys.exit(1)

def predict_params(model_bundle, image_path):
    """
    Run the policy network on an image and return predicted optimal parameters.
    Returns dict of param_key → predicted_value.
    """
    import numpy as np
    # Import feature extractor
    here = Path(__file__).parent
    sys.path.insert(0, str(here))
    from extract_features import extract_features, FEATURE_NAMES

    features = extract_features(image_path)
    X = np.array([[features[fn] for fn in FEATURE_NAMES]], dtype=np.float32)
    X_scaled = model_bundle['scaler'].transform(X)

    predictions = {}
    for param_name in model_bundle['param_names']:
        model = model_bundle['models'][param_name]
        pred = float(model.predict(X_scaled)[0])
        predictions[param_name] = pred

    return features, predictions

def format_params_for_compiler(predictions):
    """Return list of --param KEY=VALUE strings."""
    return [f"--param {k}={v:.4f}" for k, v in predictions.items()]

def compile_with_params(pg_path, predictions, output_html=None, compiler=None):
    """Invoke pigment.py with predicted parameters."""
    here = Path(__file__).parent
    compiler = compiler or here / 'pigment.py'

    out = output_html or (Path(pg_path).stem + '_optimized.html')
    cmd = [sys.executable, str(compiler), pg_path, '-o', out]
    for k, v in predictions.items():
        cmd += ['--param', f'{k}={v:.4f}']

    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0, out, result.stderr

def explain_predictions(features, predictions, model_bundle):
    """Print human-readable explanation of why each parameter was chosen."""
    import numpy as np
    feature_names = model_bundle['feature_names']
    print("\n  Parameter Predictions & Reasoning:")
    print("  " + "─" * 60)

    param_explanations = {
        'craquelure.density': ('Image complexity (entropy)', 'high entropy → more cracks'),
        'sss.radius':         ('Skin presence (face_confidence)', 'faces benefit from SSS'),
        'sfumato.kernel':     ('Edge density', 'soft edges → wider sfumato'),
        'illumination.weight':('Contrast', 'high contrast → dramatic lighting'),
        'age_shift.intensity':('Color temperature', 'warm images age differently'),
        'color_temp.offset':  ('Color temperature', 'match target warmth'),
    }

    for pk in model_bundle['param_names']:
        val = predictions[pk]
        model = model_bundle['models'][pk]
        feat_imp = dict(zip(feature_names, model.feature_importances_))
        top_feat = max(feat_imp, key=feat_imp.get)
        top_imp = feat_imp[top_feat]
        top_val = features.get(top_feat, 0)

        desc, logic = param_explanations.get(pk, (top_feat, ''))
        print(f"\n  {pk}")
        print(f"    Predicted: {val:.4f}")
        print(f"    Key feature: {top_feat} = {top_val:.4f} (importance: {top_imp:.3f})")
        print(f"    Logic: {logic}")

    print()

def main():
    ap = argparse.ArgumentParser(
        description='PIGMENT v5 — ML-Powered Compiler Optimizer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    ap.add_argument('pg', nargs='?', help='.pg source file to compile')
    ap.add_argument('--model', '-m', required=True, help='Path to trained policy model (.pkl)')
    ap.add_argument('--image', '-i', required=True, help='Target image for parameter prediction')
    ap.add_argument('--output', '-o', help='Output HTML path')
    ap.add_argument('--compiler', help='Path to pigment.py')
    ap.add_argument('--explain', action='store_true', help='Explain why each parameter was chosen')
    ap.add_argument('--params-only', action='store_true', help='Print predicted params without compiling')
    args = ap.parse_args()

    print(f"\n[PIGMENT v5 Optimizer]")
    print(f"  Model:  {args.model}")
    print(f"  Image:  {args.image}")
    if args.pg:
        print(f"  Source: {args.pg}")
    print()

    # Load model
    bundle = load_model(args.model)
    print(f"  ✓ Model loaded ({len(bundle['param_names'])} parameters, {len(bundle['feature_names'])} features)")

    # Predict
    print(f"  Extracting image features...")
    features, predictions = predict_params(bundle, args.image)

    print(f"  ✓ Parameters predicted:")
    for k, v in predictions.items():
        print(f"      {k:<28} → {v:.4f}")

    if args.explain:
        explain_predictions(features, predictions, bundle)

    if args.params_only:
        print("\n  Compiler flags:")
        for flag in format_params_for_compiler(predictions):
            print(f"    {flag}")
        return

    if not args.pg:
        print("\n  [Note] No .pg file specified — use --params-only or provide a .pg file")
        return

    if not os.path.exists(args.pg):
        print(f"[Error] .pg file not found: {args.pg}", file=sys.stderr)
        sys.exit(1)

    print(f"\n  Compiling with optimized parameters...")
    ok, out_path, err = compile_with_params(
        pg_path=args.pg,
        predictions=predictions,
        output_html=args.output,
        compiler=args.compiler
    )

    if ok:
        print(f"  ✓ Compiled → {out_path}")
        print(f"\n[PIGMENT v5] Loop complete: image → features → policy → parameters → shader")
    else:
        print(f"  ✗ Compilation failed:\n{err}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
