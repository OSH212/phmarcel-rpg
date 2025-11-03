#!/usr/bin/env python3
"""
Test Qwen3-VL-2B-Instruct model for T4 tax form extraction.
Goal: Extract ALL fields with 100% accuracy (not just the 3 required fields).
"""

import json
import torch
from pathlib import Path
from transformers import Qwen3VLForConditionalGeneration, AutoProcessor
from PIL import Image

# T4 Schema - ALL fields we want to extract
T4_SCHEMA = {
    "employer_info": {
        "employer_name": "string",
        "employer_address_line1": "string",
        "employer_address_line2": "string",
        "employer_account_number": "string"
    },
    "employee_info": {
        "employee_name": "string",
        "employee_address_line1": "string",
        "employee_address_line2": "string",
        "social_insurance_number": "string"
    },
    "year": "string",
    "boxes": {
        "box_12": {"label": "Social insurance number", "value": "string"},
        "box_14": {"label": "Employment income", "value": "string"},
        "box_16": {"label": "Employee's CPP contributions", "value": "string"},
        "box_17": {"label": "Employee's QPP contributions", "value": "string"},
        "box_18": {"label": "Employee's EI premiums", "value": "string"},
        "box_20": {"label": "RPP contributions", "value": "string"},
        "box_22": {"label": "Income tax deducted", "value": "string"},
        "box_24": {"label": "EI insurable earnings", "value": "string"},
        "box_26": {"label": "CPP/QPP pensionable earnings", "value": "string"},
        "box_28": {"label": "CPP/QPP Exempt", "value": "string"},
        "box_29": {"label": "Employment code", "value": "string"},
        "box_44": {"label": "Union dues", "value": "string"},
        "box_46": {"label": "Charitable donations", "value": "string"},
        "box_50": {"label": "RPP or DPSP registration number", "value": "string"},
        "box_52": {"label": "Pension adjustment", "value": "string"},
        "box_55": {"label": "Employee's PPIP premiums", "value": "string"},
        "box_56": {"label": "PPIP insurable earnings", "value": "string"},
        "box_30": {"label": "Other information", "value": "string"},
        "box_36": {"label": "Other information", "value": "string"},
        "box_39": {"label": "Other information", "value": "string"},
        "box_57": {"label": "Other information", "value": "string"},
        "box_77": {"label": "Other information", "value": "string"},
        "box_91": {"label": "Other information", "value": "string"}
    }
}

def create_extraction_prompt():
    """Create prompt that emphasizes raw extraction with no modifications."""
    
    schema_json = json.dumps(T4_SCHEMA, indent=2)
    
    prompt = f"""Extract all sections and text from this T4 tax form image. 

CRITICAL INSTRUCTIONS:
- Raw extraction only - NO modification, NO summarization, NO interpretation
- Extract exact values as they appear - preserve all numbers, decimals, formatting
- Do not calculate, convert, or transform any values
- If a field is empty or not visible, use null
- Return data in the exact JSON schema provided below

SCHEMA:
{schema_json}

Extract ALL fields from the image and return ONLY valid JSON matching this schema. No additional text or explanation."""
    
    return prompt

def load_model():
    """Load Qwen3-VL model and processor."""
    print("🔧 Loading Qwen3-VL-2B-Instruct model...")
    
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        "Qwen/Qwen3-VL-2B-Instruct",
        dtype="auto",
        device_map="auto"
    )
    
    processor = AutoProcessor.from_pretrained("Qwen/Qwen3-VL-2B-Instruct")
    
    print(f"✅ Model loaded on {model.device}")
    return model, processor

def extract_t4_fields(model, processor, image_path: str):
    """Extract T4 fields using Qwen3-VL."""
    
    print(f"\n📄 Processing: {image_path}")
    
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

    print(f"   Image size: {image.size}")
    
    # Create prompt
    prompt = create_extraction_prompt()
    
    # Prepare messages in chat format
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image_path},
                {"type": "text", "text": prompt},
            ],
        }
    ]
    
    # Process inputs
    print("🔄 Preparing inputs...")
    inputs = processor.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_dict=True,
        return_tensors="pt"
    )
    inputs = inputs.to(model.device)
    
    # Generate extraction
    print("🚀 Running extraction (this may take 1-2 minutes)...")
    with torch.no_grad():
        generated_ids = model.generate(
            **inputs,
            max_new_tokens=4096,  # Large enough for all T4 fields
            top_p=0.8,
            top_k=20,
            temperature=0.7,
            repetition_penalty=1.0
        )
    
    # Decode output
    generated_ids_trimmed = [
        out_ids[len(in_ids):] 
        for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
    ]
    
    output_text = processor.batch_decode(
        generated_ids_trimmed,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False
    )[0]
    
    return output_text

def main():
    print("=" * 60)
    print("🚀 QWEN3-VL T4 EXTRACTION TEST")
    print("=" * 60)
    print("Goal: Extract ALL T4 fields with 100% accuracy")
    print("Model: Qwen3-VL-2B-Instruct")
    print("=" * 60)
    
    # Load model
    model, processor = load_model()
    
    # Test on T4 sample
    image_path = "sample_docs/T4_sample.JPG"
    
    if not Path(image_path).exists():
        print(f"❌ ERROR: {image_path} not found!")
        return
    
    # Extract
    result = extract_t4_fields(model, processor, image_path)
    
    # Display results
    print("\n" + "=" * 60)
    print("📊 EXTRACTION RESULTS")
    print("=" * 60)
    print(result)
    print("=" * 60)
    
    # Save results
    output_dir = Path("extractions/qwen3vl_tests")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / "t4_extraction_test1.json"
    
    # Try to parse as JSON (strip markdown code fences if present)
    try:
        # Remove markdown code fences
        clean_result = result.strip()
        if clean_result.startswith("```json"):
            clean_result = clean_result[7:]  # Remove ```json
        if clean_result.startswith("```"):
            clean_result = clean_result[3:]  # Remove ```
        if clean_result.endswith("```"):
            clean_result = clean_result[:-3]  # Remove trailing ```
        clean_result = clean_result.strip()

        result_json = json.loads(clean_result)
        with open(output_file, 'w') as f:
            json.dump(result_json, f, indent=2)
        print(f"\n✅ Results saved to: {output_file}")

        # Quick analysis
        print("\n📈 QUICK ANALYSIS:")
        if "boxes" in result_json:
            filled_boxes = sum(1 for box, data in result_json["boxes"].items()
                             if data.get("value") not in [None, "", "null"])
            print(f"   Boxes extracted: {filled_boxes}/{len(result_json['boxes'])}")

        # Verify critical fields (challenge requirement: 3 fields)
        print("\n🎯 CRITICAL FIELDS (Challenge Requirements):")
        critical_fields = {
            "employer_name": result_json.get("employer_info", {}).get("employer_name"),
            "box_14_employment_income": result_json.get("boxes", {}).get("box_14", {}).get("value"),
            "box_22_income_tax_deducted": result_json.get("boxes", {}).get("box_22", {}).get("value")
        }
        for field, value in critical_fields.items():
            status = "✅" if value else "❌"
            print(f"   {status} {field}: {value}")

    except json.JSONDecodeError as e:
        print(f"\n⚠️  WARNING: Output is not valid JSON")
        print(f"   Error: {e}")
        # Save as text
        with open(output_file.with_suffix('.txt'), 'w') as f:
            f.write(result)
        print(f"   Raw output saved to: {output_file.with_suffix('.txt')}")

if __name__ == "__main__":
    main()

