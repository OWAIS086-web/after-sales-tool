#!/usr/bin/env python3
"""
Company-Aware Block Separation Utility

Separates mixed blocks between PakWheels and WhatsApp vector stores for any company.
This is a safety measure - the pipeline should keep blocks separated from the start.

Usage:
    python mix_block.py                    # Separate all companies
    python mix_block.py --company haval    # Separate specific company
"""

import pickle
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any


def separate_blocks_for_company(company_id: str, config: Any = None) -> None:
    """
    Separate blocks for a specific company into source-specific files.

    Args:
        company_id: Company identifier (e.g., 'haval', 'kia', 'toyota')
        config: Company configuration object (loaded if not provided)
    """
    # Load company config if not provided
    if config is None:
        try:
            from config import get_company_config
            config = get_company_config(company_id)
        except Exception as e:
            print(f"ERROR: Could not load config for company '{company_id}': {e}")
            return

    print(f"\n{'='*60}")
    print(f"Separating blocks for: {config.full_name} ({company_id})")
    print(f"{'='*60}\n")

    # Get file paths
    pakwheels_pkl = config.pakwheels_blocks_file if config.has_pakwheels else None
    whatsapp_pkl = config.whatsapp_blocks_file if config.has_whatsapp else None

    if not pakwheels_pkl and not whatsapp_pkl:
        print(f"  No data sources configured for {company_id}")
        return

    # Load all existing blocks from both potential files
    all_blocks: Dict[str, Any] = {}

    print("Loading blocks from pickle files...")

    if pakwheels_pkl and os.path.exists(pakwheels_pkl):
        try:
            with open(pakwheels_pkl, 'rb') as f:
                blocks = pickle.load(f)
            all_blocks.update(blocks)
            print(f"  Loaded {len(blocks)} blocks from {pakwheels_pkl}")
        except Exception as e:
            print(f"  ERROR loading {pakwheels_pkl}: {e}")
    else:
        print(f"  PakWheels pkl not found or disabled: {pakwheels_pkl}")

    if whatsapp_pkl and os.path.exists(whatsapp_pkl):
        try:
            with open(whatsapp_pkl, 'rb') as f:
                blocks = pickle.load(f)
            all_blocks.update(blocks)
            print(f"  Loaded {len(blocks)} blocks from {whatsapp_pkl}")
        except Exception as e:
            print(f"  ERROR loading {whatsapp_pkl}: {e}")
    else:
        print(f"  WhatsApp pkl not found or disabled: {whatsapp_pkl}")

    if not all_blocks:
        print(f"\n  No blocks found for {company_id}")
        return

    # Separate blocks based on block_id prefix (company-aware)
    pakwheels_blocks = {}
    whatsapp_blocks = {}
    unknown_blocks = {}

    print(f"\nSeparating {len(all_blocks)} blocks by source...")

    for block_id, block in all_blocks.items():
        # Check for company-specific PakWheels blocks
        # Format: {company}_pakwheels:* or {company}_{thread}_pakwheels:*
        if f"{company_id}_" in block_id.lower() and "pakwheels" in block_id.lower():
            pakwheels_blocks[block_id] = block
        # Check for company-specific WhatsApp blocks
        # Format: {company}_whatsapp:* or {company}_whatsapp_phone_*
        elif f"{company_id}_" in block_id.lower() and "whatsapp" in block_id.lower():
            whatsapp_blocks[block_id] = block
        # Legacy format without company prefix (backward compatibility)
        elif "pakwheels" in block_id.lower() and company_id == "haval":
            pakwheels_blocks[block_id] = block
            print(f"  [Legacy] PakWheels block: {block_id}")
        elif "whatsapp" in block_id.lower() and company_id == "haval":
            whatsapp_blocks[block_id] = block
            print(f"  [Legacy] WhatsApp block: {block_id}")
        else:
            unknown_blocks[block_id] = block
            # print(f"  WARNING: Unknown block type: {block_id}")

    print(f"\nSeparation Results:")
    print(f"  PakWheels blocks: {len(pakwheels_blocks)}")
    print(f"  WhatsApp blocks:  {len(whatsapp_blocks)}")
    if unknown_blocks:
        print(f"  Unknown blocks:   {len(unknown_blocks)} (NOT SAVED)")

    # Backup originals before overwriting
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if pakwheels_pkl and os.path.exists(pakwheels_pkl):
        backup_path = f"{pakwheels_pkl}.backup_{timestamp}"
        os.rename(pakwheels_pkl, backup_path)
        print(f"\n  Backed up PakWheels to: {backup_path}")

    if whatsapp_pkl and os.path.exists(whatsapp_pkl):
        backup_path = f"{whatsapp_pkl}.backup_{timestamp}"
        os.rename(whatsapp_pkl, backup_path)
        print(f"  Backed up WhatsApp to: {backup_path}")

    # Save separated blocks
    print(f"\nSaving separated blocks...")

    if pakwheels_pkl and pakwheels_blocks:
        with open(pakwheels_pkl, 'wb') as f:
            pickle.dump(pakwheels_blocks, f)
        print(f"  ✓ Saved {len(pakwheels_blocks)} PakWheels blocks to {pakwheels_pkl}")
    elif pakwheels_pkl and config.has_pakwheels:
        # Create empty file to avoid errors
        with open(pakwheels_pkl, 'wb') as f:
            pickle.dump({}, f)
        print(f"  ✓ Created empty PakWheels blocks file: {pakwheels_pkl}")

    if whatsapp_pkl and whatsapp_blocks:
        with open(whatsapp_pkl, 'wb') as f:
            pickle.dump(whatsapp_blocks, f)
        print(f"  ✓ Saved {len(whatsapp_blocks)} WhatsApp blocks to {whatsapp_pkl}")
    elif whatsapp_pkl and config.has_whatsapp:
        # Create empty file to avoid errors
        with open(whatsapp_pkl, 'wb') as f:
            pickle.dump({}, f)
        print(f"  ✓ Created empty WhatsApp blocks file: {whatsapp_pkl}")

    # Show date ranges
    print(f"\n📅 Date Ranges:")
    _show_date_range("PakWheels", pakwheels_blocks)
    _show_date_range("WhatsApp", whatsapp_blocks)

    print(f"\n✓ Separation complete for {config.full_name}!")


def _show_date_range(source_name: str, blocks: Dict[str, Any]) -> None:
    """Show date range for a set of blocks"""
    if not blocks:
        print(f"  {source_name}: No blocks")
        return

    dates = []
    for block in blocks.values():
        start_dt = getattr(block, "start_datetime", None)
        end_dt = getattr(block, "end_datetime", None)

        for dt in [start_dt, end_dt]:
            if dt:
                if isinstance(dt, str):
                    try:
                        dt = datetime.fromisoformat(dt)
                    except:
                        continue
                if isinstance(dt, datetime):
                    dates.append(dt)

    if dates:
        print(f"  {source_name}: {min(dates).strftime('%Y-%m-%d')} to {max(dates).strftime('%Y-%m-%d')} ({len(blocks)} blocks)")
    else:
        print(f"  {source_name}: {len(blocks)} blocks (no dates)")


def separate_all_companies() -> None:
    """Separate blocks for all enabled companies"""
    try:
        from config import get_enabled_companies
    except Exception as e:
        print(f"ERROR: Could not import config: {e}")
        return

    companies = get_enabled_companies()

    if not companies:
        print("No companies configured")
        return

    print(f"\n{'#'*60}")
    print(f"# Company-Aware Block Separation Utility")
    print(f"# Processing {len(companies)} companies")
    print(f"{'#'*60}\n")

    for company_id, config in companies.items():
        try:
            separate_blocks_for_company(company_id, config)
        except Exception as e:
            print(f"\nERROR processing {company_id}: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'#'*60}")
    print(f"# All companies processed!")
    print(f"# Restart the Flask app to see the changes")
    print(f"{'#'*60}\n")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Separate mixed blocks by company and source",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python mix_block.py                    # Process all companies
  python mix_block.py --company haval    # Process only Haval
  python mix_block.py --company kia      # Process only Kia
        """
    )
    parser.add_argument(
        '--company',
        type=str,
        help='Process specific company (e.g., haval, kia, toyota)'
    )

    args = parser.parse_args()

    if args.company:
        # Process single company
        try:
            from config import get_company_config
            config = get_company_config(args.company)
            separate_blocks_for_company(args.company, config)
        except ValueError as e:
            print(f"ERROR: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    else:
        # Process all companies
        separate_all_companies()


if __name__ == "__main__":
    main()
