# Brainwave Changelog

## Version 2.0 - Dynamic Workers & Iterative Refinement

### Major Changes

#### 🎯 Dynamic Worker Creation
**Before (v1):**
- Fixed set of 2 workers: `research_worker` and `writer_worker`
- Workers had predefined roles
- Same agents used for every query

**After (v2):**
- Coordinator defines 1-5 specialized workers per task
- Workers created dynamically with custom:
  - Names (e.g., `kid_explainer`, `HaikuCraftsman`, `code_reviewer`)
  - Roles tailored to the specific task
  - System prompts optimized for their specialty
- Example: "Explain X to different audiences" → Creates `kid_explainer`, `college_explainer`, `phd_explainer`

#### 🔄 Iterative Self-Improvement
**Before (v1):**
- Single pass: plan → execute → aggregate → return
- No quality assessment
- Results returned regardless of quality

**After (v2):**
- Up to 5 iteration cycles
- After each cycle, coordinator evaluates:
  - Does the result fully address the user's request?
  - Is quality sufficient?
  - What's missing or needs improvement?
- If unsatisfactory:
  - Defines new/different workers based on feedback
  - Re-plans with previous result as context
  - Executes another iteration
- Returns when satisfactory OR max iterations reached

### New Functions

1. **`define_workers()`** - Coordinator analyzes task and outputs worker definitions as JSON
2. **`create_dynamic_agent()`** - Creates agent from JSON specification
3. **`evaluate_result()`** - Coordinator evaluates if result meets user's needs

### Updated Functions

- **`create_coordinator_agent()`** - Updated system prompt with new responsibilities:
  - Worker definition
  - Result evaluation
  - Iteration strategy
  
- **`run_orchestration()`** - Complete refactor:
  - Removed hardcoded workers
  - Added iteration loop (max 5)
  - Each iteration: define workers → create agents → plan → execute → aggregate → evaluate
  - Early exit on satisfactory result
  - Fallback to previous result on errors

### Removed Functions

- ~~`create_research_worker()`~~ - No longer needed (workers created dynamically)
- ~~`create_writer_worker()`~~ - No longer needed (workers created dynamically)

### Architecture Changes

**v1 Architecture:**
```
User Prompt → Coordinator Plans → Fixed Workers Execute → Coordinator Aggregates → Return
```

**v2 Architecture:**
```
User Prompt
    ↓
╔═══════════════════ ITERATION LOOP ═══════════════════╗
║ 1. Coordinator Defines Workers (JSON)                ║
║ 2. Create Dynamic Agents                             ║
║ 3. Coordinator Plans Subtasks                        ║
║ 4. Workers Execute Tasks                             ║
║ 5. Coordinator Aggregates Results                    ║
║ 6. Coordinator Evaluates Quality                     ║
║    ├─ Satisfactory? → Return Result                  ║
║    └─ Unsatisfactory? → Loop with Feedback           ║
╚═══════════════════════════════════════════════════════╝
    ↓
Final Answer
```

### Configuration Changes

#### Safety Limits
- **v1:** 50 max iterations (task execution)
- **v2:** 
  - 5 max main iterations (worker definition → evaluation cycles)
  - 50 max task execution iterations per main iteration
  - 5 max workers per iteration

### Code Statistics

- **Lines of code:** 576 → 782 (+206 lines, +36%)
- **New core functions:** 3
- **Removed functions:** 2
- **Updated functions:** 2

### Example Outputs

#### v1 Example:
```
INFO | Starting orchestration...
INFO | Coordinator planning subtasks
INFO | Created subtask: Task(abc123, research_worker, PENDING...)
INFO | Created subtask: Task(def456, writer_worker, PENDING...)
INFO | Agent 'research_worker' executing...
INFO | Agent 'writer_worker' executing...
INFO | Coordinator aggregating results
FINAL ANSWER
[Whatever the result is, returned immediately]
```

#### v2 Example:
```
INFO | Starting orchestration...

================================================================================
ITERATION 1/5
================================================================================

INFO | Coordinator defining worker agents
INFO | Defined 3 workers: ['kid_explainer', 'college_explainer', 'phd_explainer']
INFO | Created agent: kid_explainer - Explains to 5-year-olds
INFO | Created agent: college_explainer - College-level explanations
INFO | Created agent: phd_explainer - PhD-level technical depth
INFO | Coordinator planning subtasks
INFO | Created subtask: Task(abc123, kid_explainer, PENDING...)
INFO | Created subtask: Task(def456, college_explainer, PENDING...)
INFO | Created subtask: Task(ghi789, phd_explainer, PENDING...)
INFO | Agent 'kid_explainer' executing...
INFO | Agent 'college_explainer' executing...
INFO | Agent 'phd_explainer' executing...
INFO | Coordinator aggregating 3 subtask results
INFO | Coordinator evaluating result quality
INFO | Evaluation: ✓ Satisfactory

✅ Result satisfactory after 1 iteration(s)
INFO | Reasoning: All three audience levels addressed with appropriate depth

FINAL ANSWER
[High-quality result that passed evaluation]
```

### Performance Impact

**Pros:**
- Higher quality results (iterative refinement)
- Better task-specific worker selection
- More adaptive to different query types

**Cons:**
- More LLM calls per query (worker definition, evaluation)
- Longer execution time if multiple iterations needed
- Higher token usage (but capped at 5 iterations)

### Backward Compatibility

⚠️ **Breaking changes:**
- Removed `create_research_worker()` and `create_writer_worker()`
- `run_orchestration()` signature unchanged but behavior completely different
- Output format includes iteration progress

### Migration Guide

If you had custom workers in v1:

**v1 Code:**
```python
def create_my_custom_worker() -> Agent:
    return Agent(name="my_worker", system_prompt="...")

agents = {
    "coordinator": create_coordinator_agent(),
    "my_worker": create_my_custom_worker()
}
```

**v2 Approach:**
Modify the coordinator's system prompt to guide it toward creating your desired worker type:
```python
system_prompt = """...
When the user asks about [domain], create a specialized worker with:
- name: "domain_expert"
- role: "Expert in [domain]"
- system_prompt: "[specific instructions]"
..."""
```

Or, add logic in `define_workers()` to inject your custom worker based on task analysis.

---

## Version 1.0 - Initial Release

- Fixed coordinator and 2 worker agents
- In-memory task graph with dependencies
- LLM integration with Ollama
- CLI interface
- Basic error handling and logging
