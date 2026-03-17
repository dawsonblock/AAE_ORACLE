#!/bin/bash
set -e

# Setup build directory
mkdir -p build
cd build

# Languages to build
LANGUAGES=("python" "javascript" "typescript" "go" "rust")

for LANG in "${LANGUAGES[@]}"; do
    if [ ! -d "tree-sitter-$LANG" ]; then
        echo "Cloning tree-sitter-$LANG..."
        git clone https://github.com/tree-sitter/tree-sitter-$LANG
    fi
done

echo "Building multi-language bundle..."
# This requires tree-sitter-cli or manually compiling with gcc
# For this lab, we will generate a python script to handle the build 
# since tree-sitter python bindings have Language.build_library

cat <<EOF > build_lib.py
from tree_sitter import Language
import os

langs = [
    "tree-sitter-python",
    "tree-sitter-javascript",
    "tree-sitter-typescript/typescript",
    "tree-sitter-go",
    "tree-sitter-rust"
]

Language.build_library(
    "my-languages.so",
    [os.path.join("build", lang) for lang in langs]
)
EOF

python3 build_lib.py
mv my-languages.so ../
echo "Success: build/my-languages.so created."
