#!/usr/bin/env python3
"""
PIGMENT AI Server with Dual Training (Evolved + Diff)
Complete working version
"""

import os
import sys
import json
import pickle
import glob
import numpy as np
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from PIL import Image

app = Flask(__name__)
CORS(app)

# Model path
MODEL_PATH = os.path.join(os.path.dirname(__file__), '..', 'models', 'ultimate_pigment_ai.pkl')
model = None
scaler = None
feature_names = ['fitness', 'density', 'is_stuck', 'polyRatio',
                 'mean_r', 'mean_g', 'mean_b', 'brightness_mean', 'brightness_std']

# Load model if exists
if os.path.exists(MODEL_PATH):
    try:
        with open(MODEL_PATH, 'rb') as f:
            model_data = pickle.load(f)
        model = model_data.get('model')
        scaler = model_data.get('scaler')
        print(f"✅ Model loaded from {MODEL_PATH}")
    except Exception as e:
        print(f"⚠️ Error loading model: {e}")
else:
    print(f"⚠️ No model found at {MODEL_PATH}")

# Ensure training directory exists
os.makedirs('training_data', exist_ok=True)

def extract_image_features(image_path):
    """Extract features from image"""
    try:
        img = Image.open(image_path).convert('RGB').resize((200, 300))
        img_array = np.array(img)
        
        return {
            'mean_r': float(np.mean(img_array[:,:,0])),
            'mean_g': float(np.mean(img_array[:,:,1])),
            'mean_b': float(np.mean(img_array[:,:,2])),
            'brightness_mean': float(np.mean(img_array)),
            'brightness_std': float(np.std(img_array))
        }
    except Exception as e:
        print(f"Error extracting features: {e}")
        return None

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    training_files = glob.glob('training_data/*.json')
    return jsonify({
        'status': 'healthy',
        'model': 'loaded' if model else 'not loaded',
        'training_samples': len(training_files),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/predict', methods=['POST', 'OPTIONS'])
def predict():
    """Predict optimal parameters from image"""
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        if 'image' not in request.files:
            return jsonify({'error': 'No image provided'}), 400
        
        image_file = request.files['image']
        temp_path = '/tmp/temp_image.jpg'
        image_file.save(temp_path)
        
        # Extract features
        img_features = extract_image_features(temp_path)
        if not img_features:
            return jsonify({'error': 'Failed to extract image features'}), 400
        
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
            'plateau': 1.0 if rl_state.get('plateau') == 'stuck' else 0.0,
            'polyRatio': float(rl_state.get('polyRatio', 0.7))
        }
        
        # Default result (used if no model)
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
        
        # Use model if available
        if model and scaler:
            features = [
                default_rl['fitness'],
                default_rl['density'],
                default_rl['plateau'],
                default_rl['polyRatio'],
                img_features['mean_r']/255,
                img_features['mean_g']/255,
                img_features['mean_b']/255,
                img_features['brightness_mean']/255,
                img_features['brightness_std']/255,
            ]
            
            features_scaled = scaler.transform([features])
            prediction = model.predict(features_scaled)[0]
            
            operators = ['scale', 'opacity', 'color', 'rotate', 'translate']
            operator_index = int(prediction * 5) % 5
            
            result = {
                'operator': operators[operator_index],
                'confidence': float(prediction),
                'suggested_params': {
                    'craquelure.density': float(0.2 + prediction * 0.8),
                    'sss.radius': float(0.3 + prediction * 0.9),
                    'sfumato.kernel': float(0.4 + prediction * 1.1),
                    'illumination.weight': float(0.7 + prediction * 0.5),
                    'age_shift.intensity': float(0.4 + prediction * 0.7),
                    'color_temp.offset': float((prediction - 0.5) * 1.5)
                }
            }
        
        # Clean up
        os.remove(temp_path)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/dual-train', methods=['POST'])
def dual_train():
    """Receive both evolved and diff images for training"""
    try:
        evolved_file = request.files.get('evolved')
        diff_file = request.files.get('diff')
        
        if not evolved_file or not diff_file:
            return jsonify({'error': 'Both evolved and diff images required'}), 400
        
        # Process evolved image
        evolved_img = Image.open(evolved_file.stream).convert('RGB').resize((200, 300))
        evolved_array = np.array(evolved_img)
        
        # Process diff image
        diff_img = Image.open(diff_file.stream).convert('RGB').resize((200, 300))
        diff_array = np.array(diff_img)
        
        # Extract features
        features = [
            float(np.mean(evolved_array[:,:,0])),
            float(np.mean(evolved_array[:,:,1])),
            float(np.mean(evolved_array[:,:,2])),
            float(np.std(evolved_array)),
            float(np.mean(evolved_array)),
            float(np.mean(diff_array[:,:,0])),
            float(np.max(diff_array[:,:,0])),
            float(np.std(diff_array[:,:,0])),
            float(len(np.where(diff_array[:,:,0] > 200)[0]) / 1000),
        ]
        
        # Get params
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
            'diff_images': len(diff_files),
            'last_updated': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Starting PIGMENT AI Server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)