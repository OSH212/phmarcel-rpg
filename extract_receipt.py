#!/usr/bin/env python3
"""Extract fields from receipt sample."""

import json
import sys
import torch
import warnings
from pathlib import Path
from transformers import Qwen3VLForConditionalGeneration, AutoProcessor
from PIL import Image

if len(sys.argv) < 2:
    print("Usage: python extract_receipt.py <receipt_path>")
    print("Example: python extract_receipt.py sample_docs/receipts/001.jpg")
    sys.exit(1)

print("=" * 70)
print("🔧 IMAGE PREPROCESSING")
print("=" * 70)

# CONVERT IMAGE FIRST - BEFORE LOADING MODEL
image_path = sys.argv[1]
print(f"📥 Original path: {image_path}")

# Suppress PIL palette transparency warning
warnings.filterwarnings('ignore', category=UserWarning, module='PIL.Image')

# Load and preprocess image
image = Image.open(image_path)
print(f"📊 Original size: {image.size}, mode: {image.mode}, format: {image.format}")

# Convert palette images to RGBA first to avoid transparency issues
if image.mode == 'P':
    print("🔄 Converting palette mode to RGBA...")
    image = image.convert('RGBA')

# Resize if too large (max 1536 on longest side to avoid OOM on T4 GPU)
max_size = 1536
if max(image.size) > max_size:
    ratio = max_size / max(image.size)
    new_size = tuple(int(dim * ratio) for dim in image.size)
    print(f"📏 Resizing from {image.size} to {new_size} (ratio: {ratio:.3f})")
    image = image.resize(new_size, Image.Resampling.LANCZOS)
    print(f"✅ Resized to: {image.size}")

# Convert to RGB (JPG format) - NOT PDF
if image.mode != 'RGB':
    print(f"🔄 Converting {image.mode} to RGB...")
    image = image.convert('RGB')

# Save as temporary JPG
temp_jpg = Path("temp_converted.jpg")
image.save(temp_jpg, 'JPEG', quality=95)
print(f"💾 Saved as: {temp_jpg} ({temp_jpg.stat().st_size / 1024:.1f} KB)")
image_path = str(temp_jpg)

# Verify converted image
verify_img = Image.open(image_path)
print(f"✅ Verified converted: {verify_img.size}, mode: {verify_img.mode}, format: {verify_img.format}")
print(f"📍 Using image path: {image_path}")

print("\n" + "=" * 70)
print("🤖 LOADING MODEL")
print("=" * 70)

# NOW load model with converted image ready
model = Qwen3VLForConditionalGeneration.from_pretrained(
    "Qwen/Qwen3-VL-2B-Instruct", dtype="auto", device_map="auto"
)
print(f"✅ Model loaded on {model.device}")

processor = AutoProcessor.from_pretrained("Qwen/Qwen3-VL-2B-Instruct")
print("✅ Processor loaded")

prompt = """Extract all sections and text from this receipt image.

CRITICAL INSTRUCTIONS:
- Raw extraction only - NO modification, NO summarization, NO interpretation
- Extract exact values as they appear - preserve currency symbols, decimals, formatting
- Do not calculate, convert, or transform any values
- If a field is empty or not visible, use null

Extract ALL visible fields and return as JSON with these keys:
- merchant_name
- total_amount
- date
- time
- address
- phone
- subtotal
- tax
- payment_method
- transaction_id
- any other visible fields

Return ONLY valid JSON. No additional text or explanation."""

print("\n" + "=" * 70)
print("🚀 EXTRACTION")
print("=" * 70)

messages = [
    {
        "role": "user",
        "content": [
            {"type": "image", "image": image_path},
            {"type": "text", "text": prompt},
        ],
    }
]

print("🔄 Applying chat template...")
inputs = processor.apply_chat_template(
    messages, tokenize=True, add_generation_prompt=True,
    return_dict=True, return_tensors="pt"
)
print(f"📊 Input shape: {inputs.input_ids.shape}")

print("🔄 Moving inputs to GPU...")
inputs = inputs.to(model.device)

print("🧠 Generating extraction (this may take 30-60 seconds)...")
with torch.no_grad():
    generated_ids = model.generate(
        **inputs, max_new_tokens=2048, top_p=0.8, top_k=20,
        temperature=0.7, repetition_penalty=1.0, use_cache=False
    )
print("✅ Generation complete")

print("🔄 Decoding output...")
generated_ids_trimmed = [
    out_ids[len(in_ids):]
    for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
]

output_text = processor.batch_decode(
    generated_ids_trimmed, skip_special_tokens=True,
    clean_up_tokenization_spaces=False
)[0]

print("\n" + "=" * 70)
print("📄 EXTRACTION RESULT")
print("=" * 70)
print(output_text)
print("=" * 70)

# Save
output_dir = Path("extractions/qwen3vl_tests")
output_dir.mkdir(parents=True, exist_ok=True)

receipt_name = Path(image_path).stem

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
    output_file = output_dir / f"receipt_{receipt_name}_extraction.json"
    with open(output_file, 'w') as f:
        json.dump(result_json, f, indent=2)
    print(f"\n✅ Saved to: {output_file}")
except json.JSONDecodeError as e:
    print(f"\n⚠️  JSON parse error: {e}")
    output_file = output_dir / f"receipt_{receipt_name}_extraction.txt"
    with open(output_file, 'w') as f:
        f.write(output_text)

