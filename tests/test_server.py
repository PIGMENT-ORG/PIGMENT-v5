#!/usr/bin/env python3
"""
PIGMENT v5 - Server Tests
Test suite for the AI server endpoints
"""

import unittest
import requests
import json
import os
import tempfile
from PIL import Image
import numpy as np

BASE_URL = 'http://localhost:5000'

class TestAIServer(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        """Check if server is running"""
        try:
            response = requests.get(f'{BASE_URL}/health', timeout=2)
            cls.server_running = response.status_code == 200
        except:
            cls.server_running = False
        
        if not cls.server_running:
            print("\n⚠️  Warning: AI server not running at", BASE_URL)
            print("   Tests will be skipped. Start server with:")
            print("   python server/ai_server_dual.py\n")
    
    def setUp(self):
        """Create test images before each test"""
        if not self.server_running:
            self.skipTest("Server not running")
        
        # Create a test evolved image
        self.evolved_img = Image.new('RGB', (200, 300), color='red')
        self.evolved_path = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        self.evolved_img.save(self.evolved_path.name)
        
        # Create a test diff image
        self.diff_img = Image.new('RGB', (200, 300), color='blue')
        self.diff_path = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        self.diff_img.save(self.diff_path.name)
    
    def tearDown(self):
        """Clean up test files"""
        if hasattr(self, 'evolved_path'):
            os.unlink(self.evolved_path.name)
        if hasattr(self, 'diff_path'):
            os.unlink(self.diff_path.name)
    
    def test_health_endpoint(self):
        """Test the /health endpoint"""
        response = requests.get(f'{BASE_URL}/health')
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn('status', data)
        self.assertIn('model', data)
        self.assertIn('training_samples', data)
        print("✅ /health endpoint working")
    
    def test_training_stats_endpoint(self):
        """Test the /training-stats endpoint"""
        response = requests.get(f'{BASE_URL}/training-stats')
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn('total_samples', data)
        self.assertIn('evolved_images', data)
        self.assertIn('diff_images', data)
        print("✅ /training-stats endpoint working")
    
    def test_predict_endpoint_no_image(self):
        """Test /predict with no image"""
        response = requests.post(f'{BASE_URL}/predict')
        self.assertEqual(response.status_code, 400)
        print("✅ /predict correctly rejects requests with no image")
    
    def test_predict_endpoint_with_image(self):
        """Test /predict with a valid image"""
        with open(self.evolved_path.name, 'rb') as img:
            files = {'image': img}
            data = {'rl_state': json.dumps({'fitness': 75})}
            
            response = requests.post(f'{BASE_URL}/predict', files=files, data=data)
            self.assertEqual(response.status_code, 200)
            
            result = response.json()
            self.assertIn('operator', result)
            self.assertIn('confidence', result)
            self.assertIn('suggested_params', result)
            print("✅ /predict returns valid predictions")
    
    def test_dual_train_endpoint_missing_files(self):
        """Test /dual-train with missing files"""
        response = requests.post(f'{BASE_URL}/dual-train')
        self.assertEqual(response.status_code, 400)
        print("✅ /dual-train correctly rejects requests with missing files")
    
    def test_dual_train_endpoint_with_files(self):
        """Test /dual-train with both images"""
        with open(self.evolved_path.name, 'rb') as evolved, \
             open(self.diff_path.name, 'rb') as diff:
            
            files = {
                'evolved': evolved,
                'diff': diff
            }
            data = {
                'params': json.dumps({'test': 'params'}),
                'fitness': '85.5'
            }
            
            response = requests.post(f'{BASE_URL}/dual-train', files=files, data=data)
            self.assertEqual(response.status_code, 200)
            
            result = response.json()
            self.assertEqual(result['status'], 'success')
            self.assertIn('sample_id', result)
            print("✅ /dual-train successfully saves training data")
    
    def test_predict_with_rl_state(self):
        """Test /predict with full RL state"""
        with open(self.evolved_path.name, 'rb') as img:
            files = {'image': img}
            rl_state = {
                'fitness': 85.5,
                'density': 0.6,
                'plateau': 'moving',
                'polyRatio': 0.8
            }
            data = {'rl_state': json.dumps(rl_state)}
            
            response = requests.post(f'{BASE_URL}/predict', files=files, data=data)
            self.assertEqual(response.status_code, 200)
            print("✅ /predict handles RL state correctly")
    
    def test_concurrent_requests(self):
        """Test handling of multiple requests"""
        import concurrent.futures
        
        def make_request(i):
            with open(self.evolved_path.name, 'rb') as img:
                files = {'image': img}
                data = {'rl_state': json.dumps({'fitness': 50 + i})}
                return requests.post(f'{BASE_URL}/predict', files=files, data=data)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request, i) for i in range(5)]
            for future in concurrent.futures.as_completed(futures):
                response = future.result()
                self.assertEqual(response.status_code, 200)
        
        print("✅ Server handles concurrent requests")

def run_tests():
    """Run the test suite"""
    print("\n" + "="*50)
    print("🧪 Running PIGMENT AI Server Tests")
    print("="*50)
    
    suite = unittest.TestLoader().loadTestsFromTestCase(TestAIServer)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
