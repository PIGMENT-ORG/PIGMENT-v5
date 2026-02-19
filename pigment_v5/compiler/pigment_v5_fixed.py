#!/usr/bin/env python3
"""
PIGMENT v5 Compiler - Fixed zone parsing
"""

import sys
import re
from pathlib import Path

class PIGMENTv5:
    def __init__(self):
        self.canvas = {'width': 200, 'height': 200, 'title': 'PIGMENT v5'}
        self.palette = {}
        self.layers = []
        self.metadata = {}
        
    def parse(self, content):
        lines = content.split('\n')
        i = 0
        current_layer = None
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip comments
            if line.startswith('--'):
                if '@' in line:
                    self._parse_metadata(line)
                i += 1
                continue
            
            # Parse canvas
            if 'canvas {' in line:
                i = self._parse_canvas(lines, i)
            
            # Parse palette
            elif 'palette {' in line:
                i = self._parse_palette(lines, i)
            
            # Parse layer
            elif 'layer' in line and '{' in line:
                if current_layer:
                    self.layers.append(current_layer)
                layer_name = line.split()[1]
                current_layer = {'name': layer_name, 'zones': []}
                i += 1
            
            # Parse zone inside layer
            elif current_layer and 'zone' in line and '{' in line:
                zone_name = line.split()[1]
                zone = {'name': zone_name, 'points': [], 'color': None, 'opacity': 1.0}
                i += 1
                
                # Parse zone properties
                while i < len(lines) and '}' not in lines[i]:
                    prop_line = lines[i].strip()
                    if 'color:' in prop_line:
                        zone['color'] = prop_line.split(':')[1].strip()
                    elif 'opacity:' in prop_line:
                        zone['opacity'] = float(prop_line.split(':')[1].strip())
                    elif 'points:' in prop_line:
                        points_str = prop_line.replace('points:', '').strip()
                        pairs = points_str.split()
                        for pair in pairs:
                            if ',' in pair:
                                x, y = map(float, pair.split(','))
                                zone['points'].append((x, y))
                    i += 1
                
                current_layer['zones'].append(zone)
                i += 1  # Skip the closing brace
            
            # End of layer
            elif current_layer and '}' in line:
                self.layers.append(current_layer)
                current_layer = None
                i += 1
            
            else:
                i += 1
        
        # Add last layer if any
        if current_layer and current_layer['zones']:
            self.layers.append(current_layer)
            
        return self
    
    def _parse_metadata(self, line):
        match = re.search(r'@(\w+)\s+([\d.]+)', line)
        if match:
            self.metadata[match.group(1)] = match.group(2)
    
    def _parse_canvas(self, lines, start_idx):
        i = start_idx + 1
        while i < len(lines) and '}' not in lines[i]:
            line = lines[i].strip()
            if 'width:' in line:
                self.canvas['width'] = int(line.split(':')[1].strip())
            elif 'height:' in line:
                self.canvas['height'] = int(line.split(':')[1].strip())
            elif 'title:' in line:
                self.canvas['title'] = line.split(':')[1].strip().strip('"')
            i += 1
        return i + 1
    
    def _parse_palette(self, lines, start_idx):
        i = start_idx + 1
        while i < len(lines) and '}' not in lines[i]:
            line = lines[i].strip()
            if ':' in line and '#' in line:
                parts = line.split(':')
                name = parts[0].strip()
                hex_color = parts[1].strip()
                self.palette[name] = hex_color
            i += 1
        return i + 1
    
    def generate_html(self):
        zone_count = sum(len(l['zones']) for l in self.layers)
        html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{self.canvas['title']}</title>
    <style>
        body {{ 
            margin:0; 
            background:#222; 
            display:flex; 
            justify-content:center; 
            align-items:center; 
            min-height:100vh;
            font-family: monospace;
        }}
        .container {{ text-align: center; }}
        canvas {{ 
            border:2px solid #444;
            box-shadow: 0 0 20px rgba(0,0,0,0.5);
        }}
        .info {{
            margin-top: 10px;
            color: #888;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <canvas id="canvas" width="{self.canvas['width']}" height="{self.canvas['height']}"></canvas>
        <div class="info">
            PIGMENT v5 · {len(self.palette)} colors · {zone_count} zones · {self.metadata.get('best_fitness', '')}% fitness
        </div>
    </div>
    <script>
        const canvas = document.getElementById('canvas');
        const ctx = canvas.getContext('2d');
        
        function draw() {{
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.fillStyle = 'white';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
'''
        for layer in self.layers:
            for zone in layer['zones']:
                if len(zone['points']) >= 3:
                    color_ref = zone['color'].replace('palette.', '')
                    hex_color = self.palette.get(color_ref, '#000000')
                    opacity = zone.get('opacity', 1.0)
                    r = int(hex_color[1:3], 16)
                    g = int(hex_color[3:5], 16)
                    b = int(hex_color[5:7], 16)
                    html += f'''
            // Zone {zone['name']}
            ctx.beginPath();'''
                    for j, (x, y) in enumerate(zone['points']):
                        if j == 0:
                            html += f'\n            ctx.moveTo({x}, {y});'
                        else:
                            html += f'\n            ctx.lineTo({x}, {y});'
                    html += f'''
            ctx.closePath();
            ctx.fillStyle = 'rgba({r},{g},{b},{opacity})';
            ctx.fill();
'''
        html += '''
        }
        draw();
    </script>
</body>
</html>'''
        return html
    
    def compile_file(self, input_file, output_file):
        with open(input_file, 'r') as f:
            content = f.read()
        self.parse(content)
        html = self.generate_html()
        with open(output_file, 'w') as f:
            f.write(html)
        zone_count = sum(len(l['zones']) for l in self.layers)
        print(f"✅ Compiled {input_file} → {output_file}")
        print(f"   {len(self.palette)} colors, {zone_count} zones")
        print(f"   Fitness: {self.metadata.get('best_fitness', 'N/A')}%")
        return html

def main():
    if len(sys.argv) < 3:
        print("PIGMENT v5 Compiler")
        print("Usage: python pigment_v5.py input.pg output.html")
        sys.exit(1)
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    compiler = PIGMENTv5()
    compiler.compile_file(input_file, output_file)

if __name__ == '__main__':
    main()
