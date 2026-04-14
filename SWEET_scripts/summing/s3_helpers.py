"""
S3 Template Loader for SWEET Waveform Summation

This module provides functionality to load waveform templates from AWS S3
instead of local filesystem, enabling cloud deployment without storing
116GB of templates on the web server.

Features:
- On-demand template downloading from S3
- Local caching to minimize S3 requests
- Transparent fallback to local filesystem
- Minimal memory footprint

Environment Variables:
    USE_S3_TEMPLATES: Set to 'true' to enable S3 mode
    S3_BUCKET_NAME: S3 bucket name (e.g., 'sweet-waveform-templates')
    S3_TEMPLATES_PREFIX: Prefix/folder in bucket (e.g., 'processed_templates/')
    TEMPLATES_CACHE_DIR: Local cache directory (default: /tmp/sweet_templates)
    AWS_ACCESS_KEY_ID: AWS credentials (standard boto3 env var)
    AWS_SECRET_ACCESS_KEY: AWS credentials (standard boto3 env var)
    AWS_DEFAULT_REGION: AWS region (e.g., 'us-east-1')
"""

import os
import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# Check if S3 mode is enabled
USE_S3 = os.getenv('USE_S3_TEMPLATES', 'false').lower() == 'true'

if USE_S3:
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
        S3_AVAILABLE = True
        logger.info("S3 mode enabled - boto3 imported successfully")
    except ImportError:
        S3_AVAILABLE = False
        logger.warning("USE_S3_TEMPLATES=true but boto3 not installed. Falling back to local mode.")
        USE_S3 = False
else:
    S3_AVAILABLE = False
    logger.info("S3 mode disabled - using local filesystem")


class S3TemplateLoader:
    """Load waveform templates from S3 with local caching."""
    
    def __init__(
        self,
        bucket_name: Optional[str] = None,
        prefix: Optional[str] = None,
        cache_dir: Optional[str] = None
    ):
        """
        Initialize S3 template loader.
        
        Args:
            bucket_name: S3 bucket name (default: from env var S3_BUCKET_NAME)
            prefix: S3 prefix/folder (default: from env var S3_TEMPLATES_PREFIX)
            cache_dir: Local cache directory (default: /tmp/sweet_templates)
        """
        self.bucket_name = bucket_name or os.getenv('S3_BUCKET_NAME')
        self.prefix = (prefix or os.getenv('S3_TEMPLATES_PREFIX', '')).rstrip('/') + '/'
        self.cache_dir = Path(cache_dir or os.getenv('TEMPLATES_CACHE_DIR', '/tmp/sweet_templates'))
        
        if not self.bucket_name:
            raise ValueError("S3_BUCKET_NAME environment variable not set")
        
        # Initialize S3 client
        self.s3_client = boto3.client('s3')
        
        # Create cache directory
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache for directory listings (avoids repeated S3 LIST calls)
        self._listing_cache = {}
        
        logger.info(f"S3TemplateLoader initialized: bucket={self.bucket_name}, "
                   f"prefix={self.prefix}, cache={self.cache_dir}")
    
    def get_template_path(self, vs30_dir: str, mag_dir: str, dist_dir: str, template_file: str) -> str:
        """
        Get local path to template, downloading from S3 if needed.
        
        Args:
            vs30_dir: VS30 directory (e.g., 'vs30_300')
            mag_dir: Magnitude directory (e.g., 'M5.5')
            dist_dir: Distance directory (e.g., '050km')
            template_file: Template filename (e.g., 'S201_real001.npy')
        
        Returns:
            Local file path to template
        """
        # Construct S3 key
        s3_key = f"{self.prefix}{vs30_dir}/{mag_dir}/{dist_dir}/{template_file}"
        
        # Construct local cache path (mirror S3 structure)
        local_path = self.cache_dir / vs30_dir / mag_dir / dist_dir / template_file
        
        # Return cached file if it exists
        if local_path.exists():
            logger.debug(f"Cache hit: {template_file}")
            return str(local_path)
        
        # Download from S3
        logger.info(f"Downloading from S3: {s3_key}")
        local_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            self.s3_client.download_file(self.bucket_name, s3_key, str(local_path))
            logger.info(f"Downloaded: {template_file} ({local_path.stat().st_size / 1024:.1f} KB)")
            return str(local_path)
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                raise FileNotFoundError(f"Template not found in S3: {s3_key}")
            else:
                raise RuntimeError(f"S3 download failed: {e}")
        except NoCredentialsError:
            raise RuntimeError("AWS credentials not found. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.")
    
    def list_templates(self, vs30_dir: str, mag_dir: str, dist_dir: str) -> List[str]:
        """
        List available templates in a specific bin.
        Uses caching to avoid repeated S3 LIST operations.
        
        Args:
            vs30_dir: VS30 directory
            mag_dir: Magnitude directory
            dist_dir: Distance directory
        
        Returns:
            List of template filenames
        """
        # Create cache key
        cache_key = f"{vs30_dir}/{mag_dir}/{dist_dir}"
        
        # Return cached result if available
        if cache_key in self._listing_cache:
            logger.debug(f"Cache hit for directory listing: {cache_key}")
            return self._listing_cache[cache_key]
        
        # Not in cache - fetch from S3
        prefix = f"{self.prefix}{cache_key}/"
        
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            if 'Contents' not in response:
                self._listing_cache[cache_key] = []
                return []
            
            templates = []
            for obj in response['Contents']:
                filename = obj['Key'].split('/')[-1]
                if filename.endswith('.npy'):
                    templates.append(filename)
            
            # Cache the result
            self._listing_cache[cache_key] = templates
            logger.debug(f"Cached directory listing: {cache_key} ({len(templates)} templates)")
            
            return templates
        
        except ClientError as e:
            logger.error(f"Failed to list S3 objects: {e}")
            self._listing_cache[cache_key] = []
            return []
    
    def get_available_templates_info(self) -> Dict[str, List]:
        """
        Scan S3 bucket to get available template parameters.
        
        Returns:
            Dictionary with available vs30, magnitudes, and distances
        """
        # Check if summary exists in cache
        summary_cache = self.cache_dir / 'preprocessing_summary.json'
        if summary_cache.exists():
            logger.info("Loading template info from cached summary")
            with open(summary_cache) as f:
                data = json.load(f)
                # Normalize key names
                if 'vs30_values' in data and 'vs30' not in data:
                    data['vs30'] = data['vs30_values']
                if 'distance_bins' in data and 'distances' not in data:
                    data['distances'] = data['distance_bins']
                return data
        
        # Try to download summary from S3
        s3_summary_key = f"{self.prefix}preprocessing_summary.json"
        try:
            self.s3_client.download_file(
                self.bucket_name,
                s3_summary_key,
                str(summary_cache)
            )
            logger.info("Downloaded preprocessing_summary.json from S3")
            with open(summary_cache) as f:
                data = json.load(f)
                # Normalize key names
                if 'vs30_values' in data and 'vs30' not in data:
                    data['vs30'] = data['vs30_values']
                if 'distance_bins' in data and 'distances' not in data:
                    data['distances'] = data['distance_bins']
                return data
        except ClientError:
            logger.warning("preprocessing_summary.json not found in S3, scanning structure...")
        
        # Fallback: scan S3 structure (slower)
        vs30_set = set()
        mag_set = set()
        dist_set = set()
        
        # List all objects with common prefixes
        paginator = self.s3_client.get_paginator('list_objects_v2')
        
        for page in paginator.paginate(Bucket=self.bucket_name, Prefix=self.prefix, Delimiter='/'):
            # Get VS30 directories
            if 'CommonPrefixes' in page:
                for prefix_obj in page['CommonPrefixes']:
                    vs30_dir = prefix_obj['Prefix'].split('/')[-2]
                    if vs30_dir.startswith('vs30_'):
                        try:
                            vs30_val = int(vs30_dir.split('_')[1])
                            vs30_set.add(vs30_val)
                        except (IndexError, ValueError):
                            continue
        
        # For each VS30, get magnitudes and distances (sample first VS30 only to save time)
        if vs30_set:
            # Use first VS30 directory name for sampling
            first_vs30 = sorted(vs30_set)[0]
            sample_vs30_dir = f"vs30_{first_vs30}"
            vs30_prefix = f"{self.prefix}{sample_vs30_dir}/"
            
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=vs30_prefix, Delimiter='/'):
                if 'CommonPrefixes' in page:
                    for prefix_obj in page['CommonPrefixes']:
                        mag_dir = prefix_obj['Prefix'].split('/')[-2]
                        if mag_dir.startswith('M'):
                            try:
                                mag_val = float(mag_dir[1:])
                                mag_set.add(mag_val)
                            except ValueError:
                                continue
            
            if mag_set:
                # Use first magnitude directory name for sampling
                first_mag = sorted(mag_set)[0]
                sample_mag_dir = f"M{first_mag}"
                mag_prefix = f"{vs30_prefix}{sample_mag_dir}/"
                
                for page in paginator.paginate(Bucket=self.bucket_name, Prefix=mag_prefix, Delimiter='/'):
                    if 'CommonPrefixes' in page:
                        for prefix_obj in page['CommonPrefixes']:
                            dist_dir = prefix_obj['Prefix'].split('/')[-2]
                            if dist_dir.endswith('km'):
                                try:
                                    dist_val = int(dist_dir[:-2])
                                    dist_set.add(dist_val)
                                except ValueError:
                                    continue
        
        info = {
            'magnitudes': sorted(list(mag_set)),
            'vs30': sorted(list(vs30_set)),
            'distances': sorted(list(dist_set))
        }
        
        # Cache the info
        with open(summary_cache, 'w') as f:
            json.dump(info, f, indent=2)
        
        return info
    
    def clear_cache(self):
        """Clear the local template cache."""
        import shutil
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            logger.info(f"Cache cleared: {self.cache_dir}")
    
    def get_cache_size(self) -> int:
        """Get total size of cached templates in bytes."""
        total_size = 0
        for file_path in self.cache_dir.rglob('*.npy'):
            total_size += file_path.stat().st_size
        return total_size


# Global S3 loader instance (initialized on first use)
_s3_loader: Optional[S3TemplateLoader] = None


def get_s3_loader() -> S3TemplateLoader:
    """Get or create the global S3 loader instance."""
    global _s3_loader
    if _s3_loader is None:
        _s3_loader = S3TemplateLoader()
    return _s3_loader


def load_template_from_s3(vs30_dir: str, mag_dir: str, dist_dir: str, template_file: str) -> np.ndarray:
    """
    Load a template from S3, with caching.
    
    This is a drop-in replacement for loading from local filesystem.
    
    Args:
        vs30_dir: VS30 directory
        mag_dir: Magnitude directory
        dist_dir: Distance directory
        template_file: Template filename
    
    Returns:
        Template data as numpy array
    """
    loader = get_s3_loader()
    local_path = loader.get_template_path(vs30_dir, mag_dir, dist_dir, template_file)
    return np.load(local_path)
