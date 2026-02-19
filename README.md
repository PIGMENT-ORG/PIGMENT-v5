# 🎨 PIGMENT v5 - AI-Powered Evolutionary Art System

<div align="center">
  <h3>A language that doesn't compile — it paints.</h3>
  <p>99.27% fitness masterpiece • 50 polygons • 46 colors • 2,875 training samples</p>
</div>

## 📋 Table of Contents
- [Overview](#-overview)
- [Features](#-features)
- [Quick Start](#-quick-start)
- [Architecture](#-architecture)
- [Components](#-components)
- [Usage Guide](#-usage-guide)
- [AI Training](#-ai-training)
- [Deployment](#-deployment)
- [API Reference](#-api-reference)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)

## 🎯 Overview

PIGMENT v5 is an evolutionary art system that uses AI to create stunning visuals. It combines:
- **Evolutionary Algorithms** that mutate and select polygons
- **Dual-Canvas Training** learning from both successes and errors
- **Ultimate AI** predicting optimal parameters from images
- **Supabase Integration** for continuous learning from every evolution

## ✨ Features

### Core Features
- ✅ **Multi-image upload** (up to 5 images simultaneously)
- ✅ **Real-time evolution** with adjustable speed and polygon count
- ✅ **Dual-canvas view** showing evolved image and error map
- ✅ **Genome export** in PIGMENT v5 format
- ✅ **PNG export** of evolved and diff images

### AI Features
- 🤖 **Ultimate AI** - Predicts optimal parameters from any image
- 📊 **Dual Training** - Learns from both evolved and diff images
- ☁️ **Supabase Integration** - Cloud-based training data collection
- 🔄 **Continuous Learning** - AI improves with every evolution

### Technical Features
- 🚀 **WebGL Compiler** - Hardware-accelerated rendering
- 🐳 **Docker Support** - Easy deployment anywhere
- 📦 **Modular Design** - Separate compiler, server, and web components
- 🧪 **Test Suite** - Comprehensive API testing

## 🚀 Quick Start

### 1. Clone and Setup
```bash
git clone https://github.com/yourusername/pigment-v5.git
cd pigment-v5
```

2. Start the AI Server

```bash
# Install dependencies
pip install -r requirements.txt

# Start the server
python server/ai_server_dual.py
```

3. Open the Web Interface

```bash
# Open web/index.html in your browser
# Or serve it with a simple HTTP server
python -m http.server 8000 --directory web/
```

4. Start Evolving!

· Drop an image
· Click Start
· Watch the evolution
· Export your masterpiece!

🏗 Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Web Browser                       │
│  ┌───────────────────────────────────────────────┐  │
│  │           web/index.html (Frontend)           │  │
│  └───────────────────────┬───────────────────────┘  │
└──────────────────────────┼──────────────────────────┘
                           │ HTTP/WebSocket
┌──────────────────────────┼──────────────────────────┐
│           ┌──────────────▼──────────────┐           │
│           │   server/ai_server_dual.py  │           │
│           │        (Flask API)          │           │
│           └──────────────┬──────────────┘           │
│                          │                          │
│      ┌───────────────────┼───────────────────┐     │
│      ▼                   ▼                   ▼     │
│ ┌──────────┐      ┌──────────┐      ┌──────────┐  │
│ │ compiler/│      │  models/ │      │ training │  │
│ │ pigment_ │      │  AI .pkl │      │   _data/ │  │
│ │  v5.py   │      │   files  │      │  images  │  │
│ └──────────┘      └──────────┘      └──────────┘  │
└─────────────────────────────────────────────────────┘
```

📦 Components

/compiler - The PIGMENT Compiler

· pigment_v5.py - Main v5 compiler
· pigment_v5_fixed.py - Enhanced version with better parsing

/server - AI Backend

· ai_server_dual.py - Flask server with dual-training endpoints

/web - Frontend Interface

· index.html - Complete evolutionary painter UI

/models - Trained AI Models

· ultimate_pigment_ai.pkl - Your trained model
· training_report_*.json - Model training reports

/scripts - Utility Scripts

· train_model.py - Retrain AI from collected data
· backup_training.py - Backup training data to/from Supabase

/tests - Test Suite

· test_server.py - Comprehensive API tests

📝 Usage Guide

Basic Evolution

1. Upload Image: Drag & drop or click to choose
2. Configure: Adjust polygon count, speed, size
3. Start: Click Start and watch evolution
4. Export: Save your genome as .pg or PNG

AI Features

1. Get AI Prediction: Click "🤖 Ultimate AI" after uploading
2. Apply Parameters: Use AI suggestions to improve evolution
3. Save Both PNG: Click "📸 Save Both PNG" to capture evolved + diff
4. Export Training: Download collected training data

Advanced Features

· Multi-image: Upload up to 5 images and switch between them
· Hide Evolved: Toggle to compare target and diff
· Refresh Genome: Update the genome display
· Copy to Clipboard: Quick genome copying

🤖 AI Training

Automatic Training

The system automatically collects training data from:

· Every mutation (success/failure)
· Dual-canvas captures (evolved + diff images)
· User interactions

Manual Retraining

```bash
# Retrain the AI model with collected data
python scripts/train_model.py

# Force retrain even with few samples
python scripts/train_model.py --force

# Specify custom data directory
python scripts/train_model.py --data-dir my_training_data
```

Backup Training Data

```bash
# Backup all training data
python scripts/backup_training.py

# List available backups
python scripts/backup_training.py --action list

# Restore from backup
python scripts/backup_training.py --action restore --backup-file backups/training_data_local_20250219.tar.gz

# Cleanup old backups (keep last 7 days)
python scripts/backup_training.py --action cleanup --days 7
```

🚢 Deployment

Docker Deployment

```bash
# Build the Docker image
docker build -t pigment-ai .

# Run with docker-compose
docker-compose up -d

# View logs
docker-compose logs -f
```

Cloud Deployment (Google Cloud Run)

```bash
# Build and deploy to Google Cloud Run
gcloud builds submit --tag gcr.io/your-project/pigment-ai
gcloud run deploy pigment-ai --image gcr.io/your-project/pigment-ai --platform managed
```

Environment Variables

Copy .env.example to .env and configure:

```bash
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_supabase_key
AI_SERVER_PORT=5000
MODEL_PATH=./models/ultimate_pigment_ai.pkl
```

📡 API Reference

Health Check

```http
GET /health
```

Response:

```json
{
  "status": "healthy",
  "model": "loaded",
  "training_samples": 2875
}
```

Predict Parameters

```http
POST /predict
Content-Type: multipart/form-data

- image: file (required)
- rl_state: JSON string (optional)
```

Response:

```json
{
  "operator": "scale",
  "confidence": 0.85,
  "suggested_params": {
    "craquelure.density": 0.2,
    "sss.radius": 0.3,
    "sfumato.kernel": 0.4,
    "illumination.weight": 0.7,
    "age_shift.intensity": 0.4,
    "color_temp.offset": 0.5
  }
}
```

Dual Training

```http
POST /dual-train
Content-Type: multipart/form-data

- evolved: file (required)
- diff: file (required)
- params: JSON string (optional)
- fitness: string (optional)
```

Response:

```json
{
  "status": "success",
  "message": "Training data saved",
  "sample_id": "20250219_113045"
}
```

Training Stats

```http
GET /training-stats
```

Response:

```json
{
  "total_samples": 2875,
  "evolved_images": 2875,
  "diff_images": 2875
}
```

🔧 Troubleshooting

Server Won't Start

```bash
# Check if port is in use
lsof -i :5000

# Kill process using port
kill -9 $(lsof -t -i:5000)

# Check Python version
python --version  # Need 3.8+
```

Model Not Loading

```bash
# Check if model file exists
ls -la models/ultimate_pigment_ai.pkl

# Retrain model if missing
python scripts/train_model.py
```

Web Interface Issues

```bash
# Check browser console (F12) for errors
# Verify AI_SERVER_URL in web/index.html
# Ensure CORS is enabled (it is by default)
```

Training Data Not Saving

```bash
# Check permissions
chmod -R 755 training_data/

# Verify Supabase connection
python -c "from scripts.backup_training import TrainingDataBackup; TrainingDataBackup().backup_supabase_data()"
```

📊 Performance Metrics

Current Achievements

· Best Fitness: 99.27%
· Polygons: 50
· Colors: 46
· Training Samples: 2,875
· Generations: 33,600

Expected Performance

· Cold Start: ~2-3 seconds
· Prediction Time: <100ms
· Training Time: ~30 seconds (2,875 samples)
· Concurrent Users: 5-10 without degradation

🤝 Contributing

1. Fork the repository
2. Create a feature branch (git checkout -b feature/amazing)
3. Commit changes (git commit -m 'Add amazing feature')
4. Push to branch (git push origin feature/amazing)
5. Open a Pull Request

📄 License

MIT License - feel free to use this project for anything!

🙏 Acknowledgments

· The PIGMENT community
· All the evolution algorithms that made this possible
· Your 33,600 generations of evolution!

🏆 Masterpiece Gallery

Your 99.27% fitness masterpiece is saved at:

· data/masterpiece_99.pg - The genome
· web/masterpiece_fixed.html - The rendered artwork

---

<div align="center">
  <p>Made with 🎨 and 🤖 by the PIGMENT community</p>
  <p>⭐ Star us on GitHub if you like it!</p>
</div>
