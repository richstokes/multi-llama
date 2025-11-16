#!/bin/bash
# Example queries for the Brainwave orchestrator

echo "🧠 Brainwave Example Queries"
echo "=============================="
echo ""

# Example 1: Simple factual question
echo "Example 1: Simple factual question"
echo "-----------------------------------"
uv run python app.py "Explain how photosynthesis works in 3 key steps"
echo ""

# Example 2: Multi-step analysis
echo "Example 2: Multi-step analysis"
echo "-------------------------------"
uv run python app.py "Compare the pros and cons of renewable vs fossil fuel energy, then recommend which is better for the future"
echo ""

# Example 3: Creative task
echo "Example 3: Creative task"
echo "------------------------"
uv run python app.py "Write a short story about a robot learning to paint"
echo ""

# Example 4: Research + synthesis
echo "Example 4: Research + synthesis"
echo "--------------------------------"
uv run python app.py "Explain quantum entanglement to a 10-year-old, making sure to cover what it is, why it's weird, and what it's used for"
echo ""

# Example 5: Technical explanation
echo "Example 5: Technical explanation"
echo "---------------------------------"
uv run python app.py "Explain how a neural network learns through backpropagation"
echo ""
