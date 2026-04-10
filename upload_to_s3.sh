#!/bin/bash
# Upload SWEET Templates to S3
# Your bucket: sweet-waveform-templates-917675236412-eu-north-1-an
# Region: eu-north-1 (Stockholm)

echo "=========================================="
echo "SWEET Templates S3 Upload Script"
echo "=========================================="
echo ""
echo "Bucket: sweet-waveform-templates-917675236412-eu-north-1-an"
echo "Region: eu-north-1"
echo "Source: $(pwd)/SWEET_scripts/DATA/processed_templates/"
echo "Size: 116 GB"
echo "Estimated time: 2-8 hours (depends on internet speed)"
echo ""
echo "Storage class: STANDARD_IA (~$1.45/month for 116GB)"
echo ""
echo "=========================================="
echo ""

read -p "Start upload? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "Upload cancelled"
    exit 1
fi

echo ""
echo "Starting upload..."
echo "⏳ This will take several hours. You can safely interrupt (Ctrl+C) and resume later."
echo ""

# Navigate to workspace root
cd "$(dirname "$0")"

# Start upload with progress
aws s3 sync SWEET_scripts/DATA/processed_templates/ \
    s3://sweet-waveform-templates-917675236412-eu-north-1-an/processed_templates/ \
    --storage-class STANDARD_IA \
    --region eu-north-1

echo ""
echo "=========================================="
echo "✅ Upload complete!"
echo "=========================================="
echo ""
echo "Verify upload:"
echo "  aws s3 ls s3://sweet-waveform-templates-917675236412-eu-north-1-an/processed_templates/ --recursive --summarize --human-readable | tail -2"
echo ""
echo "Next steps:"
echo "  1. Test locally: python SWEET_scripts/summing/test_s3_templates.py"
echo "  2. Configure Render with environment variables (see QUICK_START_S3.md)"
echo "  3. Deploy to Render"
echo ""
