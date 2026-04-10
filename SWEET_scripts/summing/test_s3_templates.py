#!/usr/bin/env python3
"""
Test S3 Template Loading

This script tests S3 template access before deploying to Render.

Usage:
    # Set environment variables first
    export AWS_ACCESS_KEY_ID="your-key-id"
    export AWS_SECRET_ACCESS_KEY="your-secret-key"
    export AWS_DEFAULT_REGION="us-east-1"
    export S3_BUCKET_NAME="sweet-waveform-templates"
    export S3_TEMPLATES_PREFIX="processed_templates/"
    export USE_S3_TEMPLATES="true"
    
    # Run test
    python test_s3_templates.py
"""

import os
import sys

# Set up path
sys.path.insert(0, os.path.dirname(__file__))

def test_s3_connection():
    """Test basic S3 connectivity."""
    print("=" * 60)
    print("Testing S3 Connection")
    print("=" * 60)
    
    # Check environment variables
    required_vars = [
        'AWS_ACCESS_KEY_ID',
        'AWS_SECRET_ACCESS_KEY',
        'AWS_DEFAULT_REGION',
        'S3_BUCKET_NAME',
        'USE_S3_TEMPLATES'
    ]
    
    print("\n1. Checking environment variables:")
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Mask secrets
            if 'SECRET' in var or 'KEY_ID' in var:
                display_value = value[:4] + '****' if len(value) > 4 else '****'
            else:
                display_value = value
            print(f"   ✓ {var} = {display_value}")
        else:
            print(f"   ✗ {var} = NOT SET")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\n❌ Missing environment variables: {', '.join(missing_vars)}")
        print("\nSet them with:")
        for var in missing_vars:
            print(f"   export {var}='your-value'")
        return False
    
    print("\n2. Testing S3 import:")
    try:
        import boto3
        print("   ✓ boto3 imported successfully")
    except ImportError:
        print("   ✗ boto3 not installed")
        print("\nInstall with: pip install boto3")
        return False
    
    print("\n3. Testing S3 client:")
    try:
        s3_client = boto3.client('s3')
        print("   ✓ S3 client created")
    except Exception as e:
        print(f"   ✗ Failed to create S3 client: {e}")
        return False
    
    print("\n4. Testing bucket access:")
    bucket = os.getenv('S3_BUCKET_NAME')
    try:
        response = s3_client.head_bucket(Bucket=bucket)
        print(f"   ✓ Bucket '{bucket}' accessible")
    except Exception as e:
        print(f"   ✗ Cannot access bucket '{bucket}': {e}")
        print("\nPossible issues:")
        print("   - Bucket doesn't exist")
        print("   - Wrong AWS credentials")
        print("   - Wrong AWS region")
        print("   - IAM permissions missing")
        return False
    
    print("\n5. Listing bucket contents:")
    prefix = os.getenv('S3_TEMPLATES_PREFIX', '').rstrip('/') + '/'
    try:
        response = s3_client.list_objects_v2(
            Bucket=bucket,
            Prefix=prefix,
            MaxKeys=10
        )
        
        if 'Contents' in response:
            count = response['Contents'].__len__()
            print(f"   ✓ Found {count} objects (showing first 10)")
            for i, obj in enumerate(response['Contents'][:5]):
                size_mb = obj['Size'] / (1024 * 1024)
                print(f"      - {obj['Key']} ({size_mb:.2f} MB)")
        else:
            print(f"   ⚠ No objects found with prefix '{prefix}'")
            print("   Make sure you uploaded templates to S3")
            return False
    except Exception as e:
        print(f"   ✗ Failed to list bucket contents: {e}")
        return False
    
    print("\n✅ S3 connection test passed!")
    return True


def test_s3_template_loader():
    """Test S3 template loader."""
    print("\n" + "=" * 60)
    print("Testing S3 Template Loader")
    print("=" * 60)
    
    print("\n1. Importing S3 helpers:")
    try:
        from s3_helpers import S3TemplateLoader, get_s3_loader
        print("   ✓ S3 helpers imported")
    except ImportError as e:
        print(f"   ✗ Failed to import s3_helpers: {e}")
        return False
    
    print("\n2. Creating S3 loader:")
    try:
        loader = S3TemplateLoader()
        print(f"   ✓ Loader created")
        print(f"      Bucket: {loader.bucket_name}")
        print(f"      Prefix: {loader.prefix}")
        print(f"      Cache: {loader.cache_dir}")
    except Exception as e:
        print(f"   ✗ Failed to create loader: {e}")
        return False
    
    print("\n3. Getting template info:")
    try:
        info = loader.get_available_templates_info()
        print(f"   ✓ Template info retrieved")
        print(f"      VS30 categories: {info.get('vs30', [])[:5]}")
        print(f"      Magnitudes: {info.get('magnitudes', [])[:5]}")
        print(f"      Distances: {info.get('distances', [])[:5]}")
    except Exception as e:
        print(f"   ✗ Failed to get template info: {e}")
        return False
    
    print("\n4. Loading a test template:")
    try:
        # Try to load a common template (vs30_300, M5.5, 50km, realization 0)
        vs30_dir = 'vs30_300'
        mag_dir = 'M5.5'
        dist_dir = '050km'
        
        # List available templates in this bin
        templates = loader.list_templates(vs30_dir, mag_dir, dist_dir)
        
        if not templates:
            print(f"   ⚠ No templates found in {vs30_dir}/{mag_dir}/{dist_dir}")
            print("   Trying different location...")
            
            # Try first available
            if info.get('vs30'):
                vs30_dir = info['vs30'][0]
            if info.get('magnitudes'):
                mag_dir = info['magnitudes'][0]
            if info.get('distances'):
                dist_dir = info['distances'][0]
            
            templates = loader.list_templates(vs30_dir, mag_dir, dist_dir)
        
        if templates:
            print(f"   Found {len(templates)} templates in {vs30_dir}/{mag_dir}/{dist_dir}")
            test_template = templates[0]
            print(f"   Loading: {test_template}")
            
            from s3_helpers import load_template_from_s3
            template_data = load_template_from_s3(vs30_dir, mag_dir, dist_dir, test_template)
            
            print(f"   ✓ Template loaded successfully")
            print(f"      Shape: {template_data.shape}")
            print(f"      Size: {template_data.nbytes / 1024:.1f} KB")
            print(f"      Cached at: {loader.cache_dir / vs30_dir / mag_dir / dist_dir / test_template}")
        else:
            print(f"   ✗ No templates found to test")
            return False
            
    except Exception as e:
        print(f"   ✗ Failed to load template: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n5. Checking cache:")
    cache_size = loader.get_cache_size()
    if cache_size > 0:
        print(f"   ✓ Cache active: {cache_size / 1024:.1f} KB")
    else:
        print(f"   ⚠ No cache yet")
    
    print("\n✅ S3 template loader test passed!")
    return True


def test_helpers_integration():
    """Test helpers.py integration with S3."""
    print("\n" + "=" * 60)
    print("Testing helpers.py S3 Integration")
    print("=" * 60)
    
    print("\n1. Importing helpers:")
    try:
        from helpers import load_template, get_available_templates_info
        print("   ✓ Helpers imported")
    except Exception as e:
        print(f"   ✗ Failed to import helpers: {e}")
        return False
    
    print("\n2. Getting template info via helpers:")
    try:
        info = get_available_templates_info("S3")  # Dummy path, will use S3
        print(f"   ✓ Template info retrieved via helpers")
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        return False
    
    print("\n3. Loading template via helpers:")
    try:
        # Try common template
        template = load_template(
            templates_dir="S3",
            vs30=300,
            magnitude=5.5,
            distance_km=50,
            realization_idx=0
        )
        
        if template is not None:
            print(f"   ✓ Template loaded via helpers")
            print(f"      Shape: {template.shape}")
        else:
            print(f"   ⚠ Template not found (may not exist in S3)")
            # This is ok, just means specific template doesn't exist
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n✅ Helpers integration test passed!")
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("SWEET S3 Templates Test Suite")
    print("=" * 60)
    print()
    
    # Check if S3 mode is enabled
    if os.getenv('USE_S3_TEMPLATES', '').lower() != 'true':
        print("❌ USE_S3_TEMPLATES is not set to 'true'")
        print("\nSet it with:")
        print("   export USE_S3_TEMPLATES='true'")
        print("\nThen run this script again.")
        return 1
    
    all_passed = True
    
    # Test 1: S3 connection
    if not test_s3_connection():
        all_passed = False
        print("\n⚠️  S3 connection test failed. Fix the issues above before proceeding.")
        return 1
    
    # Test 2: S3 template loader
    if not test_s3_template_loader():
        all_passed = False
    
    # Test 3: Helpers integration
    if not test_helpers_integration():
        all_passed = False
    
    # Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 All tests passed!")
        print("=" * 60)
        print("\nYou're ready to deploy to Render!")
        print("Next steps:")
        print("1. Add environment variables to Render dashboard")
        print("2. Deploy to Render")
        print("3. Test waveform computation via web interface")
        return 0
    else:
        print("❌ Some tests failed")
        print("=" * 60)
        print("\nFix the issues above before deploying.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
