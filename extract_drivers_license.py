#!/usr/bin/env python3
"""Extract fields from driver's license sample."""

import json
import torch
from pathlib import Path
from transformers import Qwen3VLForConditionalGeneration, AutoProcessor
from PIL import Image

# CONVERT IMAGE FIRST - BEFORE LOADING MODEL
image_path = "sample_docs/drivers_license.jpg"

# Load and preprocess image
image = Image.open(image_path)

# Resize if too large (max 2048 on longest side to avoid OOM)
max_size = 2048
if max(image.size) > max_size:
    ratio = max_size / max(image.size)
    new_size = tuple(int(dim * ratio) for dim in image.size)
    image = image.resize(new_size, Image.Resampling.LANCZOS)

# Convert any non-JPG to RGB (JPG format) - NOT PDF
if image.format != 'JPEG' or image.mode != 'RGB':
    image = image.convert('RGB')

# Save as temporary JPG
temp_jpg = Path("temp_converted.jpg")
image.save(temp_jpg, 'JPEG', quality=95)
image_path = str(temp_jpg)

# NOW load model with converted image ready
model = Qwen3VLForConditionalGeneration.from_pretrained(
    "Qwen/Qwen3-VL-2B-Instruct", dtype="auto", device_map="auto"
)
processor = AutoProcessor.from_pretrained("Qwen/Qwen3-VL-2B-Instruct")

prompt = """Extract all sections and text from this driver's license / ID card image.

CRITICAL INSTRUCTIONS:
- Raw extraction only - NO modification, NO summarization, NO interpretation
- Extract exact values as they appear - preserve all formatting
- Do not calculate, convert, or transform any values
- If a field is empty or not visible, use null

Extract ALL visible fields and return as JSON with these keys:
- full_name
- date_of_birth
- id_number (license number)
- address
- expiry_date
- issue_date
- sex
- height
- eye_color
- class (license class)
- any other visible fields

Return ONLY valid JSON. No additional text or explanation."""

messages = [
    {
        "role": "user",
        "content": [
            {"type": "image", "image": image_path},
            {"type": "text", "text": prompt},
        ],
    }
]

inputs = processor.apply_chat_template(
    messages, tokenize=True, add_generation_prompt=True,
    return_dict=True, return_tensors="pt"
)
inputs = inputs.to(model.device)

with torch.no_grad():
    generated_ids = model.generate(
        **inputs, max_new_tokens=2048, top_p=0.8, top_k=20,
        temperature=0.7, repetition_penalty=1.0
    )

generated_ids_trimmed = [
    out_ids[len(in_ids):] 
    for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
]

output_text = processor.batch_decode(
    generated_ids_trimmed, skip_special_tokens=True,
    clean_up_tokenization_spaces=False
)[0]

print(output_text)

# Save
output_dir = Path("extractions/qwen3vl_tests")
output_dir.mkdir(parents=True, exist_ok=True)

clean_result = output_text.strip()
if clean_result.startswith("```json"):
    clean_result = clean_result[7:]
if clean_result.startswith("```"):
    clean_result = clean_result[3:]
if clean_result.endswith("```"):
    clean_result = clean_result[:-3]
clean_result = clean_result.strip()

try:
    result_json = json.loads(clean_result)
    with open(output_dir / "drivers_license_extraction.json", 'w') as f:
        json.dump(result_json, f, indent=2)
    print(f"\n✅ Saved to: {output_dir / 'drivers_license_extraction.json'}")
except json.JSONDecodeError as e:
    print(f"\n⚠️  JSON parse error: {e}")
    with open(output_dir / "drivers_license_extraction.txt", 'w') as f:
        f.write(output_text)

