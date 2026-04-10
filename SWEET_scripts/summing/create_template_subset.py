#!/usr/bin/env python3
"""
Create a subset of templates for deployment testing.

This script creates a smaller version of the templates directory
suitable for demo/testing deployments on platforms with storage constraints.

Usage:
    python create_template_subset.py --output OUTPUT_DIR [OPTIONS]
"""

import os
import shutil
import argparse
import json
from pathlib import Path


def create_subset(
    source_dir: str,
    output_dir: str,
    vs30_categories: list = None,
    mag_range: tuple = (5.5, 6.5),
    dist_range: tuple = (10, 100),
    max_templates_per_bin: int = 10
):
    """
    Create a subset of templates based on specified criteria.
    
    Args:
        source_dir: Full templates directory
        output_dir: Where to create the subset
        vs30_categories: List of VS30 categories to include (e.g., ['vs30_300'])
        mag_range: (min_mag, max_mag) tuple
        dist_range: (min_dist_km, max_dist_km) tuple
        max_templates_per_bin: Maximum templates per magnitude/distance bin
    """
    source_path = Path(source_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    if vs30_categories is None:
        vs30_categories = ['vs30_300', 'vs30_800']  # Default to two common categories
    
    print(f"Creating template subset:")
    print(f"  VS30 categories: {vs30_categories}")
    print(f"  Magnitude range: M{mag_range[0]} - M{mag_range[1]}")
    print(f"  Distance range: {dist_range[0]} - {dist_range[1]} km")
    print(f"  Max templates per bin: {max_templates_per_bin}")
    print()
    
    total_files = 0
    total_size = 0
    
    # Iterate through VS30 categories
    for vs30_dir in os.listdir(source_path):
        if not vs30_dir.startswith('vs30_'):
            continue
        
        if vs30_dir not in vs30_categories:
            print(f"Skipping {vs30_dir} (not in selected categories)")
            continue
        
        vs30_path = source_path / vs30_dir
        if not vs30_path.is_dir():
            continue
        
        output_vs30 = output_path / vs30_dir
        output_vs30.mkdir(exist_ok=True)
        
        # Iterate through magnitude directories
        for mag_dir in os.listdir(vs30_path):
            if not mag_dir.startswith('M'):
                continue
            
            try:
                mag_value = float(mag_dir[1:])  # Extract magnitude value
            except ValueError:
                continue
            
            if not (mag_range[0] <= mag_value <= mag_range[1]):
                continue
            
            mag_path = vs30_path / mag_dir
            if not mag_path.is_dir():
                continue
            
            output_mag = output_vs30 / mag_dir
            output_mag.mkdir(exist_ok=True)
            
            # Iterate through distance directories
            for dist_dir in os.listdir(mag_path):
                if not dist_dir.endswith('km'):
                    continue
                
                try:
                    dist_value = int(dist_dir[:-2])  # Extract distance value
                except ValueError:
                    continue
                
                if not (dist_range[0] <= dist_value <= dist_range[1]):
                    continue
                
                dist_path = mag_path / dist_dir
                if not dist_path.is_dir():
                    continue
                
                output_dist = output_mag / dist_dir
                output_dist.mkdir(exist_ok=True)
                
                # Copy limited number of template files
                template_files = [f for f in os.listdir(dist_path) if f.endswith('.npy')]
                files_to_copy = template_files[:max_templates_per_bin]
                
                for template_file in files_to_copy:
                    src_file = dist_path / template_file
                    dst_file = output_dist / template_file
                    
                    shutil.copy2(src_file, dst_file)
                    file_size = os.path.getsize(src_file)
                    total_files += 1
                    total_size += file_size
                
                if files_to_copy:
                    print(f"  Copied {len(files_to_copy)} templates: {vs30_dir}/{mag_dir}/{dist_dir}")
    
    # Copy preprocessing summary if it exists
    summary_file = source_path / 'preprocessing_summary.json'
    if summary_file.exists():
        shutil.copy2(summary_file, output_path / 'preprocessing_summary.json')
    
    # Create a subset info file
    subset_info = {
        'source_directory': str(source_path),
        'vs30_categories': vs30_categories,
        'magnitude_range': mag_range,
        'distance_range_km': dist_range,
        'max_templates_per_bin': max_templates_per_bin,
        'total_files': total_files,
        'total_size_mb': round(total_size / (1024 * 1024), 2),
        'total_size_gb': round(total_size / (1024 * 1024 * 1024), 2)
    }
    
    with open(output_path / 'subset_info.json', 'w') as f:
        json.dump(subset_info, f, indent=2)
    
    print()
    print("=" * 60)
    print("Subset creation complete!")
    print(f"  Total files: {total_files}")
    print(f"  Total size: {total_size / (1024**3):.2f} GB ({total_size / (1024**2):.2f} MB)")
    print(f"  Output directory: {output_path}")
    print()
    print("Next steps:")
    print("  1. Test with: python SWEET_scripts/summing/sum_from_web_input.py --templates-dir", output_path)
    print("  2. Commit to git if size is acceptable")
    print("  3. Or upload to Render Persistent Disk / S3")
    print("=" * 60)
    
    return subset_info


def main():
    parser = argparse.ArgumentParser(
        description='Create a subset of waveform templates for deployment'
    )
    parser.add_argument(
        '--source',
        default='SWEET_scripts/DATA/processed_templates',
        help='Source templates directory (default: SWEET_scripts/DATA/processed_templates)'
    )
    parser.add_argument(
        '--output',
        required=True,
        help='Output directory for template subset'
    )
    parser.add_argument(
        '--vs30',
        nargs='+',
        default=['vs30_300'],
        help='VS30 categories to include (default: vs30_300)'
    )
    parser.add_argument(
        '--mag-min',
        type=float,
        default=5.5,
        help='Minimum magnitude (default: 5.5)'
    )
    parser.add_argument(
        '--mag-max',
        type=float,
        default=6.5,
        help='Maximum magnitude (default: 6.5)'
    )
    parser.add_argument(
        '--dist-min',
        type=int,
        default=10,
        help='Minimum distance in km (default: 10)'
    )
    parser.add_argument(
        '--dist-max',
        type=int,
        default=100,
        help='Maximum distance in km (default: 100)'
    )
    parser.add_argument(
        '--max-per-bin',
        type=int,
        default=10,
        help='Maximum templates per bin (default: 10)'
    )
    
    args = parser.parse_args()
    
    create_subset(
        source_dir=args.source,
        output_dir=args.output,
        vs30_categories=args.vs30,
        mag_range=(args.mag_min, args.mag_max),
        dist_range=(args.dist_min, args.dist_max),
        max_templates_per_bin=args.max_per_bin
    )


if __name__ == '__main__':
    main()
