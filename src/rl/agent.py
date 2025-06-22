from src.llm import generate
class RLAgent:
    """
    A reinforcement learning agent that learns to improve programs
    by optimizing reward derived from evaluator cost.
    """

    def __init__(self, task, model=None):
        """
        Args:
            task: Instance of the Task class (used for execution and context)
            model: Optional LLM or policy model for code generation
        """
        self.task = task
        self.model = model  # can be LLM or any policy backbone
        self.memory = []    # stores (state, action, reward)
        self.reward_model = None

    def sample_action(self, prompt:str, n_samples=4) -> str:
        """
        Given a string prompt (state), return a generated action (code).
        """
        # Reuse your LLM logic here
        completions = generate(prompt)
        ranked = self.reward_model.score(prompt, completions)
        best_completion = max(ranked, key=lambda x: x[1])[0]
        return best_completion


    def observe(self, state: str, action: str, reward: float):
        """
        Store (state, action, reward) into memory (or policy buffer).
        """
        self.memory.append((state, action, reward))
