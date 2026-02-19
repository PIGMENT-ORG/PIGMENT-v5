#!/usr/bin/env python3
"""
PIGMENT AI Server with Dual Training (Evolved + Diff)
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from PIL import Image
import numpy as np
import pickle
import json
import os
import glob
from datetime import datetime

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Load trained AI model if exists
model = None
scaler = None
feature_names = None

model_path = os.path.join(os.path.dirname(__file__), '..', 'models', 'ultimate_pigment_ai.pkl')
if os.path.exists(model_path):
    try:
        with open(model_path, 'rb') as f:
            model_data = pickle.load(f)
        model = model_data['model']
        scaler = model_data['scaler']
        feature_names = model_data['feature_names']
        print("✅ AI model loaded")
    except:
        print("⚠️ Could not load model")
else:
    print("⚠️ No model found, running in training mode")

# Ensure training directory exists
os.makedirs('training_data', exist_ok=True)

def extract_image_features(image_path):
    """Extract features from image"""
    img = Image.open(image_path).convert('RGB').resize((200, 300))
    img_array = np.array(img)
    
    return {
        'mean_r': float(np.mean(img_array[:,:,0])),
        'mean_g': float(np.mean(img_array[:,:,1])),
        'mean_b': float(np.mean(img_array[:,:,2])),
        'brightness_mean': float(np.mean(img_array)),
        'brightness_std': float(np.std(img_array))
    }

@app.route('/predict', methods=['POST', 'OPTIONS'])
def predict():
    """Predict optimal parameters from image"""
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image provided'}), 400
        
        image_file = request.files['image']
        image_path = '/tmp/temp_image.jpg'
        image_file.save(image_path)
        
        # Extract features
        img_features = extract_image_features(image_path)
        
        # Get RL state
        rl_state = request.form.get('rl_state', '{}')
        try:
            rl_state = json.loads(rl_state)
        except:
            rl_state = {}
        
        # Default RL state
        default_rl = {
            'fitness': float(rl_state.get('fitness', 70)),
            'density': float(rl_state.get('density', 0.5)),
            'plateau': rl_state.get('plateau', 'moving'),
            'polyRatio': float(rl_state.get('polyRatio', 0.7))
        }
        
        # Default parameters (if no model)
        result = {
            'operator': 'scale',
            'confidence': 0.5,
            'suggested_params': {
                'craquelure.density': 0.2,
                'sss.radius': 0.3,
                'sfumato.kernel': 0.4,
                'illumination.weight': 0.7,
                'age_shift.intensity': 0.4,
                'color_temp.offset': 0.5
            }
        }
        
        # Clean up
        os.remove(image_path)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/dual-train', methods=['POST'])
def dual_train():
    """Receive BOTH evolved and diff images for training"""
    try:
        evolved_file = request.files.get('evolved')
        diff_file = request.files.get('diff')
        
        if not evolved_file or not diff_file:
            return jsonify({'error': 'Both evolved and diff images required'}), 400
        
        # Load and process evolved image
        evolved_img = Image.open(evolved_file.stream).convert('RGB').resize((200, 300))
        evolved_array = np.array(evolved_img)
        
        # Load and process diff image
        diff_img = Image.open(diff_file.stream).convert('RGB').resize((200, 300))
        diff_array = np.array(diff_img)
        
        # Extract features from BOTH images
        features = []
        
        # Features from evolved (what's there)
        features.extend([
            float(np.mean(evolved_array[:,:,0])),
            float(np.mean(evolved_array[:,:,1])),
            float(np.mean(evolved_array[:,:,2])),
            float(np.std(evolved_array)),
            float(np.mean(evolved_array)),
        ])
        
        # Features from diff (what's wrong)
        features.extend([
            float(np.mean(diff_array[:,:,0])),
            float(np.max(diff_array[:,:,0])),
            float(np.std(diff_array[:,:,0])),
            float(len(np.where(diff_array[:,:,0] > 200)[0]) / 1000),
        ])
        
        # Get parameters
        params = request.form.get('params', '{}')
        fitness = request.form.get('fitness', '0')
        
        if params:
            params = json.loads(params)
        
        # Save data
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        evolved_path = f'training_data/evolved_{timestamp}.png'
        evolved_img.save(evolved_path)
        
        diff_path = f'training_data/diff_{timestamp}.png'
        diff_img.save(diff_path)
        
        with open(f'training_data/metadata_{timestamp}.json', 'w') as f:
            json.dump({
                'features': features,
                'params': params,
                'fitness': float(fitness) if fitness else 0,
                'timestamp': timestamp
            }, f, indent=2)
        
        return jsonify({
            'status': 'success',
            'message': 'Training data saved',
            'sample_id': timestamp
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/training-stats', methods=['GET'])
def training_stats():
    """Get statistics about collected training data"""
    try:
        training_files = glob.glob('training_data/*.json')
        evolved_files = glob.glob('training_data/evolved_*.png')
        diff_files = glob.glob('training_data/diff_*.png')
        
        return jsonify({
            'total_samples': len(training_files),
            'evolved_images': len(evolved_files),
            'diff_images': len(diff_files)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'model': 'loaded' if model else 'not loaded',
        'training_samples': len(glob.glob('training_data/*.json'))
    })

if __name__ == '__main__':
    print("🚀 Starting PIGMENT AI Server...")
    print(f"   Training directory: {os.path.abspath('training_data')}")
    print("   Endpoints: /predict, /dual-train, /training-stats, /health")
    app.run(host='0.0.0.0', port=5000, debug=True)
