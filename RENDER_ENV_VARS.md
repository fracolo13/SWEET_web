# Render Environment Variables

⚠️ **IMPORTANT**: Set these environment variables in your Render dashboard before deploying.

## Required Environment Variables

Go to your Render service → Environment → Add Environment Variable

```bash
# AWS S3 Configuration
AWS_ACCESS_KEY_ID=<your-aws-access-key-id>
AWS_SECRET_ACCESS_KEY=<your-aws-secret-access-key>
AWS_DEFAULT_REGION=eu-north-1

# S3 Bucket Configuration
S3_BUCKET_NAME=sweet-waveform-templates-917675236412-eu-north-1-an
S3_TEMPLATES_PREFIX=processed_templates/

# Enable S3 Mode
USE_S3_TEMPLATES=true

# Cache directory (Render's /tmp is ephemeral but fast)
TEMPLATES_CACHE_DIR=/tmp/sweet_templates
```

**Note**: Replace `<your-aws-access-key-id>` and `<your-aws-secret-access-key>` with your actual AWS credentials.

## How to Set in Render

1. Go to https://dashboard.render.com
2. Select your SWEET web service
3. Click "Environment" in the left sidebar
4. Click "Add Environment Variable"
5. Add each variable above (one at a time)
6. Click "Save Changes"
7. Render will automatically redeploy with the new variables

## Security Note

⚠️ **IMPORTANT**: Never commit AWS credentials to git. Always use environment variables or secrets management.
