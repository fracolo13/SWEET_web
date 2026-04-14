# S3 Configuration for Render Deployment

## Overview
Your SWEET application templates are stored in AWS S3. The templates must be properly configured on Render for the application to function.

## S3 Bucket Information
- **Bucket Name**: `sweet-waveform-templates-917675236412-eu-north-1-an`
- **Region**: `eu-north-1`
- **Templates Path**: `processed_templates/`

## Bucket Structure
```
sweet-waveform-templates-917675236412-eu-north-1-an/
└── processed_templates/
    ├── vs30_300/
    │   ├── M5.0/
    │   │   ├── 001km/
    │   │   │   ├── S1_real00.npy
    │   │   │   ├── S1_real01.npy
    │   │   │   └── ...
    │   │   ├── 005km/
    │   │   ├── 010km/
    │   │   └── ... (up to 200km in 5km increments)
    │   ├── M5.1/
    │   └── ... (up to M8.0)
    └── vs30_600/
        └── (same structure)
```

## Render Environment Variables

Add these environment variables in your Render dashboard:

### Required Variables

1. **USE_S3_TEMPLATES**
   - Value: `true`
   - Description: Enables S3 template loading mode

2. **S3_BUCKET_NAME**
   - Value: `sweet-waveform-templates-917675236412-eu-north-1-an`
   - Description: Your S3 bucket name

3. **S3_TEMPLATES_PREFIX**
   - Value: `processed_templates/`
   - Description: Folder path within bucket (must end with `/`)

4. **AWS_ACCESS_KEY_ID**
   - Value: `[Your AWS Access Key]`
   - Description: IAM user access key with S3 read permissions

5. **AWS_SECRET_ACCESS_KEY**
   - Value: `[Your AWS Secret Key]`
   - Description: IAM user secret key

6. **AWS_DEFAULT_REGION**
   - Value: `eu-north-1`
   - Description: AWS region where your bucket is located

### How to Set Environment Variables on Render

1. Go to your Render dashboard
2. Select your web service
3. Click on **Environment** in the left sidebar
4. Click **Add Environment Variable**
5. Add each variable listed above
6. Click **Save Changes**
7. Render will automatically redeploy your service

## IAM Permissions

Your AWS IAM user needs these S3 permissions:

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
                "arn:aws:s3:::sweet-waveform-templates-917675236412-eu-north-1-an",
                "arn:aws:s3:::sweet-waveform-templates-917675236412-eu-north-1-an/*"
            ]
        }
    ]
}
```

## Template Specifications

- **VS30 Values**: 300, 600 m/s
- **Magnitudes**: 5.0 to 8.0 (0.1 increments) = 31 values
- **Distances**: 1 to 200 km (5 km increments) = 41 bins
- **Realizations**: 1000 per combination
- **Total Files**: ~2,542,000 templates

## Upload Templates to S3

If you haven't uploaded your templates yet, use this command:

```bash
# Using AWS CLI
aws s3 sync SWEET_scripts/DATA/processed_templates/ \
    s3://sweet-waveform-templates-917675236412-eu-north-1-an/processed_templates/ \
    --region eu-north-1
```

Or use the provided upload script:
```bash
./upload_to_s3.sh
```

## Verification

After configuring Render, check the logs for these messages:

```
[INFO] S3 template mode requested (USE_S3_TEMPLATES=true)
[INFO] S3 template loading enabled and imports successful
[INFO] S3 loader initialized: bucket=sweet-waveform-templates-917675236412-eu-north-1-an, 
                               prefix=processed_templates/
```

If you see errors like:
- `No templates found in S3` → Check S3_TEMPLATES_PREFIX
- `NoCredentialsError` → Check AWS credentials
- `403 Forbidden` → Check IAM permissions
- `404 Not Found` → Check bucket name and region

## Troubleshooting

### Templates Not Found
- Verify templates are uploaded to S3
- Check the prefix matches exactly (including trailing `/`)
- Ensure bucket region matches AWS_DEFAULT_REGION

### Authentication Errors
- Verify AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are correct
- Check IAM user has required permissions
- Ensure credentials are not expired

### Still Having Issues?
Check Render logs for detailed error messages:
1. Go to Render dashboard
2. Select your service
3. Click **Logs** tab
4. Look for `[ERROR]` and `[DEBUG S3]` messages
