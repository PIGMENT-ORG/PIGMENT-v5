#!/usr/bin/env python3
"""
PIGMENT v5 Converter - Converts old .pg to v5 zone format
"""

import re
import sys

def rgba_to_hex(rgba_str):
    """Convert rgba(r,g,b,a) to hex color (#rrggbb)"""
    match = re.search(r'rgba\((\d+),(\d+),(\d+)(?:,(\d+))?\)', rgba_str)
    if match:
        r, g, b = match.group(1), match.group(2), match.group(3)
        return f'#{int(r):02x}{int(g):02x}{int(b):02x}'
    return '#ff0000'

def convert_pg_file(input_file, output_file):
    """Convert old .pg to v5 zone format"""
    with open(input_file, 'r') as f:
        content = f.read()
    
    # Extract canvas dimensions
    width_match = re.search(r'width:\s*(\d+)', content)
    height_match = re.search(r'height:\s*(\d+)', content)
    width = width_match.group(1) if width_match else '200'
    height = height_match.group(1) if height_match else '200'
    
    # Extract all polygons
    polygon_pattern = r'poly-(\d+)\s*{\s*points:\s*([^}]+?)\s*color:\s*([^}]+?)\s*}'
    polygons = re.findall(polygon_pattern, content, re.DOTALL)
    
    # Build v5 file
    output = f'''-- PIGMENT Genome v5 (Converted)
-- Source: {input_file}
-- Date: {__import__('datetime').datetime.now().strftime("%Y-%m-%d")}

canvas {{
  width: {width}
  height: {height}
  format: portrait
  ground: canvas
  age: 0yr
  light: upper-left
  title: "Converted Painting"
}}

palette {{
'''

    # Add unique colors to palette
    colors = {}
    for i, (idx, points, color) in enumerate(polygons):
        if 'rgba' in color:
            hex_color = rgba_to_hex(color)
            color_name = f'color_{i}'
            colors[color_name] = hex_color
            output += f'  {color_name}: {hex_color}\n'
    
    output += '}\n\nlayer base {\n'
    
    # Convert each polygon to a zone
    for i, (idx, points, color) in enumerate(polygons):
        points = ' '.join(points.strip().split())
        
        # Extract opacity if present
        opacity = '1.0'
        if 'rgba' in color:
            alpha_match = re.search(r'rgba\([^,]+,[^,]+,[^,]+,([^)]+)\)', color)
            if alpha_match:
                alpha = float(alpha_match.group(1))
                if alpha <= 1.0:
                    opacity = f'{alpha:.3f}'
                else:
                    opacity = f'{alpha/255:.3f}'
        
        color_name = f'color_{i}' if 'rgba' in color else 'black'
        
        output += f'''
  zone poly_{i} {{
    color: palette.{color_name}
    opacity: {opacity}
    points: {points}
  }}
'''
    
    output += '}\n'
    
    with open(output_file, 'w') as f:
        f.write(output)
    
    print(f"✅ Converted {len(polygons)} polygons → {output_file}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python convert_to_v5_zones.py input.pg output.pg")
        sys.exit(1)
    convert_pg_file(sys.argv[1], sys.argv[2])
