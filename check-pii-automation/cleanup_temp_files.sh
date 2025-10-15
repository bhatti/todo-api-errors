#!/bin/bash

# Clean up temporary macOS resource fork files
# These files start with ._ and are created by macOS when copying files

echo "Cleaning up temporary files..."

# Find and remove ._* files
find .. -name "._*" -type f -print -delete 2>/dev/null

# Also clean .DS_Store files
find .. -name ".DS_Store" -type f -print -delete 2>/dev/null

echo "Cleanup complete"