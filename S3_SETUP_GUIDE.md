# AWS S3 Setup Guide for SWEET Templates

This guide walks you through setting up S3 storage for your 116GB waveform templates.

## Step 1: Create S3 Bucket

### Via AWS Console (Easiest):

1. **Login to AWS Console**: https://console.aws.amazon.com/s3/
2. **Click "Create bucket"**
3. **Configure bucket**:
   - Bucket name: `sweet-waveform-templates` (must be globally unique - add your initials if taken)
   - AWS Region: Choose closest to your Render deployment (e.g., `us-east-1` for US East, `eu-west-1` for Europe)
   - Leave "Block all public access" **ENABLED** (for security)
   - Enable "Bucket Versioning": Optional (recommended for safety)
   - Click **Create bucket**

### Via AWS CLI (Alternative):

```bash
# Install AWS CLI if not already installed
brew install awscli  # macOS
# or: pip install awscli

# Configure AWS credentials (you'll need Access Key ID and Secret Access Key)
aws configure
# You'll be prompted for:
#   AWS Access Key ID: [your key]
#   AWS Secret Access Key: [your secret]
#   Default region: us-east-1 (or your preferred region)
#   Default output format: json

# Create the bucket
aws s3 mb s3://sweet-waveform-templates --region us-east-1
```

---

## Step 2: Get AWS Credentials

You need programmatic access credentials for the backend to access S3.

### Create IAM User with S3 Access:

1. **Go to IAM Console**: https://console.aws.amazon.com/iam/
2. **Click "Users" → "Create user"**
3. **User name**: `sweet-web-app`
4. **Click "Next"**
5. **Attach permissions**:
   - Click "Attach policies directly"
   - Search for `AmazonS3ReadOnlyAccess` and check it
   - (Or create custom policy for more security - see below)
6. **Click "Next" → "Create user"**
7. **Create Access Key**:
   - Click on the user you just created
   - Go to "Security credentials" tab
   - Click "Create access key"
   - Choose "Application running outside AWS"
   - Click "Next" → "Create access key"
   - **IMPORTANT**: Copy both:
     - Access Key ID (e.g., `AKIAIOSFODNN7EXAMPLE`)
     - Secret Access Key (e.g., `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY`)
   - Save these somewhere safe - you won't see the secret again!

### Custom IAM Policy (More Secure):

Instead of `AmazonS3ReadOnlyAccess`, create a policy that only allows reading from your specific bucket:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::sweet-waveform-templates",
        "arn:aws:s3:::sweet-waveform-templates/*"
      ]
    }
  ]
}
```

---

## Step 3: Upload Templates to S3

This is the most time-consuming step (116 GB will take several hours depending on your internet speed).

### Option A: Using AWS CLI (Recommended)

```bash
# Configure AWS CLI with your credentials (if not done already)
aws configure

# Navigate to your workspace
cd /Users/francescoacolosimo/Desktop/SWEET_web

# Start upload (this will take several hours for 116GB)
# The --storage-class STANDARD_IA saves money (~40% cheaper) for infrequently accessed data
aws s3 sync SWEET_scripts/DATA/processed_templates/ \
    s3://sweet-waveform-templates/processed_templates/ \
    --storage-class STANDARD_IA \
    --no-progress

# To see progress during upload, remove --no-progress
```

**Cost optimization**:
- `STANDARD`: $0.023/GB/month = ~$2.67/month for 116GB
- `STANDARD_IA` (Infrequent Access): $0.0125/GB/month = ~$1.45/month for 116GB
- Use STANDARD_IA since templates are read-only and accessed occasionally

### Option B: Using AWS S3 Console (For smaller subsets)

1. Go to your bucket in S3 console
2. Click "Upload"
3. Drag and drop folders (may timeout for large uploads)
4. Not recommended for 116GB - use CLI instead

### Monitor Upload Progress:

```bash
# In another terminal, check how many files have been uploaded
aws s3 ls s3://sweet-waveform-templates/processed_templates/ --recursive | wc -l

# Check total size uploaded
aws s3 ls s3://sweet-waveform-templates/processed_templates/ --recursive --summarize --human-readable | tail -2
```

### Resume Interrupted Upload:

The `aws s3 sync` command is smart - if interrupted, just run it again and it will only upload missing files.

---

## Step 4: Update Backend to Use S3

The backend has been updated to support S3! Here's what you need to know:

### Environment Variables on Render:

Add these environment variables to your Render web service:

1. Go to your Render dashboard
2. Select your `sweet-web` service
3. Go to "Environment" tab
4. Add these variables:

| Key | Value | Note |
|-----|-------|------|
| `AWS_ACCESS_KEY_ID` | Your access key ID | Keep this secret! |
| `AWS_SECRET_ACCESS_KEY` | Your secret access key | Keep this secret! |
| `AWS_DEFAULT_REGION` | `us-east-1` (or your region) | |
| `S3_BUCKET_NAME` | `sweet-waveform-templates` | Your bucket name |
| `S3_TEMPLATES_PREFIX` | `processed_templates/` | Prefix/folder in bucket |
| `USE_S3_TEMPLATES` | `true` | Enable S3 mode |
| `TEMPLATES_CACHE_DIR` | `/tmp/sweet_templates` | Local cache on Render |

5. Click "Save Changes"

### Testing Locally (Before Deploying):

Test S3 access locally first:

```bash
# Set environment variables in your terminal
export AWS_ACCESS_KEY_ID="your-access-key-id"
export AWS_SECRET_ACCESS_KEY="your-secret-access-key"
export AWS_DEFAULT_REGION="us-east-1"
export S3_BUCKET_NAME="sweet-waveform-templates"
export S3_TEMPLATES_PREFIX="processed_templates/"
export USE_S3_TEMPLATES="true"
export TEMPLATES_CACHE_DIR="/tmp/sweet_templates"

# Activate your conda environment
conda activate ETH

# Test the S3 template loader
python SWEET_scripts/summing/test_s3_templates.py
```

---

## Step 5: Update requirements.txt

Add boto3 (AWS SDK) to your dependencies:

```bash
# Already added to requirements.txt:
boto3>=1.26.0
```

---

## Step 6: Deploy to Render

Once you've verified S3 access works locally:

```bash
# Commit the changes
git add .
git commit -m "Add S3 templates support"
git push

# Render will auto-deploy (if you have auto-deploy enabled)
# Or manually deploy from the Render dashboard
```

---

## Step 7: Update Frontend Default Path

The frontend can now use S3 automatically. You have two options:

### Option A: Use API config endpoint (Recommended)

The frontend will automatically fetch the templates path from the backend API, which will return "S3" when S3 is enabled.

No changes needed - already implemented!

### Option B: Manual override

Users can still manually specify a local path in the UI if needed (for local testing).

---

## Troubleshooting

### "Access Denied" Errors

**Cause**: IAM permissions issue

**Fix**:
- Verify the IAM user has S3 read permissions
- Check the bucket name matches exactly
- Ensure credentials are set correctly in Render environment variables

### "Bucket Not Found" Errors

**Cause**: Wrong bucket name or region

**Fix**:
- Verify bucket name: `aws s3 ls s3://sweet-waveform-templates/`
- Check AWS_DEFAULT_REGION matches where you created the bucket

### Slow Waveform Computation

**Cause**: Downloading templates from S3 on each request

**Fix**:
- Templates are cached in `/tmp/sweet_templates` on first use
- First request will be slow (~30 seconds), subsequent requests fast
- Consider using Render's persistent disk for hot cache (optional)

### Out of Memory on Render

**Cause**: Free tier has 512MB RAM limit

**Fix**:
- Upgrade to Starter plan ($7/month) for 512MB-2GB RAM
- Or reduce number of stations/subsources per request
- Templates are loaded one at a time to minimize memory usage

---

## Cost Breakdown

| Service | Cost | Notes |
|---------|------|-------|
| **S3 Storage (STANDARD_IA)** | ~$1.45/month | 116 GB @ $0.0125/GB/month |
| **S3 Requests (GET)** | ~$0.01-0.10/month | Depends on usage, very cheap |
| **Data Transfer Out** | First 100GB/month free | Then $0.09/GB |
| **Render Web Service** | Free or $7/month | Free tier or Starter plan |
| **Total** | **~$1.50-8.50/month** | Depending on Render plan |

For typical demo usage (<100GB transfer/month): **~$1.50/month total**

---

## Performance Optimization Tips

1. **Use caching aggressively**: The backend caches templates in `/tmp` - they persist across requests in the same container

2. **Batch similar requests**: If computing waveforms for multiple scenarios, do them together to reuse cached templates

3. **Consider CloudFront CDN** (Advanced): Put CloudFront in front of S3 for faster global access (~$1/month additional)

4. **Monitor costs**: Set up AWS Billing Alerts
   - Go to AWS Billing Console
   - Create alert if costs exceed $5 or $10/month

---

## Next Steps

✅ **You've completed S3 setup when**:
- [ ] S3 bucket created
- [ ] IAM user created with credentials saved
- [ ] Templates uploaded to S3 (116GB - takes time!)
- [ ] Environment variables configured in Render
- [ ] Backend tested locally with S3
- [ ] Deployed to Render
- [ ] Tested waveform computation on production

**Current Status**: Waiting for template upload to complete (Step 3)

Once upload finishes (check with `aws s3 ls` command), proceed to Step 4!
