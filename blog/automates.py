# from transformers import AutoModelForCausalLM, AutoTokenizer
# from rest_framework.views import APIView
# from rest_framework.permissions import IsAuthenticated
# import re
# import threading
# import logging
# import markdown
# import torch
#
# logger = logging.getLogger(__name__)
#
# # Smaller model for faster generation.
# MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"
#
# DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
#
# if DEVICE.type == "cuda":
#     MODEL_DTYPE = (
#         torch.bfloat16
#         if torch.cuda.is_bf16_supported()
#         else torch.float16
#     )
#
# else:
#     MODEL_DTYPE = torch.float32
#
# _tokenizer = None
# _model = None
# _lock = threading.Lock()
#
#
# def get_modelold():
#     """Load the model once per process."""
#     global _tokenizer, _model
#
#     if _model is None:
#         with _lock:
#             if _model is None:
#                 logger.info("Loading blog generation model...")
#
#                 tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
#
#                 model = AutoModelForCausalLM.from_pretrained(
#                     MODEL_ID,
#                     torch_dtype=MODEL_DTYPE,
#                     low_cpu_mem_usage=True,
#                     attn_implementation="sdpa",
#                 )
#
#                 model.to(DEVICE)
#                 model.eval()
#
#                 _tokenizer = tokenizer
#                 _model = model
#
#                 logger.info("Blog generation model loaded.")
#
#     return _tokenizer, _model
#
#
# SYSTEM = """
# You are an expert technical blog writer who writes high-quality,
# complete technical articles for Medium.
#
# Write a complete, engaging, technically accurate blog post.
#
# MANDATORY STRUCTURE:
#
# 1. First line: TITLE: <descriptive title>
# 2. Introduction explaining the topic and why it matters.
# 3. Several well-organized sections using ## headings.
# 4. Detailed explanations with practical examples.
# 5. Include Python code blocks when relevant to the topic.
# 6. Explain the code and important concepts.
# 7. Include common mistakes, best practices, or tips where useful.
# 8. End with a meaningful conclusion.
#
# WRITING RULES:
#
# - Target approximately 600-800 words.
# - Make the article comprehensive and useful.
# - Use valid Markdown formatting.
# - Use fenced code blocks for code.
# - Avoid repetitive explanations and filler.
# - Do not skip important concepts just to shorten the article.
# - Ensure the article has a clear beginning, middle, and ending.
# - Output the title first, followed by the complete article.
# - Do not include commentary about these instructions.
# """
#
#
# class AIBlogGeneratorViewold(APIView):
#     permission_classes = [IsAuthenticated]
#
#     def post(self, request):
#         prompt = request.data.get("prompt", "")
#
#         if not isinstance(prompt, str) or not prompt.strip():
#             return Response(
#                 {"error": "Prompt cannot be empty."},
#                 status=400,
#             )
#
#         prompt = prompt.strip()
#
#         try:
#             start_time = time.perf_counter()
#
#             tokenizer, model = get_model()
#             model_ready_time = time.perf_counter()
#
#             messages = [
#                 {"role": "system", "content": SYSTEM},
#                 {
#                     "role": "user",
#                     "content": (
#                         f"Write a complete technical blog post about: {prompt}"
#                     ),
#                 },
#             ]
#
#             inputs = tokenizer.apply_chat_template(
#                 messages,
#                 tokenize=True,
#                 add_generation_prompt=True,
#                 return_tensors="pt",
#                 return_dict=True,
#             )
#
#             inputs = {
#                 key: value.to(DEVICE)
#                 for key, value in inputs.items()
#             }
#
#             input_length = inputs["input_ids"].shape[1]
#
#             # Reserve enough tokens for a complete article.
#             max_new_tokens = 1000
#
#             with torch.inference_mode():
#                 output = model.generate(
#                     **inputs,
#                     max_new_tokens=max_new_tokens,
#                     do_sample=False,
#                     use_cache=True,
#                     pad_token_id=tokenizer.eos_token_id,
#                     eos_token_id=tokenizer.eos_token_id,
#                 )
#
#             generation_end_time = time.perf_counter()
#
#             generated_tokens = output[0, input_length:]
#
#             raw = tokenizer.decode(
#                 generated_tokens,
#                 skip_special_tokens=True,
#             ).strip()
#
#             # Extract the title and article body.
#             match = re.match(
#                 r"^\s*TITLE:\s*(.+)",
#                 raw,
#             )
#
#             if match:
#                 title = match.group(1).strip()
#                 body_md = raw[match.end():].strip()
#             else:
#                 title = prompt[:120].title()
#                 body_md = raw
#
#             # Remove an accidental repeated title at the beginning.
#             body_md = re.sub(
#                 r"^\s*TITLE:\s*[^\n]+\n*",
#                 "",
#                 body_md,
#                 count=1,
#             )
#
#             html = markdown.markdown(
#                 body_md,
#                 extensions=[
#                     "fenced_code",
#                     "tables",
#                 ],
#             )
#
#             end_time = time.perf_counter()
#
#             logger.info(
#                 "Blog generation timings: model_ready=%.2fs, "
#                 "generation=%.2fs, formatting=%.2fs, total=%.2fs, "
#                 "generated_tokens=%d",
#                 model_ready_time - start_time,
#                 generation_end_time - model_ready_time,
#                 end_time - generation_end_time,
#                 end_time - start_time,
#                 len(generated_tokens),
#             )
#
#             return Response({
#                 "title": title,
#                 "html": html or "<p></p>",
#             })
#
#         except Exception:
#             logger.exception("Blog generation failed")
#
#             return Response(
#                 {"error": "Failed to generate blog post."},
#                 status=500,
#             )


# ------------------- Try 2.0 --------------------#

import logging
import re
import threading
import time

import markdown
import torch

from transformers import AutoModelForCausalLM, AutoTokenizer
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


logger = logging.getLogger(__name__)

MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

if DEVICE.type == "cuda":
    MODEL_DTYPE = (
        torch.bfloat16
        if torch.cuda.is_bf16_supported()
        else torch.float16
    )
else:
    MODEL_DTYPE = torch.float32


MAX_NEW_TOKENS = 1600
MAX_PROMPT_LENGTH = 5000

_tokenizer = None
_model = None

# Protect model initialization.
_model_load_lock = threading.Lock()

# Limit simultaneous inference in each worker process.
_generation_lock = threading.Lock()


SYSTEM = """
You are an expert technical writer who creates high-quality,
technically accurate articles for Medium.

Write a complete, original technical blog post about the user's topic.

OUTPUT REQUIREMENTS:

1. The first line must be:
   TITLE: <descriptive title>

2. Target 600-800 words for the article body, excluding the title.

3. Begin with an engaging introduction explaining the topic and
   why it matters.

4. Use several well-organized Markdown sections with ## headings.

5. Explain the important concepts clearly, with practical examples.

6. Include relevant Python code blocks when appropriate.
   Use fenced Markdown code blocks with language identifiers.

7. Explain the code, its purpose, and important implementation details.

8. Include common mistakes, best practices, and trade-offs where useful.

9. End with a meaningful conclusion and practical takeaways.

10. Use valid Markdown and avoid repetitive explanations or filler.

COMPLETENESS:

- Include an introduction, substantive main sections, examples where
  relevant, and a conclusion.
- Finish every code block.
- Finish every sentence and section.
- Reserve enough space for the conclusion.
- Never intentionally stop in the middle of a sentence or code block.
- Do not add commentary about these instructions.
- Do not fabricate technical facts.

Return the title and complete article, starting with the TITLE line.
"""


def get_model():
    """Initialize the model once per process."""

    global _tokenizer, _model

    if _model is None:
        with _model_load_lock:
            if _model is None:
                logger.info("Loading blog generation model...")

                start = time.perf_counter()

                tokenizer = AutoTokenizer.from_pretrained(
                    MODEL_ID
                )

                model = AutoModelForCausalLM.from_pretrained(
                    MODEL_ID,
                    torch_dtype=MODEL_DTYPE,
                    low_cpu_mem_usage=True,
                    attn_implementation="sdpa",
                )

                model.to(DEVICE)
                model.eval()

                # Publish only after initialization succeeds.
                _tokenizer = tokenizer
                _model = model

                logger.info(
                    "Model loaded in %.2f seconds on %s",
                    time.perf_counter() - start,
                    DEVICE,
                )

    return _tokenizer, _model


def extract_article(raw, fallback_title):
    """Extract the title and article body from generated Markdown."""

    raw = raw.strip()

    match = re.match(
        r"^\s*TITLE:\s*(.+?)\s*$",
        raw,
        flags=re.MULTILINE,
    )

    if match:
        title = match.group(1).strip()
        body_md = raw[match.end():].strip()
    else:
        title = fallback_title[:120]
        body_md = raw

    # Remove an accidental duplicate title at the beginning.
    body_md = re.sub(
        r"^\s*TITLE:\s*[^\n]+\s*\n?",
        "",
        body_md,
        count=1,
    ).strip()

    # Remove a repeated H1 title if the model adds one.
    body_md = re.sub(
        r"^\s*#\s+" + re.escape(title) + r"\s*\n+",
        "",
        body_md,
        count=1,
        flags=re.IGNORECASE,
    ).strip()

    return title, body_md


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

        if len(prompt) > MAX_PROMPT_LENGTH:
            return Response(
                {
                    "error": (
                        f"Prompt cannot exceed "
                        f"{MAX_PROMPT_LENGTH} characters."
                    )
                },
                status=400,
            )

        request_start = time.perf_counter()

        try:
            model_start = time.perf_counter()

            tokenizer, model = get_model()

            model_ready_time = time.perf_counter()

            messages = [
                {
                    "role": "system",
                    "content": SYSTEM,
                },
                {
                    "role": "user",
                    "content": (
                        "Write a complete technical blog post about "
                        f"the following topic:\n{prompt}"
                    ),
                },
            ]

            # Apply the model's native chat template.
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

            # Serialize inference within this process.
            with _generation_lock:
                generation_start = time.perf_counter()

                with torch.inference_mode():
                    output = model.generate(
                        **inputs,
                        max_new_tokens=MAX_NEW_TOKENS,
                        do_sample=False,
                        use_cache=True,
                        pad_token_id=(
                            tokenizer.pad_token_id
                            if tokenizer.pad_token_id is not None
                            else tokenizer.eos_token_id
                        ),
                        eos_token_id=tokenizer.eos_token_id,
                    )

                # CUDA operations are asynchronous. Synchronize before
                # measuring generation latency on a GPU.
                if DEVICE.type == "cuda":
                    torch.cuda.synchronize()

                generation_end = time.perf_counter()

            generated_tokens = output[0, input_length:]

            raw = tokenizer.decode(
                generated_tokens,
                skip_special_tokens=True,
            ).strip()

            title, body_md = extract_article(
                raw,
                prompt,
            )

            # Convert generated Markdown into HTML.
            html = markdown.markdown(
                body_md,
                extensions=[
                    "fenced_code",
                    "tables",
                ],
            )

            word_count = len(body_md.split())

            # Log short output for diagnostics. Do not automatically
            # regenerate every short article: retries add latency.
            if word_count < 500:
                logger.warning(
                    "Short article generated: %d words",
                    word_count,
                )

            if not body_md:
                logger.warning(
                    "Model returned an empty article body."
                )

                return Response(
                    {
                        "error": (
                            "The model could not generate an article. "
                            "Please try again."
                        )
                    },
                    status=502,
                )

            logger.info(
                "Blog metrics: "
                "model_ready=%.2fs, "
                "generation=%.2fs, "
                "total=%.2fs, "
                "input_tokens=%d, "
                "output_tokens=%d, "
                "words=%d, "
                "device=%s",
                model_ready_time - model_start,
                generation_end - generation_start,
                time.perf_counter() - request_start,
                input_length,
                len(generated_tokens),
                word_count,
                DEVICE,
            )

            return Response(
                {
                    "title": title,
                    "html": html or "<p></p>",
                }
            )

        except Exception:
            logger.exception("Blog generation failed")

            return Response(
                {
                    "error": "Failed to generate blog post."
                },
                status=500,
            )
# -------------------- Try 3.0---------------------#
