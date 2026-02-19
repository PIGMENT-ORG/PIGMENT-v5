#!/usr/bin/env python3
import os
import sys

# Add pigment_v5 to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'pigment_v5'))

# Import from pigment_v5.server
from pigment_v5.server.ai_server_dual import app

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
