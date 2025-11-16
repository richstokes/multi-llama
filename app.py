"""
Multi-agent LLM orchestrator with Ollama backend.

Architecture:
- Coordinator agent: Plans and aggregates
- Worker agents: Execute specialized tasks
- Task graph: In-memory dependency tracking
"""

import json
import sys
import uuid
from dataclasses import dataclass, field
from typing import Optional

import ollama
from loguru import logger

# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")


# ============================================================================
# 1. CORE TASK DATACLASS
# ============================================================================

@dataclass
class Task:
    """Represents a task in the orchestrator."""
    id: str
    parent_id: Optional[str]
    description: str
    assigned_agent: str
    status: str  # PENDING | RUNNING | DONE | FAILED
    depends_on: list[str] = field(default_factory=list)
    output: Optional[str] = None
    summary: Optional[str] = None

    def __repr__(self) -> str:
        desc_short = self.description[:50] + "..." if len(self.description) > 50 else self.description
        return f"Task({self.id[:8]}, {self.assigned_agent}, {self.status}, '{desc_short}')"


# ============================================================================
# 2. LLM WRAPPER (Ollama)
# ============================================================================

def call_llm(messages: list[dict], model: str = "gpt-oss") -> str:
    """
    Call Ollama API with chat messages.
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        model: Model name (default: gpt-oss)
    
    Returns:
        Assistant message content as string
    """
    try:
        logger.debug(f"Calling LLM model '{model}' with {len(messages)} messages")
        response = ollama.chat(
            model=model,
            messages=messages,
            stream=False
        )
        content = response["message"]["content"]
        logger.debug(f"LLM response: {len(content)} chars")
        return content
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        raise


def call_llm_json(messages: list[dict], model: str = "gpt-oss") -> dict:
    """
    Call Ollama API expecting JSON response.
    
    Automatically retries once with a "fix this JSON" instruction if parsing fails.
    
    Args:
        messages: List of message dicts with 'role' and 'content'
        model: Model name (default: gpt-oss)
    
    Returns:
        Parsed JSON dict
    """
    # First attempt
    response = call_llm(messages, model)
    
    try:
        # Try to extract JSON from markdown code blocks if present
        content = response.strip()
        if content.startswith("```json"):
            content = content.split("```json")[1].split("```")[0].strip()
        elif content.startswith("```"):
            content = content.split("```")[1].split("```")[0].strip()
        
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse failed on first attempt: {e}")
        logger.debug(f"Raw response: {response[:200]}")
        
        # Retry with fix instruction
        fix_messages = messages + [
            {"role": "assistant", "content": response},
            {"role": "user", "content": "That was not valid JSON. Please fix it and output ONLY valid JSON, no other text."}
        ]
        
        retry_response = call_llm(fix_messages, model)
        
        try:
            content = retry_response.strip()
            if content.startswith("```json"):
                content = content.split("```json")[1].split("```")[0].strip()
            elif content.startswith("```"):
                content = content.split("```")[1].split("```")[0].strip()
            
            return json.loads(content)
        except json.JSONDecodeError as e2:
            logger.error(f"JSON parse failed on retry: {e2}")
            logger.error(f"Raw retry response: {retry_response[:200]}")
            raise Exception(f"Failed to get valid JSON from LLM after retry: {e2}")


# ============================================================================
# 3. AGENT ABSTRACTION
# ============================================================================

class Agent:
    """Base agent class."""
    
    def __init__(self, name: str, system_prompt: str, model: str = "gpt-oss"):
        self.name = name
        self.system_prompt = system_prompt
        self.model = model
    
    def run(self, task: Task, context: str) -> str:
        """
        Execute agent on a task with given context.
        
        Args:
            task: The task to execute
            context: Context string (includes task description and dependencies)
        
        Returns:
            LLM response as string
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": context}
        ]
        
        logger.info(f"Agent '{self.name}' executing task: {task.id[:8]}")
        response = call_llm(messages, self.model)
        return response


# ============================================================================
# 4. AGENT INSTANCES
# ============================================================================

def create_coordinator_agent() -> Agent:
    """Create the coordinator agent."""
    system_prompt = """You are a Coordinator Agent in a multi-agent system.

Your responsibilities:
1. WORKER DEFINITION: Analyze the user's request and define specialized worker agents (up to 5) that would be most useful.
2. PLANNING: Break down complex user requests into subtasks for your defined workers.
3. EVALUATION: Assess if results adequately satisfy the user's original request.
4. AGGREGATION: Synthesize results from workers into a final coherent answer.

You have the ability to dynamically create specialized worker agents with custom capabilities.
Each worker should have a clear role, expertise area, and purpose.

When defining workers, output JSON ONLY in this format:
{
  "workers": [
    {
      "name": "descriptive_name_here",
      "role": "Brief description of role",
      "system_prompt": "Detailed instructions for this worker including expertise, responsibilities, and output style"
    }
  ]
}

When planning subtasks, output JSON ONLY in this format:
{
  "subtasks": [
    {
      "description": "Clear task description",
      "assigned_agent": "worker_name",
      "depends_on": []
    }
  ]
}

When evaluating results, output JSON ONLY in this format:
{
  "satisfactory": true/false,
  "reasoning": "Explanation of why result does or doesn't meet user's needs",
  "improvements_needed": "Specific areas that need work (if not satisfactory)"
}

When aggregating, produce a clear markdown-formatted final answer."""
    
    return Agent(name="coordinator", system_prompt=system_prompt)


def create_dynamic_agent(worker_def: dict) -> Agent:
    """Create a worker agent from a dynamic definition.
    
    Args:
        worker_def: Dict with 'name', 'role', 'system_prompt'
    
    Returns:
        Agent instance
    """
    return Agent(
        name=worker_def["name"],
        system_prompt=worker_def["system_prompt"]
    )


# ============================================================================
# 5. COORDINATOR PLANNING & AGGREGATION
# ============================================================================

def define_workers(
    root_task: Task,
    coordinator: Agent,
    previous_attempt: Optional[str] = None,
    previous_feedback: Optional[str] = None
) -> list[dict]:
    """
    Use coordinator to define what worker agents would be useful.
    
    Args:
        root_task: The root task
        coordinator: Coordinator agent
        previous_attempt: Previous iteration's result (if any)
        previous_feedback: Feedback on what needs improvement (if any)
    
    Returns:
        List of worker definition dicts
    """
    context = f"""WORKER DEFINITION REQUEST

User's goal: {root_task.description}
"""
    
    if previous_attempt:
        context += f"""

This is iteration {2 if not previous_feedback else 'N'}. Previous attempt did not fully satisfy the user's needs.

Previous result:
{previous_attempt[:500]}...

Feedback on what needs improvement:
{previous_feedback}
"""
    
    context += """

Analyze this goal and define 1-5 specialized worker agents that would be most effective.
Each worker should have a unique expertise area relevant to the task.

Output JSON ONLY in this format:
{
  "workers": [
    {
      "name": "descriptive_name",
      "role": "Brief role description",
      "system_prompt": "Detailed system prompt with expertise, responsibilities, and style guidelines"
    }
  ]
}"""
    
    messages = [
        {"role": "system", "content": coordinator.system_prompt},
        {"role": "user", "content": context}
    ]
    
    logger.info("Coordinator defining worker agents")
    
    try:
        result = call_llm_json(messages, coordinator.model)
        workers = result.get("workers", [])
        
        if len(workers) > 5:
            logger.warning(f"Coordinator defined {len(workers)} workers, limiting to 5")
            workers = workers[:5]
        
        logger.info(f"Defined {len(workers)} workers: {[w['name'] for w in workers]}")
        return workers
    
    except Exception as e:
        logger.error(f"Failed to define workers: {e}")
        raise


def plan_subtasks(
    root_task: Task,
    tasks: dict[str, Task],
    agents: dict[str, Agent]
) -> list[Task]:
    """
    Use coordinator to plan subtasks for the root task.
    
    Args:
        root_task: The root task to plan for
        tasks: Global tasks dict
        agents: Available agents dict
    
    Returns:
        List of newly created subtasks
    """
    coordinator = agents["coordinator"]
    
    # Build context
    worker_descriptions = [
        f"- {name}: {agent.system_prompt.split('Your role:')[0] if 'Your role:' in agent.system_prompt else agent.system_prompt[:100]}"
        for name, agent in agents.items()
        if name != "coordinator"
    ]
    
    context = f"""PLANNING REQUEST

User's goal: {root_task.description}

Available worker agents:
{chr(10).join(worker_descriptions)}

Create a plan by breaking this goal into subtasks. Assign each subtask to an appropriate worker.
You can create task dependencies using the "depends_on" field with task IDs.

Output JSON ONLY in this format:
{{
  "subtasks": [
    {{
      "description": "task description",
      "assigned_agent": "research_worker",
      "depends_on": []
    }}
  ]
}}"""
    
    messages = [
        {"role": "system", "content": coordinator.system_prompt},
        {"role": "user", "content": context}
    ]
    
    logger.info(f"Coordinator planning subtasks for root task: {root_task.id[:8]}")
    
    try:
        result = call_llm_json(messages, coordinator.model)
        subtasks_data = result.get("subtasks", [])
        
        created_tasks = []
        task_id_map = {}  # Map from index to actual task ID
        
        for idx, subtask_data in enumerate(subtasks_data):
            task_id = str(uuid.uuid4())
            task_id_map[idx] = task_id
            
            # Resolve dependencies (they might reference indices if coordinator is smart)
            depends_on = subtask_data.get("depends_on", [])
            resolved_deps = []
            for dep in depends_on:
                if isinstance(dep, int) and dep in task_id_map:
                    resolved_deps.append(task_id_map[dep])
                elif isinstance(dep, str) and dep in tasks:
                    resolved_deps.append(dep)
            
            task = Task(
                id=task_id,
                parent_id=root_task.id,
                description=subtask_data["description"],
                assigned_agent=subtask_data["assigned_agent"],
                status="PENDING",
                depends_on=resolved_deps
            )
            
            tasks[task_id] = task
            created_tasks.append(task)
            logger.info(f"Created subtask: {task}")
        
        return created_tasks
    
    except Exception as e:
        logger.error(f"Failed to plan subtasks: {e}")
        raise


def evaluate_result(
    root_task: Task,
    result: str,
    coordinator: Agent
) -> tuple[bool, str, str]:
    """
    Use coordinator to evaluate if result satisfies user's needs.
    
    Args:
        root_task: The root task
        result: The current result
        coordinator: Coordinator agent
    
    Returns:
        Tuple of (is_satisfactory, reasoning, improvements_needed)
    """
    context = f"""EVALUATION REQUEST

Original user goal: {root_task.description}

Current result:
{result}

Evaluate whether this result fully and adequately satisfies the user's original goal.
Be critical and thorough. Consider:
- Does it fully address all aspects of the request?
- Is it sufficiently detailed and accurate?
- Is the quality high enough?
- Are there any gaps or weaknesses?

Output JSON ONLY in this format:
{{
  "satisfactory": true/false,
  "reasoning": "Detailed explanation",
  "improvements_needed": "Specific areas to improve (if not satisfactory)"
}}"""
    
    messages = [
        {"role": "system", "content": coordinator.system_prompt},
        {"role": "user", "content": context}
    ]
    
    logger.info("Coordinator evaluating result quality")
    
    try:
        evaluation = call_llm_json(messages, coordinator.model)
        is_satisfactory = evaluation.get("satisfactory", False)
        reasoning = evaluation.get("reasoning", "No reasoning provided")
        improvements = evaluation.get("improvements_needed", "")
        
        logger.info(f"Evaluation: {'✓ Satisfactory' if is_satisfactory else '✗ Needs improvement'}")
        logger.debug(f"Reasoning: {reasoning}")
        
        return is_satisfactory, reasoning, improvements
    
    except Exception as e:
        logger.error(f"Failed to evaluate result: {e}")
        # Default to accepting result if evaluation fails
        return True, "Evaluation failed, accepting result", ""


def aggregate(root_task: Task, tasks: dict[str, Task], coordinator: Agent) -> str:
    """
    Use coordinator to aggregate results into final answer.
    
    Args:
        root_task: The root task
        tasks: Global tasks dict
        coordinator: Coordinator agent
    
    Returns:
        Final aggregated answer
    """
    # Collect all DONE subtasks
    subtasks = [
        t for t in tasks.values()
        if t.parent_id == root_task.id and t.status == "DONE"
    ]
    
    if not subtasks:
        return "No subtasks completed successfully."
    
    # Build context with subtask results
    results = []
    for task in subtasks:
        summary = task.summary or task.output or "No output"
        if len(summary) > 500:
            summary = summary[:500] + "..."
        results.append(f"Task: {task.description}\nResult: {summary}\n")
    
    context = f"""AGGREGATION REQUEST

Original user goal: {root_task.description}

Completed subtask results:

{chr(10).join(results)}

Synthesize these results into a final, coherent answer in markdown format.
Provide a clear, complete response to the user's original goal."""
    
    messages = [
        {"role": "system", "content": coordinator.system_prompt},
        {"role": "user", "content": context}
    ]
    
    logger.info(f"Coordinator aggregating {len(subtasks)} subtask results")
    final_answer = call_llm(messages, coordinator.model)
    return final_answer


# ============================================================================
# 6. WORKER EXECUTION
# ============================================================================

def execute_task(task: Task, agent: Agent, tasks: dict[str, Task]) -> None:
    """
    Execute a worker task.
    
    Updates task status, output, and summary in place.
    
    Args:
        task: Task to execute
        agent: Agent to use
        tasks: Global tasks dict (for dependency lookup)
    """
    task.status = "RUNNING"
    
    try:
        # Build context with dependencies
        context_parts = [f"Task: {task.description}\n"]
        
        if task.depends_on:
            context_parts.append("Dependencies (previous task results):")
            for dep_id in task.depends_on:
                dep_task = tasks.get(dep_id)
                if dep_task and dep_task.status == "DONE":
                    dep_summary = dep_task.summary or dep_task.output or "No output"
                    if len(dep_summary) > 300:
                        dep_summary = dep_summary[:300] + "..."
                    context_parts.append(f"\n- {dep_task.description}")
                    context_parts.append(f"  Result: {dep_summary}")
        
        context = "\n".join(context_parts)
        
        # Execute
        output = agent.run(task, context)
        task.output = output
        
        # Create summary (truncate for now; could use LLM to summarize)
        if len(output) > 300:
            task.summary = output[:297] + "..."
        else:
            task.summary = output
        
        task.status = "DONE"
        logger.info(f"Task {task.id[:8]} completed successfully")
    
    except Exception as e:
        task.status = "FAILED"
        task.output = f"Error: {str(e)}"
        logger.error(f"Task {task.id[:8]} failed: {e}")


# ============================================================================
# 7. ORCHESTRATOR LOOP
# ============================================================================

def run_orchestration(root_description: str) -> str:
    """
    Main orchestration loop with dynamic worker creation and iterative improvement.
    
    Args:
        root_description: User's input goal
    
    Returns:
        Final aggregated answer
    """
    logger.info(f"Starting orchestration for: '{root_description}'")
    
    # Create coordinator
    coordinator = create_coordinator_agent()
    
    # Create root task
    root_id = str(uuid.uuid4())
    root_task = Task(
        id=root_id,
        parent_id=None,
        description=root_description,
        assigned_agent="coordinator",
        status="PENDING"
    )
    
    # Iteration state
    max_main_iterations = 5
    previous_result = None
    previous_feedback = None
    final_answer = ""
    
    for main_iteration in range(1, max_main_iterations + 1):
        logger.info(f"\n{'='*80}")
        logger.info(f"ITERATION {main_iteration}/{max_main_iterations}")
        logger.info(f"{'='*80}\n")
        
        # 1. Define workers for this iteration
        try:
            worker_defs = define_workers(
                root_task,
                coordinator,
                previous_attempt=previous_result,
                previous_feedback=previous_feedback
            )
        except Exception as e:
            logger.error(f"Worker definition failed: {e}")
            if previous_result:
                return previous_result  # Return last good result
            return f"Failed to define workers: {e}"
        
        # 2. Create agents dynamically
        agents = {"coordinator": coordinator}
        for worker_def in worker_defs:
            try:
                agent = create_dynamic_agent(worker_def)
                agents[agent.name] = agent
                logger.info(f"Created agent: {agent.name} - {worker_def.get('role', 'No role specified')}")
            except Exception as e:
                logger.error(f"Failed to create agent from def {worker_def}: {e}")
        
        # 3. Initialize tasks for this iteration
        tasks: dict[str, Task] = {root_id: root_task}
        
        # 4. Plan subtasks
        try:
            subtasks = plan_subtasks(root_task, tasks, agents)
            logger.info(f"Planned {len(subtasks)} subtasks")
        except Exception as e:
            logger.error(f"Planning failed: {e}")
            if previous_result:
                return previous_result
            return f"Failed to plan tasks: {e}"
        
        # 5. Execution loop
        max_exec_iterations = 50  # Safety limit
        exec_iteration = 0
        
        while exec_iteration < max_exec_iterations:
            exec_iteration += 1
            
            # Find ready tasks (PENDING with all dependencies DONE)
            ready_tasks = []
            for task in tasks.values():
                if task.status == "PENDING" and task.assigned_agent != "coordinator":
                    # Check if all dependencies are done
                    deps_ready = all(
                        tasks.get(dep_id, {}).status == "DONE"
                        for dep_id in task.depends_on
                    ) if task.depends_on else True
                    
                    if deps_ready:
                        ready_tasks.append(task)
            
            if not ready_tasks:
                # Check if any tasks are still running
                running = [t for t in tasks.values() if t.status == "RUNNING"]
                pending = [t for t in tasks.values() if t.status == "PENDING" and t.assigned_agent != "coordinator"]
                
                if not running and not pending:
                    logger.info("All tasks completed")
                    break
                else:
                    logger.warning(f"No ready tasks but {len(running)} running, {len(pending)} pending")
                    break
            
            # Execute ready tasks
            for task in ready_tasks:
                agent = agents.get(task.assigned_agent)
                if not agent:
                    logger.error(f"Unknown agent: {task.assigned_agent}")
                    task.status = "FAILED"
                    task.output = f"Unknown agent: {task.assigned_agent}"
                    continue
                
                execute_task(task, agent, tasks)
        
        # 6. Aggregate results
        logger.info("Aggregating results")
        try:
            final_answer = aggregate(root_task, tasks, coordinator)
            root_task.status = "DONE"
            root_task.output = final_answer
        except Exception as e:
            logger.error(f"Aggregation failed: {e}")
            if previous_result:
                return previous_result
            return f"Failed to aggregate results: {e}"
        
        # 7. Evaluate result
        is_satisfactory, reasoning, improvements_needed = evaluate_result(
            root_task,
            final_answer,
            coordinator
        )
        
        if is_satisfactory:
            logger.info(f"\n✅ Result satisfactory after {main_iteration} iteration(s)")
            logger.info(f"Reasoning: {reasoning}")
            return final_answer
        else:
            logger.info(f"\n⚠️  Result needs improvement")
            logger.info(f"Reasoning: {reasoning}")
            logger.info(f"Improvements needed: {improvements_needed}")
            
            if main_iteration == max_main_iterations:
                logger.warning(f"Reached max iterations ({max_main_iterations}), returning current result")
                return final_answer
            
            # Prepare for next iteration
            previous_result = final_answer
            previous_feedback = improvements_needed
            
            # Clear tasks for next iteration (keep root task)
            for task_id in list(tasks.keys()):
                if task_id != root_id:
                    del tasks[task_id]
            
            root_task.status = "PENDING"  # Reset for next iteration
    
    return final_answer


# ============================================================================
# 8. CLI ENTRYPOINT
# ============================================================================

def print_task_tree(tasks: dict[str, Task]) -> None:
    """Print a compact tree view of all tasks."""
    print("\n" + "="*80)
    print("TASK GRAPH")
    print("="*80)
    
    # Find root
    roots = [t for t in tasks.values() if t.parent_id is None]
    
    for root in roots:
        print(f"\n🎯 ROOT: {root.description[:60]}")
        print(f"   Status: {root.status}")
        
        # Find children
        children = [t for t in tasks.values() if t.parent_id == root.id]
        for i, child in enumerate(children):
            is_last = i == len(children) - 1
            prefix = "└──" if is_last else "├──"
            status_emoji = {"DONE": "✅", "FAILED": "❌", "RUNNING": "⏳", "PENDING": "⏸️"}.get(child.status, "❓")
            
            desc_short = child.description[:50] + "..." if len(child.description) > 50 else child.description
            print(f"   {prefix} {status_emoji} [{child.assigned_agent}] {desc_short}")
            print(f"       ID: {child.id[:8]} | Deps: {len(child.depends_on)}")
    
    print("="*80 + "\n")


def main():
    """CLI entrypoint."""
    if len(sys.argv) < 2:
        print("Usage: python app.py '<your question or task>'")
        print("Example: python app.py 'Explain quantum computing to a beginner'")
        sys.exit(1)
    
    prompt = " ".join(sys.argv[1:])
    
    logger.info("="*80)
    logger.info("MULTI-AGENT ORCHESTRATOR")
    logger.info("="*80)
    
    # Run orchestration
    final_answer = run_orchestration(prompt)
    
    # Print results
    print("\n" + "="*80)
    print("FINAL ANSWER")
    print("="*80)
    print(final_answer)
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
