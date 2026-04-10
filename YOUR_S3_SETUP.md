# Your S3 Setup - Quick Reference

## Your Configuration

- **Bucket Name**: `sweet-waveform-templates-917675236412-eu-north-1-an`
- **Region**: `eu-north-1` (Stockholm, Sweden)
- **Templates Size**: 116 GB
- **Current Status**: Bucket created, empty (ready for upload)

## Next Steps

### 1. Configure AWS CLI (if not done already)

```bash
aws configure
```

When prompted, enter:
- **AWS Access Key ID**: Get from IAM Console (see S3_SETUP_GUIDE.md Step 2)
- **AWS Secret Access Key**: Get from IAM Console
- **Default region**: `eu-north-1`
- **Default output format**: `json`

### 2. Upload Templates to S3

**Option A: Using provided script (recommended)**

```bash
chmod +x upload_to_s3.sh
./upload_to_s3.sh
```

**Option B: Manual upload**

```bash
aws s3 sync SWEET_scripts/DATA/processed_templates/ \
    s3://sweet-waveform-templates-917675236412-eu-north-1-an/processed_templates/ \
    --storage-class STANDARD_IA \
    --region eu-north-1
```

**⏱️ This will take 2-8 hours for 116GB**

### 3. Monitor Upload Progress

In another terminal:

```bash
# Count uploaded files
aws s3 ls s3://sweet-waveform-templates-917675236412-eu-north-1-an/processed_templates/ --recursive | wc -l

# Check total size
aws s3 ls s3://sweet-waveform-templates-917675236412-eu-north-1-an/processed_templates/ --recursive --summarize --human-readable | tail -2
```

### 4. Test Locally

```bash
# Load configuration
source s3_config.sh

# Set your AWS credentials
export AWS_ACCESS_KEY_ID="your-key-id"
export AWS_SECRET_ACCESS_KEY="your-secret-key"

# Run test
cd SWEET_scripts/summing
python test_s3_templates.py
```

### 5. Configure Render

Add these environment variables in your Render dashboard:

```
AWS_ACCESS_KEY_ID = your-access-key-id
AWS_SECRET_ACCESS_KEY = your-secret-access-key
AWS_DEFAULT_REGION = eu-north-1
S3_BUCKET_NAME = sweet-waveform-templates-917675236412-eu-north-1-an
S3_TEMPLATES_PREFIX = processed_templates/
USE_S3_TEMPLATES = true
TEMPLATES_CACHE_DIR = /tmp/sweet_templates
```

### 6. Deploy

```bash
git add .
git commit -m "Add S3 templates support"
git push
```

## Quick Commands Reference

```bash
# Verify bucket exists
aws s3 ls s3://sweet-waveform-templates-917675236412-eu-north-1-an/

# Check upload status
aws s3 ls s3://sweet-waveform-templates-917675236412-eu-north-1-an/processed_templates/ --recursive --summarize --human-readable | tail -2

# Resume interrupted upload (just run again)
./upload_to_s3.sh

# Clear local cache
rm -rf /tmp/sweet_templates

# Estimate monthly cost
# Storage: 116GB × $0.0125/GB = ~$1.45/month
# Requests: ~$0.01-0.10/month
# Total: ~$1.50/month
```

## Files Created for Your Setup

- `upload_to_s3.sh` - Upload script with your bucket/region
- `s3_config.sh` - Environment variables for your config
- `YOUR_S3_SETUP.md` - This file

## Need Help?

See detailed guides:
- **S3_SETUP_GUIDE.md** - Complete setup walkthrough
- **QUICK_START_S3.md** - Quick start commands
- **DEPLOYMENT_TEMPLATES.md** - All deployment options

## Current Status Checklist

- [x] S3 bucket created (`sweet-waveform-templates-917675236412-eu-north-1-an`)
- [ ] IAM user created with access keys
- [ ] AWS CLI configured
- [ ] Templates uploaded to S3 (116GB)
- [ ] Tested locally with S3
- [ ] Environment variables added to Render
- [ ] Deployed to Render
- [ ] Tested waveform computation in production

**You are here**: Ready to upload templates ⬆️
