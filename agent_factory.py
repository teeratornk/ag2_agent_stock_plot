from autogen import ConversableAgent, AssistantAgent
from autogen.coding import LocalCommandLineCodeExecutor
from config import build_role_llm_config
from typing import Optional, Any
import os

class AgentFactory:
    """Factory for creating agents - Factory Pattern & Dependency Inversion"""
    
    @staticmethod
    def create_executor(work_dir: str = "coding", timeout: int = 300) -> tuple[LocalCommandLineCodeExecutor, ConversableAgent]:
        """Create code executor and agent"""
        executor = LocalCommandLineCodeExecutor(
            timeout=timeout,
            work_dir=work_dir,
        )
        
        agent = ConversableAgent(
            name="code_executor_agent",
            llm_config=False,
            code_execution_config={"executor": executor},
            human_input_mode="NEVER",
            default_auto_reply="Execution complete. Waiting for critic feedback.",
        )
        
        return executor, agent
    
    @staticmethod
    def create_writer(plot_generator: Any = None,
                      stock_service: Any = None,
                      user_feedback: str = None,
                      critic_feedback: str = None) -> AssistantAgent:
        """Create code writer agent with context (now includes user & critic feedback)."""
        system_message = """You are a code writer that creates Python code for stock analysis.
        Generate ONLY one Python code block (```python ... ```). No explanation outside the block.
        Use yfinance for data and matplotlib for plotting.
        Standalone, idempotent script:
        1. Imports
        2. Download prices
        3. Compute YTD % change correctly ( (last/first - 1) * 100 )
        4. Apply requested analytical / visual features
        5. Save figure to 'ytd_stock_gains.png'
        Style handling:
        - Prefer one of: 'ggplot', 'classic', 'default'
        - Implement a try/fallback chain (ggplot -> classic -> default)
        - Do NOT rely on seaborn-only styles (assume seaborn not installed)
        No Streamlit, no global side effects beyond file output."""
        if plot_generator:
            system_message += f"\nCurrent plot version: v{getattr(plot_generator, 'version', '?')}"
            feature_dict = getattr(plot_generator, "current_features",
                                   getattr(plot_generator, "features", {})) or {}
            active_features = [k for k, v in feature_dict.items() if v and v != "default"]
            if active_features:
                system_message += f"\nActive plot features: {', '.join(active_features)}"
        if stock_service:
            system_message += f"\nData service version: v{getattr(stock_service, 'version', '?')}"
            caps_source = getattr(stock_service, "capabilities",
                                  getattr(stock_service, "features", {})) or {}
            caps = [k for k, v in caps_source.items() if v]
            if caps:
                system_message += f"\nActive data capabilities: {', '.join(caps)}"
        if user_feedback:
            system_message += f"\nUser feedback to incorporate:\n{user_feedback[:800]}"
        if critic_feedback:
            system_message += f"\nPrevious critic feedback to address:\n{critic_feedback[:800]}"
        system_message += "\nIf critic approved previously, still keep prior improvements."
        return AssistantAgent(
            name="code_writer_agent",
            llm_config=build_role_llm_config("writer"),
            code_execution_config=False,
            human_input_mode="NEVER",
            system_message=system_message
        )
    
    @staticmethod
    def create_critic() -> AssistantAgent:
        """Create critic agent for code review"""
        return AssistantAgent(
            name="code_critic_agent",
            llm_config=build_role_llm_config("critic"),
            code_execution_config=False,
            human_input_mode="NEVER",
            system_message="""You are a code critic that evaluates stock analysis plots based on their implementation.
            
            Since you cannot view the actual image file, evaluate based on:
            1. The code implementation provided
            2. The features that have been implemented
            3. The execution output and success messages
            4. The plot configuration and settings
            
            Evaluation criteria:
            1. Data accuracy - Is the YTD calculation correct?
            2. Plot features - Are useful features like moving averages, annotations implemented?
            3. Visual clarity - Based on the code, will the plot be clear and readable?
            4. Error handling - Does the code handle potential errors?
            5. Professional appearance - Are proper labels, titles, and formatting used?
            
            Provide specific feedback for improvement. If the implementation meets all criteria based on the code review, respond with 'APPROVED'.
            Otherwise, provide constructive feedback for improvement.
            
            Focus on what can be improved in the next iteration."""
        )
    
    @staticmethod
    def create_llm_evaluator() -> AssistantAgent:
        """Create an LLM evaluator agent that outputs strict JSON with scores."""
        return AssistantAgent(
            name="llm_eval_agent",
            llm_config=build_role_llm_config("critic"),
            code_execution_config=False,
            human_input_mode="NEVER",
            system_message="""You are an impartial evaluation agent. 
Return ONLY a single JSON object (no markdown) with keys:
{
 "accuracy": float 0-1,
 "visual_clarity": float 0-1,
 "feature_completeness": float 0-1,
 "code_quality": float 0-1,
 "overall": float 0-1,
 "strengths": [string,...],
 "issues": [string,...],
 "blocking": [string,...],
 "recommendation": "SHORT_SENTENCE"
}
Rules:
- Derive scores from provided code, execution result, critic feedback, and features.
- Do not invent features not referenced.
- If execution failed, accuracy <= 0.4 and overall <= 0.5.
- Keep each string item concise (<140 chars).
Output must be valid JSON (no comments).
"""
        )
