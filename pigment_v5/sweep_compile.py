#!/usr/bin/env python3
"""
PIGMENT v5 Pipeline — Step 2: Parameter Sweep Compiler
Compiles a .pg file with a grid of parameter combinations.
"""

import argparse
import sys
import os
import json
import itertools
import subprocess
from pathlib import Path

# Parameter grid (216 combinations)
PARAM_GRID = {
    'craquelure.density':   [0.2, 0.6, 1.2],
    'sss.radius':           [0.3, 0.7, 1.4],
    'sfumato.kernel':       [0.4, 0.8, 1.6],
    'illumination.weight':  [0.7, 1.3],
    'age_shift.intensity':  [0.4, 1.2],
    'color_temp.offset':    [-0.4, 0.5]
}

def compile_with_params(pg_path, params, output_path, compiler='pigment.py'):
    """Compile .pg with specific parameters"""
    cmd = [compiler, pg_path, '-o', output_path]
    for k, v in params.items():
        cmd.extend(['--param', f'{k}={v}'])
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.returncode == 0, result.stderr

def main():
    parser = argparse.ArgumentParser(description='PIGMENT v5 Parameter Sweep')
    parser.add_argument('pg_file', help='.pg source file')
    parser.add_argument('--output-dir', '-d', required=True, help='Output directory')
    parser.add_argument('--sample-id', help='Sample ID prefix')
    parser.add_argument('--compiler', default='pigment.py', help='Compiler path')
    
    args = parser.parse_args()
    
    # Create output directory
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate all parameter combinations
    keys = list(PARAM_GRID.keys())
    combos = list(itertools.product(*PARAM_GRID.values()))
    
    print(f"[PIGMENT Sweep] {args.pg_file} → {args.output_dir}")
    print(f"               {len(combos)} combinations (#0–#{len(combos)-1})")
    
    sample_id = args.sample_id or Path(args.pg_file).stem
    manifest = {
        'sample_id': sample_id,
        'source': str(args.pg_file),
        'compiler': args.compiler,
        'renders': []
    }
    
    # Compile each combination
    for i, combo in enumerate(combos):
        params = dict(zip(keys, combo))
        combo_id = f"{sample_id}_c{i:03d}"
        output_html = out_dir / f"{combo_id}.html"
        
        # Create param string for display
        param_str = '_'.join(f"{k.split('.')[-1]}{v:.2f}" for k, v in params.items())
        
        ok, error = compile_with_params(args.pg_file, params, str(output_html), args.compiler)
        
        manifest['renders'].append({
            'global_idx': i,
            'combo_id': f"{sample_id}_{param_str}",
            'params': params,
            'html_path': str(output_html),
            'compiled': ok
        })
        
        if (i+1) % 20 == 0 or i+1 == len(combos):
            print(f"  Progress: {i+1}/{len(combos)} — ✓{sum(1 for r in manifest['renders'] if r['compiled'])} ✗{sum(1 for r in manifest['renders'] if not r['compiled'])}")
    
    # Save manifest
    manifest_path = out_dir / f"{sample_id}_manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\n[PIGMENT Sweep] ✓ Complete")
    print(f"               {sum(1 for r in manifest['renders'] if r['compiled'])}/{len(combos)} compiled successfully")
    print(f"               Manifest → {manifest_path}")

if __name__ == '__main__':
    main()
