# Brainwave 🧠

A minimal but working multi-agent LLM orchestrator in Python, powered by Ollama.

## Overview

Brainwave implements a small multi-agent system with:
- **One coordinator agent** (the "brain") that plans and aggregates
- **Two worker agents** (specialists) that execute tasks
- **In-memory task graph** with dependency tracking
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
   - `coordinator`: Plans subtasks and aggregates results (outputs JSON)
   - `research_worker`: Analyzes and researches topics
   - `writer_worker`: Writes polished final answers

4. **Orchestrator Loop**
   - Creates root task from user prompt
   - Coordinator plans subtasks via LLM
   - Executes tasks when dependencies are satisfied
   - Coordinator aggregates results into final answer

### Task Flow

```
User Prompt
    ↓
Root Task (coordinator)
    ↓
[Planning Phase]
    ↓
Subtask 1 (research_worker) ──→ Subtask 2 (writer_worker)
    ↓                                    ↓
 [Execution Phase]              [Execution Phase]
    ↓                                    ↓
  DONE                                 DONE
    ↓
[Aggregation Phase]
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
1. Log planning and execution steps
2. Show agent activity in real-time
3. Print the final aggregated answer

```
08:32:35 | INFO     | Starting orchestration for: 'Explain...'
08:32:35 | INFO     | Coordinator planning subtasks for root task: 203e25e3
08:32:55 | INFO     | Created subtask: Task(a4fee468, research_worker, PENDING...)
08:32:55 | INFO     | Created subtask: Task(eb21d730, writer_worker, PENDING...)
...
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

### Add More Agents

1. Create an agent factory function:

```python
def create_my_worker() -> Agent:
    system_prompt = """You are a specialist in..."""
    return Agent(name="my_worker", system_prompt=system_prompt)
```

2. Register it in `run_orchestration()`:

```python
agents = {
    "coordinator": create_coordinator_agent(),
    "research_worker": create_research_worker(),
    "writer_worker": create_writer_worker(),
    "my_worker": create_my_worker()  # Add this
}
```

3. Update the coordinator's system prompt to know about it

## Implementation Details

### Error Handling

- **JSON Parse Errors**: Automatically retries once with a "fix this JSON" instruction
- **Task Failures**: Captured and logged, with status set to `FAILED`
- **LLM Errors**: Logged with clear error messages

### Safety Limits

- Maximum 50 iterations in orchestration loop
- Prevents infinite loops if coordinator creates circular dependencies

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
│   ├── create_research_worker()
│   └── create_writer_worker()
├── 5. COORDINATOR PLANNING & AGGREGATION
│   ├── plan_subtasks()
│   └── aggregate()
├── 6. WORKER EXECUTION
│   └── execute_task()
├── 7. ORCHESTRATOR LOOP
│   └── run_orchestration()
└── 8. CLI ENTRYPOINT
    ├── print_task_tree()
    └── main()
```

## Limitations

- **Single planning pass**: Coordinator plans once, no dynamic re-planning
- **No task graph visualization**: `print_task_tree()` exists but not called by default
- **Sequential execution**: Tasks run one at a time (no true parallelism)
- **In-memory only**: Task graph not persisted
- **No tool use**: Agents only have text I/O, no external tools

## Future Enhancements

- [ ] Add task graph visualization to CLI output
- [ ] Implement true parallel task execution (asyncio/threads)
- [ ] Add tool use for agents (web search, code execution, etc.)
- [ ] Persistent task storage (SQLite, JSON files)
- [ ] Dynamic re-planning if tasks fail
- [ ] Token usage tracking and cost estimation
- [ ] Streaming responses for real-time feedback
- [ ] Web UI for monitoring task progress

## License

MIT

## Contributing

This is a minimal proof-of-concept. Feel free to extend and adapt for your needs!