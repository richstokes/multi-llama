# Brainwave 🧠

A minimal but working multi-agent LLM orchestrator in Python, powered by Ollama.

## Overview

Brainwave implements an intelligent multi-agent system with:
- **One coordinator agent** (the "brain") that:
  - Dynamically defines specialized worker agents (up to 5) tailored to each task
  - Plans and delegates subtasks
  - Evaluates results for quality
  - Iterates to improve results (up to 5 iterations)
  - Aggregates final answers
- **Dynamic worker agents** (specialists) created on-demand with custom capabilities
- **In-memory task graph** with dependency tracking
- **Iterative self-improvement** - the system refines its output until satisfactory
- **Simple CLI** to run tasks from user prompts

## Architecture

### Core Components

1. **Task Dataclass** (`Task`)
   - `id`: Unique task identifier
   - `parent_id`: Parent task reference
   - `description`: Task description
   - `assigned_agent`: Which agent executes it
   - `status`: `PENDING` | `RUNNING` | `DONE` | `FAILED`
   - `depends_on`: List of task IDs this depends on
   - `output`: Full LLM response
   - `summary`: Truncated summary for context passing

2. **LLM Wrapper** (Ollama)
   - `call_llm()`: Basic chat completion
   - `call_llm_json()`: JSON-mode with automatic retry on parse failure

3. **Agent System**
   - `Agent`: Base class with system prompt and execution logic
   - `coordinator`: Central intelligence that:
     - Defines specialized workers for each task
     - Plans subtasks and delegates work
     - Evaluates result quality
     - Iterates to improve results
   - **Dynamic workers**: Created on-demand with custom:
     - Names (e.g., `kid_explainer`, `HaikuCraftsman`, `code_analyst`)
     - Roles and expertise areas
     - System prompts tailored to the specific task

4. **Orchestrator Loop**
   - Creates root task from user prompt
   - **Iteration loop** (up to 5 iterations):
     - Coordinator analyzes task and defines specialized workers
     - Creates dynamic worker agents
     - Plans subtasks for defined workers
     - Executes tasks when dependencies are satisfied
     - Aggregates results
     - **Evaluates result quality**
     - If unsatisfactory: defines new workers and iterates
     - If satisfactory: returns final answer

### Task Flow

```
User Prompt
    ↓
Root Task (coordinator)
    ↓
╔═══════════════════ ITERATION LOOP (max 5) ═══════════════════╗
║  [Worker Definition Phase]                                     ║
║  Coordinator analyzes task → Defines 1-5 specialized workers  ║
║    ↓                                                           ║
║  [Dynamic Agent Creation]                                      ║
║  Create workers: kid_explainer, phd_explainer, etc.           ║
║    ↓                                                           ║
║  [Planning Phase]                                              ║
║  Coordinator plans subtasks for workers                        ║
║    ↓                                                           ║
║  [Execution Phase]                                             ║
║  Worker 1 → Worker 2 → Worker 3 (with dependencies)          ║
║    ↓                                                           ║
║  [Aggregation Phase]                                           ║
║  Coordinator synthesizes results                               ║
║    ↓                                                           ║
║  [Evaluation Phase]                                            ║
║  Is result satisfactory?                                       ║
║    ├─ YES → Return final answer                               ║
║    └─ NO  → Define new workers, iterate again                 ║
╚════════════════════════════════════════════════════════════════╝
    ↓
Final Answer
```

## Requirements

- Python 3.13+ (or 3.11+)
- [Ollama](https://ollama.ai/) running locally
- Model: `gpt-oss` (or configure your preferred model)

## Installation

```bash
# Clone or navigate to the repo
cd brainwave

# Install dependencies with uv
uv sync
```

## Usage

### Basic Usage

```bash
uv run python app.py "Your question or task here"
```

### Example

```bash
uv run python app.py "Explain how photosynthesis works in 3 key steps"
```

### Output

The orchestrator will:
1. Show iteration progress (ITERATION 1/5, 2/5, etc.)
2. Log worker definition and creation
3. Show task planning and execution in real-time
4. Display evaluation results (✓ Satisfactory or ✗ Needs improvement)
5. Print the final aggregated answer

```
================================================================================
ITERATION 1/5
================================================================================

Coordinator defining worker agents
Defined 3 workers: ['kid_explainer', 'college_explainer', 'phd_explainer']
Created agent: kid_explainer - Explains complex topics to children
Created agent: college_explainer - Explains to college level
Created agent: phd_explainer - Explains at PhD level
Planned 3 subtasks
Agent 'kid_explainer' executing task: a2b6ba01
Task a2b6ba01 completed successfully
...
Coordinator aggregating 3 subtask results
Coordinator evaluating result quality
Evaluation: ✓ Satisfactory

✅ Result satisfactory after 1 iteration(s)

================================================================================
FINAL ANSWER
================================================================================
[Final markdown-formatted answer]
================================================================================
```

## Configuration

### Change Model

Edit the model name in `app.py`:

```python
def call_llm(messages: list[dict], model: str = "your-model-name") -> str:
    ...
```

### Adjust Logging Level

```python
logger.add(sys.stderr, level="DEBUG", format="...")
```

Options: `DEBUG`, `INFO`, `WARNING`, `ERROR`

### Customize Coordinator Behavior

You can adjust the coordinator's decision-making by modifying its system prompt in `create_coordinator_agent()`. For example:

- **Change worker limit**: Modify "up to 5" workers to a different number
- **Add domain expertise**: Include specific domain knowledge in the prompt
- **Adjust evaluation criteria**: Change what the coordinator considers "satisfactory"
- **Modify iteration strategy**: Guide how the coordinator improves results

### Adjust Iteration Limits

In `run_orchestration()`:

```python
max_main_iterations = 5  # Change this to adjust max iterations
```

```python
max_exec_iterations = 50  # Change this for task execution safety limit
```

## Implementation Details

### Dynamic Worker Creation

The coordinator analyzes each task and defines workers with:
- **Custom names**: Descriptive names like `HaikuCraftsman`, `CodeReviewer`, `DataAnalyst`
- **Specific roles**: Tailored to the exact needs of the task
- **Optimized prompts**: Each worker gets a system prompt designed for its specialty

Example worker definition:
```json
{
  "workers": [
    {
      "name": "kid_explainer",
      "role": "Explains complex topics to 5-year-olds",
      "system_prompt": "You are an expert at explaining complex topics to young children..."
    }
  ]
}
```

### Iterative Evaluation

After each iteration, the coordinator:
1. Reviews the aggregated result
2. Compares it against the original user request
3. Outputs evaluation JSON:
   ```json
   {
     "satisfactory": false,
     "reasoning": "Missing technical depth in PhD explanation",
     "improvements_needed": "Add quantum mechanics equations and Bell inequality discussion"
   }
   ```
4. If unsatisfactory and iterations remain:
   - Defines new/different workers based on feedback
   - Re-plans with the previous result as context
   - Executes another iteration

### Error Handling

- **JSON Parse Errors**: Automatically retries once with a "fix this JSON" instruction
- **Task Failures**: Captured and logged, with status set to `FAILED`
- **LLM Errors**: Logged with clear error messages
- **Iteration Failures**: Falls back to previous good result if available

### Safety Limits

- Maximum 5 main iterations (worker definition → execution → evaluation cycles)
- Maximum 50 task execution iterations per main iteration
- Maximum 5 workers per iteration
- Prevents infinite loops and runaway costs

### Dependencies

Tasks can depend on other tasks:

```json
{
  "subtasks": [
    {
      "description": "Research topic X",
      "assigned_agent": "research_worker",
      "depends_on": []
    },
    {
      "description": "Write summary using research",
      "assigned_agent": "writer_worker",
      "depends_on": ["<id_of_first_task>"]
    }
  ]
}
```

The orchestrator only executes tasks when all dependencies are `DONE`.

## Code Structure

```
app.py
├── 1. CORE TASK DATACLASS
│   └── Task
├── 2. LLM WRAPPER (Ollama)
│   ├── call_llm()
│   └── call_llm_json()
├── 3. AGENT ABSTRACTION
│   └── Agent
├── 4. AGENT INSTANCES
│   ├── create_coordinator_agent()
│   └── create_dynamic_agent()          # Creates workers from JSON specs
├── 5. COORDINATOR PLANNING & AGGREGATION
│   ├── define_workers()                # NEW: Defines specialized workers
│   ├── plan_subtasks()
│   ├── evaluate_result()               # NEW: Evaluates quality
│   └── aggregate()
├── 6. WORKER EXECUTION
│   └── execute_task()
├── 7. ORCHESTRATOR LOOP
│   └── run_orchestration()            # Now with iteration loop
└── 8. CLI ENTRYPOINT
    ├── print_task_tree()
    └── main()
```

## Key Features

✅ **Dynamic Worker Creation**: Coordinator creates specialized agents for each task  
✅ **Iterative Refinement**: Up to 5 iterations to improve quality  
✅ **Self-Evaluation**: Coordinator critically assesses its own output  
✅ **Flexible Architecture**: Adapts to any type of query  
✅ **Dependency Tracking**: Workers can build on each other's results  

## Limitations

- **No task graph visualization**: `print_task_tree()` exists but not called by default
- **Sequential execution**: Tasks run one at a time (no true parallelism)
- **In-memory only**: Task graph not persisted between runs
- **No tool use**: Agents only have text I/O, no external tools
- **Conservative evaluation**: Coordinator may be overly critical and iterate unnecessarily

## Future Enhancements

- [ ] Add task graph visualization to CLI output
- [ ] Implement true parallel task execution (asyncio/threads)
- [ ] Add tool use for agents (web search, code execution, file I/O, etc.)
- [ ] Persistent task storage (SQLite, JSON files)
- [ ] Worker reuse across iterations (if a worker is still useful)
- [ ] Human-in-the-loop evaluation (user approves/rejects results)
- [ ] Token usage tracking and cost estimation
- [ ] Streaming responses for real-time feedback
- [ ] Web UI for monitoring task progress
- [ ] Multi-model support (different models for different workers)
- [ ] Result caching to avoid redundant work

## License

MIT

## Contributing

This is a minimal proof-of-concept. Feel free to extend and adapt for your needs!