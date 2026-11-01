from transformers import AutoModelForCausalLM, AutoTokenizer
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
import re
import threading
import logging
import markdown
import torch

logger = logging.getLogger(__name__)

# Smaller model for faster generation.
MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

if DEVICE.type == "cuda":
    MODEL_DTYPE = (
        torch.bfloat16
        if torch.cuda.is_bf16_supported()
        else torch.float16
    )

else:
    MODEL_DTYPE = torch.float32

_tokenizer = None
_model = None
_lock = threading.Lock()


def get_model():
    """Load the model once per process."""
    global _tokenizer, _model

    if _model is None:
        with _lock:
            if _model is None:
                logger.info("Loading blog generation model...")

                tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)

                model = AutoModelForCausalLM.from_pretrained(
                    MODEL_ID,
                    torch_dtype=MODEL_DTYPE,
                    low_cpu_mem_usage=True,
                    attn_implementation="sdpa",
                )

                model.to(DEVICE)
                model.eval()

                _tokenizer = tokenizer
                _model = model

                logger.info("Blog generation model loaded.")

    return _tokenizer, _model


SYSTEM = """
You are an expert technical blog writer who writes high-quality,
complete technical articles for Medium.

Write a complete, engaging, technically accurate blog post.

MANDATORY STRUCTURE:

1. First line: TITLE: <descriptive title>
2. Introduction explaining the topic and why it matters.
3. Several well-organized sections using ## headings.
4. Detailed explanations with practical examples.
5. Include Python code blocks when relevant to the topic.
6. Explain the code and important concepts.
7. Include common mistakes, best practices, or tips where useful.
8. End with a meaningful conclusion.

WRITING RULES:

- Target approximately 600-800 words.
- Make the article comprehensive and useful.
- Use valid Markdown formatting.
- Use fenced code blocks for code.
- Avoid repetitive explanations and filler.
- Do not skip important concepts just to shorten the article.
- Ensure the article has a clear beginning, middle, and ending.
- Output the title first, followed by the complete article.
- Do not include commentary about these instructions.
"""


class AIBlogGeneratorView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        prompt = request.data.get("prompt", "")

        if not isinstance(prompt, str) or not prompt.strip():
            return Response(
                {"error": "Prompt cannot be empty."},
                status=400,
            )

        prompt = prompt.strip()

        try:
            start_time = time.perf_counter()

            tokenizer, model = get_model()
            model_ready_time = time.perf_counter()

            messages = [
                {"role": "system", "content": SYSTEM},
                {
                    "role": "user",
                    "content": (
                        f"Write a complete technical blog post about: {prompt}"
                    ),
                },
            ]

            inputs = tokenizer.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
                return_tensors="pt",
                return_dict=True,
            )

            inputs = {
                key: value.to(DEVICE)
                for key, value in inputs.items()
            }

            input_length = inputs["input_ids"].shape[1]

            # Reserve enough tokens for a complete article.
            max_new_tokens = 1000

            with torch.inference_mode():
                output = model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=False,
                    use_cache=True,
                    pad_token_id=tokenizer.eos_token_id,
                    eos_token_id=tokenizer.eos_token_id,
                )

            generation_end_time = time.perf_counter()

            generated_tokens = output[0, input_length:]

            raw = tokenizer.decode(
                generated_tokens,
                skip_special_tokens=True,
            ).strip()

            # Extract the title and article body.
            match = re.match(
                r"^\s*TITLE:\s*(.+)",
                raw,
            )

            if match:
                title = match.group(1).strip()
                body_md = raw[match.end():].strip()
            else:
                title = prompt[:120].title()
                body_md = raw

            # Remove an accidental repeated title at the beginning.
            body_md = re.sub(
                r"^\s*TITLE:\s*[^\n]+\n*",
                "",
                body_md,
                count=1,
            )

            html = markdown.markdown(
                body_md,
                extensions=[
                    "fenced_code",
                    "tables",
                ],
            )

            end_time = time.perf_counter()

            logger.info(
                "Blog generation timings: model_ready=%.2fs, "
                "generation=%.2fs, formatting=%.2fs, total=%.2fs, "
                "generated_tokens=%d",
                model_ready_time - start_time,
                generation_end_time - model_ready_time,
                end_time - generation_end_time,
                end_time - start_time,
                len(generated_tokens),
            )

            return Response({
                "title": title,
                "html": html or "<p></p>",
            })

        except Exception:
            logger.exception("Blog generation failed")

            return Response(
                {"error": "Failed to generate blog post."},
                status=500,
            )


# ------------------- Try 2.0 --------------------#

import os
import json
import time
import logging
import requests

from dotenv import load_dotenv
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

load_dotenv()

logger = logging.getLogger(__name__)


class AIBlogGeneratorViewOLD(APIView):
    permission_classes = [IsAuthenticated]

    NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
    MODEL_NAME = "mistralai/mistral-large-4-1t-a52b"

    def post(self, request):
        # Validate prompt
        prompt = request.data.get("prompt", "")

        if not isinstance(prompt, str):
            return Response(
                {"error": "Prompt must be a string."},
                status=400
            )

        prompt = prompt.strip()

        if not prompt:
            return Response(
                {"error": "Prompt cannot be empty."},
                status=400
            )

        # Get NVIDIA API key
        api_key = os.getenv("NVIDIA_API_KEY")

        if not api_key:
            logger.error("NVIDIA_API_KEY is missing.")

            return Response(
                {"error": "NVIDIA API key is not configured."},
                status=500
            )

        # Blog generation instructions
        system_instruction = """
You are an expert technical blog writer.

Write an engaging, informative technical blog post based
on the user's topic.

Return ONLY a valid JSON object with exactly two fields:

{
    "title": "Blog title",
    "html": "<h2>Introduction</h2><p>Blog content...</p>"
}

Requirements:
- Write a clear introduction and conclusion.
- Use <h2> for main headings.
- Use <h3> for subsections.
- Use <p> for paragraphs.
- Use <ul>, <ol>, and <li> for lists.
- Use <blockquote> for quotations when appropriate.
- Format Python examples using:
  <pre><code class="language-python">...</code></pre>
- Include practical examples when relevant.
- Keep the article concise for this initial configuration.
- Return valid JSON without Markdown code fences.
- Escape quotation marks and special characters correctly
  inside JSON strings.
- Do not include <html>, <head>, or <body> tags.
"""

        payload = {
            "model": self.MODEL_NAME,
            "messages": [
                {
                    "role": "system",
                    "content": system_instruction
                },
                {
                    "role": "user",
                    "content": (
                        "Write a technical blog post about:\n\n"
                        f"{prompt}"
                    )
                }
            ],
            "max_tokens": 512,
            "temperature": 0.5,
            "top_p": 1,
            "frequency_penalty": 0,
            "presence_penalty": 0,
            "stream": False
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        start_time = time.time()

        try:
            # Send request to NVIDIA.
            response = requests.post(
                self.NVIDIA_API_URL,
                headers=headers,
                json=payload,
                timeout=(15, 300)
            )

            elapsed = round(time.time() - start_time, 2)

            logger.info(
                "NVIDIA API responded with status %s in %s seconds.",
                response.status_code,
                elapsed
            )

            # Parse response.
            try:
                response_data = response.json()
            except ValueError:
                logger.error(
                    "NVIDIA returned non-JSON data: %s",
                    response.text[:1000]
                )

                return Response(
                    {
                        "error": "NVIDIA returned an invalid response.",
                        "elapsed_seconds": elapsed
                    },
                    status=502
                )

            # Handle API errors.
            if not response.ok:
                logger.error(
                    "NVIDIA API error: status=%s response=%s",
                    response.status_code,
                    response_data
                )

                return Response(
                    {
                        "error": "NVIDIA API request failed.",
                        "status_code": response.status_code,
                        "details": response_data.get(
                            "detail",
                            response_data.get(
                                "error",
                                "Unknown NVIDIA API error."
                            )
                        )
                    },
                    status=502
                )

            # Validate choices.
            choices = response_data.get("choices", [])

            if not choices:
                logger.error(
                    "No choices in NVIDIA response: %s",
                    response_data
                )

                return Response(
                    {"error": "NVIDIA returned no generated content."},
                    status=502
                )

            message = choices[0].get("message", {})
            content = message.get("content")

            if not isinstance(content, str) or not content.strip():
                return Response(
                    {"error": "NVIDIA returned empty content."},
                    status=502
                )

            # Parse generated JSON.
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                logger.warning(
                    "Generated content is not valid JSON: %s",
                    content[:1000]
                )

                return Response(
                    {
                        "error": "The model returned invalid JSON.",
                        "generated_content": content[:2000]
                    },
                    status=502
                )

            # Validate title and HTML.
            title = result.get("title")
            html = result.get("html")

            if (
                    not isinstance(title, str)
                    or not isinstance(html, str)
                    or not title.strip()
                    or not html.strip()
            ):
                return Response(
                    {
                        "error": "The generated blog has an invalid structure."
                    },
                    status=502
                )

            # Return successful result.
            return Response(
                {
                    "title": title.strip(),
                    "html": html.strip(),
                    "model": self.MODEL_NAME,
                    "elapsed_seconds": elapsed
                },
                status=200
            )

        except requests.Timeout:
            elapsed = round(time.time() - start_time, 2)

            logger.warning(
                "NVIDIA request timed out after %s seconds.",
                elapsed
            )

            return Response(
                {
                    "error": "NVIDIA API request timed out.",
                    "elapsed_seconds": elapsed,
                    "message": (
                        "The AI provider did not return data within "
                        "the configured timeout."
                    )
                },
                status=504
            )

        except requests.RequestException:
            logger.exception("Failed to connect to NVIDIA API.")

            return Response(
                {
                    "error": "Unable to connect to NVIDIA API."
                },
                status=502
            )

# -------------------- Try 3.0---------------------#
