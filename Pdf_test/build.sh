#!/usr/bin/env bash
# Compile every .tex in this folder to PDF using XeLaTeX (needed for Arabic + fontspec).
# Usage:  bash build.sh
cd "$(dirname "$0")"
fail=0

# Make BasicTeX tools discoverable too, if present.
export PATH="/Library/TeX/texbin:$PATH"

if command -v tectonic >/dev/null 2>&1; then
  # Preferred: single-binary XeTeX engine, auto-fetches packages + Amiri font.
  for tex in *.tex; do
    echo ">> Compiling $tex (tectonic)"
    if ! tectonic -X compile --outdir . "$tex" >/dev/null 2>&1; then
      echo "   !! FAILED: $tex"
      fail=1
    fi
  done
elif command -v xelatex >/dev/null 2>&1; then
  mkdir -p build
  for tex in *.tex; do
    echo ">> Compiling $tex (xelatex)"
    # Run twice so cross-references / layout settle.
    xelatex -interaction=nonstopmode -halt-on-error -output-directory=build "$tex" >/dev/null
    xelatex -interaction=nonstopmode -halt-on-error -output-directory=build "$tex" >/dev/null
    mv "build/${tex%.tex}.pdf" "./${tex%.tex}.pdf"
  done
  rm -rf build
else
  echo "ERROR: no LaTeX engine found. Install tectonic (brew install tectonic) or BasicTeX."
  exit 1
fi
echo ">> Done. PDFs are in $(pwd)"
ls -1 *.pdf
