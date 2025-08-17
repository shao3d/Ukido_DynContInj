#!/bin/bash

# 🎨 Local diagram generation script for Ukido project
# Usage: ./scripts/generate_diagrams.sh

echo "🔍 Generating architecture diagrams for Ukido project..."

# Create output directory
mkdir -p docs/diagrams

# Check if dependencies are installed
command -v pydeps >/dev/null 2>&1 || { echo "⚠️  pydeps not installed. Run: pip install pydeps"; }
command -v code2flow >/dev/null 2>&1 || { echo "⚠️  code2flow not installed. Run: pip install code2flow"; }
command -v pyreverse >/dev/null 2>&1 || { echo "⚠️  pyreverse not installed. Run: pip install pylint"; }

# Generate dependency graph
if command -v pydeps >/dev/null 2>&1; then
    echo "📊 Generating dependency graph..."
    pydeps src --max-bacon=2 --cluster --noshow -o docs/diagrams/dependencies.svg
else
    echo "⏭️  Skipping dependency graph (pydeps not installed)"
fi

# Generate call flow
if command -v code2flow >/dev/null 2>&1; then
    echo "🔄 Generating call flow..."
    code2flow src/ --output docs/diagrams/call_flow.png --no-trimming --hide-legend
else
    echo "⏭️  Skipping call flow (code2flow not installed)"
fi

# Generate UML diagrams
if command -v pyreverse >/dev/null 2>&1; then
    echo "📐 Generating UML diagrams..."
    pyreverse -o png -p Ukido src/*.py -d docs/diagrams/
else
    echo "⏭️  Skipping UML diagrams (pyreverse not installed)"
fi

echo "✅ Diagram generation complete!"
echo "📁 Check docs/diagrams/ for generated files"
ls -la docs/diagrams/