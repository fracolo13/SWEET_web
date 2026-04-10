# Quick Start: S3 Templates Setup

## What You Need

✅ AWS account created  
⬜ S3 bucket created  
⬜ IAM credentials obtained  
⬜ Templates uploaded to S3  
⬜ Environment variables configured  
⬜ Deployed to Render  

## Step-by-Step Commands

### 1. Install AWS CLI
```bash
brew install awscli        # macOS
# or: pip install awscli
```

### 2. Configure AWS Credentials
```bash
aws configure
```
You'll be prompted for:
- **Access Key ID**: Get from AWS IAM Console
- **Secret Access Key**: Get from AWS IAM Console  
- **Region**: Use `us-east-1` (or closest to you)
- **Output format**: `json`

### 3. Create S3 Bucket
```bash
# Already created! Your bucket:
aws s3 ls s3://sweet-waveform-templates-917675236412-eu-north-1-an
```

### 4. Upload Templates (Takes Several Hours for 116GB)
```bash
cd /Users/francescoacolosimo/Desktop/SWEET_web

# Upload with cost-optimized storage class
aws s3 sync SWEET_scripts/DATA/processed_templates/ \
    s3://sweet-waveform-templates-917675236412-eu-north-1-an/processed_templates/ \
    --storage-class STANDARD_IA \
    --region eu-north-1

# Monitor progress in another terminal
watch -n 30 'aws s3 ls s3://sweet-waveform-templates-917675236412-eu-north-1-an/processed_templates/ --recursive --summarize --human-readable | tail -2'
```

### 5. Test Locally
```bash
# Set environment variables
export AWS_ACCESS_KEY_ID="your-key-id"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="eu-north-1"
export S3_BUCKET_NAME="sweet-waveform-templates-917675236412-eu-north-1-an"
export S3_TEMPLATES_PREFIX="processed_templates/"
export USE_S3_TEMPLATES="true"

# Install boto3
pip install boto3

# Run test
cd SWEET_scripts/summing
python test_s3_templates.py
```

If tests pass, continue to deployment!

### 6. Configure Render

1. Go to https://dashboard.render.com
2. Select your `sweet-web` service
3. Go to "Environment" tab
4. Add these variables:

```
AWS_ACCESS_KEY_ID = your-access-key-id
AWS_SECRET_ACCESS_KEY = your-secret-access-key
AWS_DEFAULT_REGION = eu-north-1
S3_BUCKET_NAME = sweet-waveform-templates-917675236412-eu-north-1-an
S3_TEMPLATES_PREFIX = processed_templates/
USE_S3_TEMPLATES = true
TEMPLATES_CACHE_DIR = /tmp/sweet_templates
```

⚠️ **Important**: Mark `AWS_SECRET_ACCESS_KEY` as secret!

### 7. Deploy to Render

```bash
# Commit changes
git add .
git commit -m "Add S3 templates support"
git push

# Render auto-deploys (or trigger manually in dashboard)
```

### 8. Test in Production

1. Go to your deployed SWEET web app
2. Navigate to Waveforms section
3. Click "Compute Waveforms"
4. First request will be slow (~30 seconds) while templates download
5. Subsequent requests will be fast (cached)

## Troubleshooting

### Upload is slow
**Normal!** 116GB takes 2-8 hours depending on your internet speed.

Check progress:
```bash
aws s3 ls s3://sweet-waveform-templates/processed_templates/ --recursive | wc -l
```

### "Access Denied" error
Check IAM permissions. User needs `s3:GetObject` and `s3:ListBucket` on your bucket.

### "Bucket not found" error
Verify bucket name:
```bash
aws s3 ls s3://sweet-waveform-templates/
```

### Render deployment fails
Check logs in Render dashboard. Common issues:
- Missing environment variables
- boto3 not in requirements.txt (already added)
- Wrong AWS region

## Cost Estimate

- **S3 Storage (STANDARD_IA)**: ~$1.45/month for 116GB
- **S3 Requests**: ~$0.01-0.10/month
- **Data Transfer**: First 100GB/month free
- **Render**: Free tier or $7/month

**Total: ~$1.50-8.50/month**

## Alternative: Demo Subset

If you want to test with less data first:

```bash
# Create 2-5GB subset
python SWEET_scripts/summing/create_template_subset.py \
    --output SWEET_scripts/DATA/templates_demo \
    --vs30 vs30_300 \
    --mag-min 5.5 --mag-max 6.5 \
    --dist-min 10 --dist-max 100 \
    --max-per-bin 5

# Upload subset instead
aws s3 sync SWEET_scripts/DATA/templates_demo/ \
    s3://sweet-waveform-templates-917675236412-eu-north-1-an/templates_demo/ \
    --storage-class STANDARD_IA \
    --region eu-north-1

# Use S3_TEMPLATES_PREFIX=templates_demo/ in Render
```

## Next Steps

Once deployed and tested, see [DEPLOYMENT_TEMPLATES.md](DEPLOYMENT_TEMPLATES.md) for:
- Performance optimization
- CloudFront CDN setup
- Monitoring and alerts
- Cache management

## Getting Help

Created files:
- `S3_SETUP_GUIDE.md` - Detailed S3 setup instructions
- `DEPLOYMENT_TEMPLATES.md` - All deployment options
- `QUICK_START_S3.md` - This file
- `test_s3_templates.py` - S3 connection test script
- `s3_helpers.py` - S3 template loader
- `create_template_subset.py` - Create smaller template subsets

All code is ready - just follow these steps!
