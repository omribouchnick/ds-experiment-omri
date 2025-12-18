#!/bin/bash
# Download latest database and CSV from PythonAnywhere
# Usage: Run this on your LOCAL machine (not PythonAnywhere)
# It will download files from PythonAnywhere to your local machine

echo "=" * 80
echo "📥 DOWNLOADING LATEST DATA FROM PYTHONANYWHERE"
echo "=" * 80

# Configuration
PYTHONANYWHERE_USER="Omribouch"
PYTHONANYWHERE_HOST="${PYTHONANYWHERE_USER}.pythonanywhere.com"
REMOTE_BASE_DIR="/home/${PYTHONANYWHERE_USER}/ds-experiment-omri/Experiment_Code"
LOCAL_BASE_DIR="ds-experiment-omri/Experiment_Code"

# Files to download
FILES=(
    "DATA/db.sqlite3"
    "DATA/conditions_experiment_3ps_11x11_120_A.csv"
)

echo ""
echo "This script will download files from PythonAnywhere using scp"
echo "Make sure you have SSH access configured"
echo ""
echo "Files to download:"
for file in "${FILES[@]}"; do
    echo "  - ${file}"
done
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 1
fi

# Create local directories if needed
mkdir -p "${LOCAL_BASE_DIR}/DATA"

# Download each file
for file in "${FILES[@]}"; do
    remote_path="${REMOTE_BASE_DIR}/${file}"
    local_path="${LOCAL_BASE_DIR}/${file}"
    
    echo ""
    echo "Downloading: ${file}"
    echo "  From: ${PYTHONANYWHERE_USER}@${PYTHONANYWHERE_HOST}:${remote_path}"
    echo "  To: ${local_path}"
    
    # Use scp to download
    scp "${PYTHONANYWHERE_USER}@${PYTHONANYWHERE_HOST}:${remote_path}" "${local_path}"
    
    if [ $? -eq 0 ]; then
        echo "  ✅ Success!"
        
        # Show file size
        if [ -f "${local_path}" ]; then
            size=$(du -h "${local_path}" | cut -f1)
            echo "  File size: ${size}"
        fi
    else
        echo "  ❌ Failed to download ${file}"
    fi
done

echo ""
echo "=" * 80
echo "✅ DOWNLOAD COMPLETE"
echo "=" * 80
echo ""
echo "Files downloaded to: ${LOCAL_BASE_DIR}/"
echo ""
echo "You can now run your validation notebook with the latest data!"

