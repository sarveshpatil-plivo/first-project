#!/usr/bin/env python3
"""
Day 1 - Project 1: CLI Folder Scanner Tool

A command-line tool that:
- Takes a folder path as input
- Scans all files in that folder
- Outputs a summary: total files, total size, largest file, file types breakdown
- Saves the report to a text file
"""

import os
import sys
from datetime import datetime
from collections import defaultdict


def format_size(size_bytes):
    """Convert bytes to human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} TB"


def scan_folder(folder_path):
    """Scan a folder and return statistics."""
    if not os.path.exists(folder_path):
        return None, f"Error: Path '{folder_path}' does not exist"

    if not os.path.isdir(folder_path):
        return None, f"Error: '{folder_path}' is not a directory"

    stats = {
        "folder_path": os.path.abspath(folder_path),
        "total_files": 0,
        "total_size": 0,
        "largest_file": {"name": None, "size": 0},
        "file_types": defaultdict(lambda: {"count": 0, "size": 0}),
        "files": []
    }

    # Scan the folder
    for item in os.listdir(folder_path):
        item_path = os.path.join(folder_path, item)

        # Only count files (not subdirectories)
        if os.path.isfile(item_path):
            file_size = os.path.getsize(item_path)

            # Get file extension
            _, ext = os.path.splitext(item)
            ext = ext.lower() if ext else "(no extension)"

            # Update stats
            stats["total_files"] += 1
            stats["total_size"] += file_size
            stats["file_types"][ext]["count"] += 1
            stats["file_types"][ext]["size"] += file_size
            stats["files"].append({"name": item, "size": file_size, "type": ext})

            # Track largest file
            if file_size > stats["largest_file"]["size"]:
                stats["largest_file"] = {"name": item, "size": file_size}

    return stats, None


def generate_report(stats):
    """Generate a text report from the stats."""
    lines = []
    lines.append("=" * 60)
    lines.append("FOLDER SCAN REPORT")
    lines.append("=" * 60)
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Folder: {stats['folder_path']}")
    lines.append("")

    # Summary
    lines.append("-" * 40)
    lines.append("SUMMARY")
    lines.append("-" * 40)
    lines.append(f"Total Files: {stats['total_files']}")
    lines.append(f"Total Size: {format_size(stats['total_size'])}")

    if stats["largest_file"]["name"]:
        lines.append(f"Largest File: {stats['largest_file']['name']} ({format_size(stats['largest_file']['size'])})")
    else:
        lines.append("Largest File: N/A (folder is empty)")
    lines.append("")

    # File types breakdown
    lines.append("-" * 40)
    lines.append("FILE TYPES BREAKDOWN")
    lines.append("-" * 40)

    if stats["file_types"]:
        # Sort by count (most common first)
        sorted_types = sorted(stats["file_types"].items(), key=lambda x: x[1]["count"], reverse=True)

        for ext, data in sorted_types:
            lines.append(f"  {ext:15} {data['count']:5} files  {format_size(data['size']):>10}")
    else:
        lines.append("  No files found")

    lines.append("")
    lines.append("=" * 60)
    lines.append("END OF REPORT")
    lines.append("=" * 60)

    return "\n".join(lines)


def save_report(report, output_path):
    """Save the report to a file."""
    with open(output_path, 'w') as f:
        f.write(report)
    return output_path


def main():
    """Main entry point."""
    print("\n" + "=" * 50)
    print("FOLDER SCANNER - Day 1 Project")
    print("=" * 50 + "\n")

    # Get folder path from argument or prompt
    if len(sys.argv) > 1:
        folder_path = sys.argv[1]
    else:
        folder_path = input("Enter folder path to scan: ").strip()

    if not folder_path:
        print("Error: No folder path provided")
        sys.exit(1)

    # Expand ~ to home directory
    folder_path = os.path.expanduser(folder_path)

    print(f"\nScanning: {folder_path}")
    print("-" * 40)

    # Scan the folder
    stats, error = scan_folder(folder_path)

    if error:
        print(error)
        sys.exit(1)

    # Generate and display report
    report = generate_report(stats)
    print(report)

    # Save to file
    output_filename = f"scan_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), output_filename)
    save_report(report, output_path)

    print(f"\nReport saved to: {output_path}")


if __name__ == "__main__":
    main()
