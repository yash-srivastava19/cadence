"""
LLM provider interface for Cadence evolution system.

This module provides a typed interface to Large Language Model APIs
with comprehensive error handling and response validation.
"""

import os
import re
import logging
import time
from typing import Optional, List
from dataclasses import dataclass

from dotenv import load_dotenv
from google import genai

from .models import LLMResponse, CodeBlock, PromptText

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """Configuration for LLM providers."""

    model: str = "gemini-2.0-flash"
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 1.0


class LLMError(Exception):
    """Custom exception for LLM-related errors."""

    pass


class LLMProvider:
    """
    Interface to Large Language Model providers.

    Provides typed methods for code generation, instruction mutation,
    and lesson extraction with comprehensive error handling.
    """

    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        """
        Initialize LLM provider.

        Args:
            config: LLM configuration, uses defaults if None
        """
        self.config = config or LLMConfig()
        self._client = self._initialize_client()

    def _initialize_client(self) -> genai.Client:
        """Initialize the LLM client."""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise LLMError("GEMINI_API_KEY environment variable not set")

        try:
            return genai.Client(api_key=api_key)
        except Exception as e:
            raise LLMError(f"Failed to initialize LLM client: {e}")

    def _make_request(
        self,
        prompt: PromptText,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        """
        Make a request to the LLM API with retries.

        Args:
            prompt: Input prompt text
            model: Model to use (defaults to config model)
            temperature: Sampling temperature (defaults to config temperature)

        Returns:
            LLMResponse with generated text and metadata

        Raises:
            LLMError: If request fails after retries
        """
        model = model or self.config.model
        temperature = temperature or self.config.temperature

        for attempt in range(self.config.max_retries):
            try:
                start_time = time.time()

                # Call generate_content with minimal supported args
                response = self._client.models.generate_content(
                    model=model, contents=prompt
                )

                if not response or not hasattr(response, "text"):
                    raise LLMError("Invalid response structure from LLM API")

                execution_time = time.time() - start_time
                logger.info(f"LLM request completed in {execution_time:.2f} seconds")

                # Extract token counts if available
                prompt_tokens = getattr(response, "prompt_token_count", None)
                completion_tokens = getattr(response, "candidates_token_count", None)
                finish_reason = getattr(response, "finish_reason", None)

                return LLMResponse(
                    text=response.text,
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    finish_reason=finish_reason,
                )

            except Exception as e:
                logger.warning(f"LLM request attempt {attempt + 1} failed: {e}")

                if attempt == self.config.max_retries - 1:
                    raise LLMError(
                        f"LLM request failed after {self.config.max_retries} attempts: {e}"
                    )

                time.sleep(self.config.retry_delay * (attempt + 1))

    def generate_code(self, prompt: PromptText) -> List[CodeBlock]:
        """
        Generate code from a prompt.

        Args:
            prompt: Generation prompt

        Returns:
            List of extracted code blocks

        Raises:
            LLMError: If generation fails
        """
        try:
            response = self._make_request(prompt, model="gemini-2.0-flash")

            # Extract code blocks from response
            code_strings = self._extract_code_blocks(response.text)

            # Convert to CodeBlock objects
            code_blocks = []
            for i, code in enumerate(code_strings):
                code_blocks.append(CodeBlock(content=code, language="python"))

            logger.debug(f"Generated {len(code_blocks)} code blocks from prompt")
            return code_blocks

        except Exception as e:
            logger.error(f"Code generation failed: {e}")
            raise LLMError(f"Code generation failed: {e}")

    def mutate_instruction(self, base_instruction: PromptText) -> str:
        """
        Mutate an instruction to improve creativity and effectiveness.

        Args:
            base_instruction: Current instruction text

        Returns:
            Improved instruction text
        """
        meta_prompt = f"""You are modifying instructions for an AI code optimizer.

The current instruction is:

\"\"\"{base_instruction}\"\"\"

Please rewrite it to help the model be more creative, more effective at reducing cost, and less repetitive.
Keep the instruction concise and return only the new instruction block, nothing else."""

        try:
            response = self._make_request(meta_prompt)
            new_instruction = response.text.strip()

            # Validate that we got a reasonable response
            if len(new_instruction) < 10:
                logger.warning("Generated instruction too short, keeping original")
                return base_instruction

            logger.debug("Successfully mutated instruction")
            return new_instruction

        except Exception as e:
            logger.error(f"Instruction mutation failed: {e}")
            return base_instruction

    def generate_lesson(self, meta_prompt: PromptText) -> str:
        """
        Generate a lesson from evolution history.

        Args:
            meta_prompt: Prompt containing evolution history

        Returns:
            Lesson text
        """
        try:
            response = self._make_request(meta_prompt)
            lesson = response.text.strip()
            # Accept any non-empty lesson
            if not lesson:
                logger.warning("Generated empty lesson, using default guidance")
                return "Focus on improving algorithm efficiency and solution quality."
            logger.debug("Successfully generated lesson")
            return lesson

        except Exception as e:
            logger.error(f"Lesson generation failed: {e}")
            return "No lesson generated due to an error."

    def _extract_code_blocks(
        self,
        text: str,
        start_marker: str = "### START_BLOCK",
        end_marker: str = "### END_BLOCK",
    ) -> List[str]:
        """
        Extract code blocks from LLM response.

        Args:
            text: Response text to extract from
            start_marker: Start block marker
            end_marker: End block marker

        Returns:
            List of extracted code strings
        """
        try:
            pattern = f"{re.escape(start_marker)}\n(.*?)\n{re.escape(end_marker)}"
            matches = re.findall(pattern, text, re.DOTALL)

            # Clean up extracted code
            cleaned_matches = []
            for match in matches:
                # Strip outer whitespace but include empty blocks
                cleaned = match.strip()
                cleaned_matches.append(cleaned)

            logger.debug(f"Extracted {len(cleaned_matches)} code blocks")
            return cleaned_matches

        except Exception as e:
            logger.error(f"Code block extraction failed: {e}")
            return []

    def validate_response(self, response_text: str) -> bool:
        """
        Validate LLM response quality.

        Args:
            response_text: Response to validate

        Returns:
            True if response is valid, False otherwise
        """
        if not response_text or not isinstance(response_text, str):
            return False

        # Check minimum length
        if len(response_text) < 10:
            return False

        # Check for excessive newlines (corruption indicator)
        if response_text.count("\n") > len(response_text) // 2:
            return False

        return True


"""
# Global LLM provider instance and module-level client for legacy functions
"""
_default_provider = LLMProvider()
# Module-level client for legacy top-level functions
client = _default_provider._client


def mutate_instruction(base_instruction: str) -> str:
    """Legacy function - mutate instruction using module-level client."""
    # Prepare meta-prompt
    meta_prompt = f"""You are modifying instructions for an AI code optimizer.

The current instruction is:

\"\"\"{base_instruction}\"\"\"

Please rewrite it to help the model be more creative, more effective at reducing cost, and less repetitive.
Keep the instruction concise and return only the new instruction block, nothing else."""
    try:
        # Call legacy client directly
        response = client.models.generate_content(contents=meta_prompt)
        new_instruction = response.text.strip()
        # Validate length
        if len(new_instruction) < 10:
            return base_instruction
        return new_instruction
    except Exception:
        return base_instruction


def generate(prompt: PromptText) -> List[str]:  # noqa: F821
    """Legacy code generation function using LLMProvider for block extraction."""
    try:
        # Use LLMProvider to generate code blocks
        code_blocks = _default_provider.generate_code(prompt)
        if code_blocks:
            return [block.content for block in code_blocks]
        # Fallback: extract blocks from prompt itself
        fallback_blocks = _default_provider._extract_code_blocks(prompt)
        if fallback_blocks:
            return fallback_blocks
        return []
    except Exception as e:
        logger.error(f"Legacy generate function failed: {e}")
        # Fallback extraction on exception
        try:
            return _default_provider._extract_code_blocks(prompt)
        except Exception:
            return []


def extract_valid_blocks(text: str) -> List[str]:
    """Extract valid code blocks from text."""
    return _default_provider._extract_code_blocks(text)


def generate_lessons(meta_prompt: str) -> str:
    """Legacy function - generate lesson."""
    return _default_provider.generate_lesson(meta_prompt)
