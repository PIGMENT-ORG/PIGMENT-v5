#!/usr/bin/env python3
"""
PIGMENT v5 Pipeline — Step 2: Parameter Sweep Compiler
Compiles a .pg file with a grid of parameter combinations.
Each combination produces one HTML file for headless rendering + scoring.

Usage:
    python sweep_compile.py painting.pg --output-dir /tmp/sweep/
    python sweep_compile.py painting.pg --sample-id 42 --output-dir /tmp/sweep/
    python sweep_compile.py --list-grid        # Print the parameter grid
    python sweep_compile.py painting.pg --dry-run

The parameter grid (216 combinations):
    craquelure.density:    0.2, 0.6, 1.2     (sparse, normal, dense)
    sss.radius:            0.3, 0.7, 1.4     (subtle, normal, strong)
    sfumato.kernel:        0.4, 0.8, 1.6     (sharp, normal, very soft)
    illumination.weight:   0.7, 1.3          (flat, dramatic)
    age_shift.intensity:   0.4, 1.2          (fresh, aged)
    color_temp.offset:    -0.4, 0.5          (cool, warm)
"""
import argparse, sys, os, json, itertools, subprocess
from pathlib import Path

# ── Parameter grid ──────────────────────────────────────────────────────────

PARAM_GRID = {
    'craquelure.density':   [0.2, 0.6, 1.2],
    'sss.radius':           [0.3, 0.7, 1.4],
    'sfumato.kernel':       [0.4, 0.8, 1.6],
    'illumination.weight':  [0.7, 1.3],
    'age_shift.intensity':  [0.4, 1.2],
    'color_temp.offset':    [-0.4, 0.5],
}

PARAM_KEYS = list(PARAM_GRID.keys())

def build_combos():
    """Return list of dicts, each a unique parameter combination."""
    values = [PARAM_GRID[k] for k in PARAM_KEYS]
    combos = []
    for combo in itertools.product(*values):
        combos.append(dict(zip(PARAM_KEYS, combo)))
    return combos

COMBOS = build_combos()

def combo_id(combo):
    """Short deterministic ID for a parameter combination."""
    parts = []
    for k in PARAM_KEYS:
        short = k.split('.')[0][:4]
        parts.append(f"{short}{combo[k]:.2f}")
    return '_'.join(parts)

def combo_index(combo):
    """Index of a combo in COMBOS list."""
    for i, c in enumerate(COMBOS):
        if c == combo:
            return i
    return -1

# ── Compiler interface ───────────────────────────────────────────────────────

def find_compiler():
    """Locate pigment.py relative to this script."""
    here = Path(__file__).parent
    candidates = [here / 'pigment.py', here.parent / 'pigment.py', Path('pigment.py')]
    for p in candidates:
        if p.exists():
            return str(p)
    return None

def compile_one(pg_path, combo, output_html, compiler=None):
    """
    Compile pg_path with the given parameter combo to output_html.
    Returns (success, stderr_text).
    """
    compiler = compiler or find_compiler()
    if not compiler:
        return False, "Cannot find pigment.py"

    cmd = [sys.executable, compiler, pg_path, '-o', output_html]
    for k, v in combo.items():
        cmd += ['--param', f'{k}={v}']

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.returncode == 0, result.stderr
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)

# ── Main sweep logic ─────────────────────────────────────────────────────────

def sweep(pg_path, output_dir, sample_id=None, dry_run=False, compiler=None,
          start_combo=0, end_combo=None):
    """
    Compile pg_path with all parameter combinations.
    Outputs HTML files + a manifest JSON.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    sid = sample_id or Path(pg_path).stem
    combos_to_run = COMBOS[start_combo:end_combo]
    total = len(combos_to_run)

    print(f"[PIGMENT Sweep] {Path(pg_path).name} → {output_dir}")
    print(f"               {total} combinations (#{start_combo}–#{(end_combo or len(COMBOS))-1})")
    if dry_run:
        print("               DRY RUN — no files will be written")
    print()

    manifest = {
        'sample_id': sid,
        'pg_path': str(Path(pg_path).resolve()),
        'param_keys': PARAM_KEYS,
        'combos': [],
    }

    ok_count = 0
    fail_count = 0

    for i, combo in enumerate(combos_to_run):
        global_idx = start_combo + i
        cid = combo_id(combo)
        html_name = f"{sid}_c{global_idx:03d}.html"
        html_path = str(out / html_name)

        if dry_run:
            print(f"  [dry] combo {global_idx:03d}: {cid}")
            continue

        success, err = compile_one(pg_path, combo, html_path, compiler=compiler)

        if success:
            ok_count += 1
            status = '✓'
        else:
            fail_count += 1
            status = '✗'
            print(f"  [{status}] combo {global_idx:03d}: {err.strip()[:80]}")

        # Always record in manifest (even failures)
        manifest['combos'].append({
            'global_idx': global_idx,
            'combo_id': cid,
            'params': combo,
            'html_path': html_path if success else None,
            'compiled': success,
        })

        # Progress every 20
        if (i + 1) % 20 == 0 or i == total - 1:
            pct = 100 * (i + 1) / total
            print(f"  Progress: {i+1}/{total} ({pct:.0f}%) — ✓{ok_count} ✗{fail_count}")

    manifest_path = out / f"{sid}_manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    print(f"\n[PIGMENT Sweep] ✓ Complete")
    print(f"               {ok_count}/{total} compiled successfully")
    print(f"               Manifest → {manifest_path}")
    return manifest

def main():
    ap = argparse.ArgumentParser(
        description='PIGMENT v5 — Parameter Sweep Compiler',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    ap.add_argument('pg', nargs='?', help='.pg source file')
    ap.add_argument('--output-dir', '-d', default='./sweep_out', help='Output directory for HTML files')
    ap.add_argument('--sample-id', help='Sample ID prefix for output files (default: pg filename stem)')
    ap.add_argument('--compiler', help='Path to pigment.py (auto-detected if omitted)')
    ap.add_argument('--dry-run', action='store_true', help='Print combos without compiling')
    ap.add_argument('--list-grid', action='store_true', help='Print the parameter grid and exit')
    ap.add_argument('--start', type=int, default=0, help='Start at combo index (for resuming)')
    ap.add_argument('--end', type=int, default=None, help='End at combo index (exclusive)')
    ap.add_argument('--single', type=int, metavar='IDX', help='Compile only combo IDX')
    args = ap.parse_args()

    if args.list_grid:
        print(f"\nPIGMENT v5 Parameter Grid — {len(COMBOS)} total combinations")
        print("─" * 60)
        for k, vals in PARAM_GRID.items():
            print(f"  {k:<28} {vals}")
        print()
        print("Sample combos:")
        for i in [0, 1, len(COMBOS)//2, len(COMBOS)-1]:
            c = COMBOS[i]
            print(f"  [{i:03d}] {combo_id(c)}")
        print()
        return

    if not args.pg:
        ap.print_help()
        sys.exit(0)

    if not os.path.exists(args.pg):
        print(f"[Error] File not found: {args.pg}", file=sys.stderr)
        sys.exit(1)

    start = args.start
    end = args.end
    if args.single is not None:
        start = args.single
        end = args.single + 1

    sweep(
        pg_path=args.pg,
        output_dir=args.output_dir,
        sample_id=args.sample_id,
        dry_run=args.dry_run,
        compiler=args.compiler,
        start_combo=start,
        end_combo=end,
    )

if __name__ == '__main__':
    main()
