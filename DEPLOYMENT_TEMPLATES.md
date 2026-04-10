# Templates Deployment Guide for Render

This guide explains the best approaches for deploying the waveform templates directory when running SWEET on Render or other cloud platforms.

## Current Setup

- **Local Development**: Templates are stored in `SWEET_scripts/DATA/processed_templates/`
- **Backend**: Automatically resolves relative paths to workspace root
- **Frontend**: Default path is now `SWEET_scripts/DATA/processed_templates`

## Deployment Options for Render

### Option 1: Include Templates in Repository ✅ **RECOMMENDED for Small/Medium Datasets**

**Best for**: Template libraries < 500 MB

**Pros**:
- Simplest deployment (zero configuration)
- No additional costs
- Fast access (local filesystem)
- Version controlled with code

**Cons**:
- Increases repository size
- Slower git operations
- Free tier has storage limits

**Implementation**:
```bash
# 1. Ensure templates are committed to git
git add SWEET_scripts/DATA/processed_templates/
git commit -m "Add preprocessed waveform templates"
git push

# 2. Deploy to Render
# Templates will be automatically included with the deployment
```

**Status**: Already configured! The backend resolves relative paths automatically.

---

### Option 2: Render Persistent Disk 💾 **RECOMMENDED for Large Datasets**

**Best for**: Template libraries > 500 MB, frequently accessed data

**Pros**:
- Fast local access
- Persistent across deployments
- Can be updated independently
- Up to 1GB free, then $0.25/GB/month

**Cons**:
- Requires manual setup
- One-time upload process
- Additional cost for >1GB

**Implementation**:

#### Step 1: Create Persistent Disk in Render Dashboard
1. Go to your Render dashboard
2. Click "New +" → "Disk"
3. Configure:
   - Name: `sweet-templates`
   - Mount Path: `/opt/render/project/templates`
   - Size: 1-10 GB (based on needs)

#### Step 2: Upload Templates
```bash
# On your local machine, create an archive
cd SWEET_scripts/DATA
tar -czf processed_templates.tar.gz processed_templates/

# Use Render Shell to upload (via their dashboard)
# Or use SCP if SSH access is available
```

#### Step 3: Update render.yaml
```yaml
services:
  - type: web
    name: sweet-web
    env: python
    plan: free
    autoDeploy: true
    buildCommand: pip install -r requirements.txt
    startCommand: python -m uvicorn app:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /health
    disk:
      name: sweet-templates
      mountPath: /opt/render/project/templates
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.9
      - key: TEMPLATES_DIR
        value: /opt/render/project/templates/processed_templates
```

#### Step 4: Update Frontend Default
In `sweet_web_v2.html`, change the default input value:
```html
<input type="text" id="templates-dir" 
       value="/opt/render/project/templates/processed_templates" 
       class="w-full px-3 py-2 border border-gray-300 rounded text-xs">
```

Or use environment variable approach (see Option 5).

---

### Option 3: External Cloud Storage (S3/GCS) ☁️ **RECOMMENDED for Very Large Datasets**

**Best for**: Template libraries > 10 GB, shared across services, infrequent updates

**Pros**:
- Unlimited storage
- Can be shared across deployments
- Cheapest for large datasets (~$0.023/GB/month for S3)
- Can use CDN for faster access

**Cons**:
- Network latency for first access
- Requires credentials management
- More complex setup
- Code modifications needed

**Implementation**:

#### Step 1: Upload to S3/GCS
```bash
# Using AWS CLI
aws s3 sync SWEET_scripts/DATA/processed_templates/ \
    s3://your-bucket/sweet-templates/

# Or using Google Cloud
gsutil -m rsync -r SWEET_scripts/DATA/processed_templates/ \
    gs://your-bucket/sweet-templates/
```

#### Step 2: Modify Backend to Support Cloud Storage
Create `SWEET_scripts/summing/cloud_helpers.py`:
```python
import os
import boto3
from pathlib import Path

def download_templates_if_needed():
    """Download templates from S3 on first run"""
    local_path = Path("/tmp/sweet_templates")
    
    if local_path.exists():
        return str(local_path)
    
    # Download from S3
    s3 = boto3.client('s3')
    bucket = os.getenv('S3_BUCKET', 'your-bucket')
    prefix = 'sweet-templates/'
    
    local_path.mkdir(parents=True, exist_ok=True)
    
    # Download all templates (this runs once per container startup)
    # Implementation details omitted for brevity
    
    return str(local_path)
```

#### Step 3: Update render.yaml
```yaml
envVars:
  - key: AWS_ACCESS_KEY_ID
    sync: false  # Add via Render dashboard
  - key: AWS_SECRET_ACCESS_KEY
    sync: false  # Add via Render dashboard
  - key: S3_BUCKET
    value: your-bucket-name
  - key: USE_CLOUD_TEMPLATES
    value: true
```

---

### Option 4: Git LFS (Large File Storage) 📦

**Best for**: Template libraries 500MB - 5GB, version-controlled data

**Pros**:
- Keeps templates in git with version control
- Doesn't bloat repository
- Automatic deployment with Render
- First 1GB free on GitHub

**Cons**:
- Requires Git LFS setup
- Bandwidth limits on free tier
- Slower than local disk

**Implementation**:
```bash
# Install Git LFS
brew install git-lfs  # macOS
git lfs install

# Track template files
cd /Users/francescoacolosimo/Desktop/SWEET_web
git lfs track "SWEET_scripts/DATA/processed_templates/**/*.npy"
git add .gitattributes
git add SWEET_scripts/DATA/processed_templates/
git commit -m "Add templates with Git LFS"
git push
```

Render automatically handles Git LFS during deployment.

---

### Option 5: Environment Variable Configuration 🔧 **RECOMMENDED for Flexibility**

Make the templates path configurable via environment variable for easy switching between development and production.

#### Update render.yaml:
```yaml
envVars:
  - key: TEMPLATES_DIR
    value: SWEET_scripts/DATA/processed_templates  # Or your chosen path
```

#### Update app.py:
```python
# At the top of app.py
DEFAULT_TEMPLATES_DIR = os.getenv(
    'TEMPLATES_DIR', 
    'SWEET_scripts/DATA/processed_templates'
)

# In the WaveformSummationInput model (models/waveforms.py):
class WaveformSummationInput(BaseModel):
    templates_dir: str = Field(
        default_factory=lambda: os.getenv(
            'TEMPLATES_DIR', 
            'SWEET_scripts/DATA/processed_templates'
        ),
        description="Path to preprocessed templates directory"
    )
```

#### Update Frontend to fetch from API:
Add an endpoint to get default config:
```python
@app.get("/api/config")
async def get_config():
    return {
        "templates_dir": os.getenv('TEMPLATES_DIR', 'SWEET_scripts/DATA/processed_templates')
    }
```

Then update `sweet_web_v2.html`:
```javascript
// On page load, fetch default config
async function loadDefaultConfig() {
    const response = await fetch('/api/config');
    const config = await response.json();
    document.getElementById('templates-dir').value = config.templates_dir;
}
```

---

## Recommendation Summary

| Templates Size | Best Option | Monthly Cost | Setup Complexity |
|---------------|-------------|--------------|------------------|
| < 100 MB | Git Repository | $0 | ⭐ Easy |
| 100-500 MB | Git LFS | $0-5 | ⭐⭐ Medium |
| 500 MB - 5 GB | Render Persistent Disk | $0-1.25 | ⭐⭐ Medium |
| > 5 GB | AWS S3 + Caching | $0.12-1 | ⭐⭐⭐ Complex |

## Current Status

✅ **Already configured for local development**
- Templates path: `SWEET_scripts/DATA/processed_templates`
- **Templates size**: **116 GB** 📊
- Backend resolves relative paths automatically
- Frontend has configurable input field

## Recommended Deployment Strategy (for 116GB dataset)

⚠️ **Important**: Your templates directory is **116 GB**, which is too large for standard git or Render's free tier.

### 🎯 Best Approach: AWS S3 + On-Demand Loading

**Estimated Cost**: ~$2.67/month storage + minimal transfer costs

**Implementation Plan**:

1. **Upload templates to S3** (one-time setup)
2. **Modify backend** to download only needed templates on-demand
3. **Cache** frequently used templates in `/tmp` on Render
4. **Optional**: Create a smaller "essential templates" subset for faster deployment

### Alternative: Subset of Templates for Demo Deployment

For demonstration/testing purposes, you could:
- Select only templates for specific magnitude ranges (e.g., M5.5-M6.5)
- Reduce to single VS30 category (e.g., vs30_300)
- Limit distance bins to common ranges (10-100km)

This could reduce size to ~5-10 GB, making Render Persistent Disk viable.

## Next Steps

1. **For Production Deployment**:
   - Follow Option 3 (S3) implementation in this guide
   - Upload all 116GB to S3 (~$2.67/month)
   - Modify backend to support on-demand template loading

2. **For Quick Demo/Testing**:
   - Create a templates subset using the provided script:
     ```bash
     python SWEET_scripts/summing/create_template_subset.py \
         --output SWEET_scripts/DATA/templates_demo \
         --vs30 vs30_300 \
         --mag-min 5.5 --mag-max 6.5 \
         --dist-min 10 --dist-max 100 \
         --max-per-bin 5
     ```
   - This creates a ~2-5 GB subset suitable for Render Persistent Disk
   - Update frontend to use the subset path
   - Commit and deploy

3. **Choose deployment option** based on your needs (see recommendations above)

3. **For quick deployment on Render** (Option 1):
   - Simply commit templates to git and deploy
   - No additional configuration needed!

4. **For production** (Option 2 or 5):
   - Set up persistent disk or environment variables
   - Update `render.yaml` accordingly

---

## Troubleshooting

### "Templates directory not found" error
- Check the path is correct in the UI
- Verify templates are included in deployment (git status)
- Check Render logs for file system issues

### Slow waveform computation
- Templates may be loading from slow storage
- Consider using Render Persistent Disk for faster access
- Implement caching in the backend

### Out of memory errors
- Reduce number of templates loaded simultaneously
- Use streaming for large template files
- Upgrade Render plan if needed
