"""Qwen3-VL service for document classification and extraction."""

import json
import warnings
import torch
from pathlib import Path
from typing import Optional, Dict, Any
from PIL import Image
from pdf2image import convert_from_path
from transformers import Qwen3VLForConditionalGeneration, AutoProcessor

from app.schemas.extraction import T4Extraction, IDExtraction, ReceiptExtraction


class Qwen3VLService:
    """Singleton service for Qwen3-VL model operations."""
    
    _instance = None
    _model = None
    _processor = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._model is None:
            self._load_model()
    
    def _load_model(self):
        """Load Qwen3-VL model and processor (called once)."""
        print("🔧 Loading Qwen3-VL-2B-Instruct model...")
        self._model = Qwen3VLForConditionalGeneration.from_pretrained(
            "Qwen/Qwen3-VL-2B-Instruct", dtype="auto", device_map="auto"
        )
        self._processor = AutoProcessor.from_pretrained("Qwen/Qwen3-VL-2B-Instruct")
        print(f"✅ Model loaded on {self._model.device}")
    
    def preprocess_image(self, image_path: str) -> str:
        """Preprocess image: resize if needed, convert to JPG. Convert PDF to image if needed.

        Args:
            image_path: Path to original image or PDF

        Returns:
            Path to preprocessed image (may be temp file)
        """
        warnings.filterwarnings('ignore', category=UserWarning, module='PIL.Image')

        # Handle PDF files - convert directly to final format
        if image_path.lower().endswith('.pdf'):
            # Convert PDF to images (all pages, but we'll use first page for classification)
            images = convert_from_path(image_path, dpi=200)
            if not images:
                raise ValueError(f"Failed to convert PDF to image: {image_path}")

            image = images[0]  # Use first page

            # Convert to RGB if needed
            if image.mode == 'P':
                image = image.convert('RGBA').convert('RGB')
            elif image.mode != 'RGB':
                image = image.convert('RGB')

            # Resize if too large
            max_size = 1536
            if max(image.size) > max_size:
                ratio = max_size / max(image.size)
                new_size = tuple(int(dim * ratio) for dim in image.size)
                image = image.resize(new_size, Image.Resampling.LANCZOS)

            # Save as temp JPG
            temp_path = image_path.replace('.pdf', '_processed.jpg')
            image.save(temp_path, 'JPEG', quality=95)
            return temp_path

        image = Image.open(image_path)
        original_format = image.format
        original_size = image.size
        
        # Convert palette images to RGBA first
        if image.mode == 'P':
            image = image.convert('RGBA')
        
        # Resize if too large (max 1536 on longest side to avoid OOM on T4 GPU)
        max_size = 1536
        if max(image.size) > max_size:
            ratio = max_size / max(image.size)
            new_size = tuple(int(dim * ratio) for dim in image.size)
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        # Convert to RGB
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Save as temporary JPG if not already JPG or if resized
        if original_format != 'JPEG' or image.size != original_size:
            temp_jpg = Path(image_path).parent / f"temp_{Path(image_path).stem}.jpg"
            image.save(temp_jpg, 'JPEG', quality=95)
            return str(temp_jpg)
        
        return image_path
    
    def classify_document(self, image_path: str) -> str:
        """Classify document type.
        
        Args:
            image_path: Path to document image
            
        Returns:
            Document kind: "T4", "id", "receipt", or "unknown"
        """
        processed_path = self.preprocess_image(image_path)
        
        prompt = """Classify this document into ONE of these categories:
- T4: Canadian T4 tax form (Statement of Remuneration Paid)
- id: Government-issued ID (driver's license, passport, health card)
- receipt: Purchase receipt or invoice
- unknown: None of the above

Return ONLY the category name (T4, id, receipt, or unknown). No explanation."""
        
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": processed_path},
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        
        inputs = self._processor.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True,
            return_dict=True, return_tensors="pt"
        )
        inputs = inputs.to(self._model.device)
        
        with torch.no_grad():
            generated_ids = self._model.generate(
                **inputs, max_new_tokens=50, top_p=0.8, top_k=20,
                temperature=0.3, repetition_penalty=1.0, use_cache=False
            )
        
        generated_ids_trimmed = [
            out_ids[len(in_ids):] 
            for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        
        output_text = self._processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True,
            clean_up_tokenization_spaces=False
        )[0].strip().lower()
        
        # Clean up temp file if created
        if processed_path != image_path:
            Path(processed_path).unlink(missing_ok=True)
        
        # Map output to valid doc_kind
        if "t4" in output_text:
            return "T4"
        elif "id" in output_text or "license" in output_text or "passport" in output_text:
            return "id"
        elif "receipt" in output_text or "invoice" in output_text:
            return "receipt"
        else:
            return "unknown"
    
    def extract_t4(self, image_path: str) -> T4Extraction:
        """Extract fields from T4 tax form."""
        processed_path = self.preprocess_image(image_path)

        # Simplified schema - just show the structure, not full JSON schema
        prompt = """Extract all sections and text from this T4 tax form image.

CRITICAL INSTRUCTIONS:
- Raw extraction only - NO modification, NO summarization, NO interpretation
- Extract exact values as they appear - preserve all numbers, decimals, formatting
- Do not calculate, convert, or transform any values
- If a field is empty or not visible, use null
- Return data in the exact JSON schema provided below

SCHEMA:
{
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
        "box_56": {"label": "PPIP insurable earnings", "value": "string"}
    }
}

Extract ALL fields from the image and return ONLY valid JSON matching this schema. No additional text or explanation."""

        return self._extract_with_schema(processed_path, prompt, T4Extraction)
    
    def extract_id(self, image_path: str) -> IDExtraction:
        """Extract fields from ID/driver's license."""
        processed_path = self.preprocess_image(image_path)

        prompt = """Extract all visible fields from this ID/driver's license image.

CRITICAL INSTRUCTIONS:
- Raw extraction only - NO modification, NO summarization
- Extract exact values as they appear
- If a field is not visible, use null
- Return data in the exact JSON schema provided below

SCHEMA:
{
    "full_name": "string",
    "date_of_birth": "string",
    "id_number": "string",
    "expiry_date": "string",
    "address": "string",
    "sex": "string",
    "height": "string"
}

Extract ALL fields and return ONLY valid JSON. No additional text."""

        return self._extract_with_schema(processed_path, prompt, IDExtraction)
    
    def extract_receipt(self, image_path: str) -> ReceiptExtraction:
        """Extract fields from receipt."""
        processed_path = self.preprocess_image(image_path)

        prompt = """Extract all visible fields from this receipt image.

CRITICAL INSTRUCTIONS:
- Raw extraction only - NO modification
- Extract exact values - preserve currency symbols, decimals
- If a field is not visible, use null
- Return data in the exact JSON schema provided below

SCHEMA:
{
    "merchant_name": "string",
    "total_amount": "string",
    "date": "string",
    "items": "string"
}

Extract ALL fields and return ONLY valid JSON. No additional text."""

        return self._extract_with_schema(processed_path, prompt, ReceiptExtraction)
    
    def _extract_with_schema(self, image_path: str, prompt: str, schema_class):
        """Generic extraction with schema validation."""
        print(f"🔄 Starting extraction for {schema_class.__name__}")
        print(f"   Image: {image_path}")

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image_path},
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        print("🔄 Preparing inputs...")
        inputs = self._processor.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True,
            return_dict=True, return_tensors="pt"
        )
        inputs = inputs.to(self._model.device)
        print(f"   Input tokens: {inputs.input_ids.shape[1]}")

        print("🚀 Running model generation (this may take 1-2 minutes)...")
        with torch.no_grad():
            generated_ids = self._model.generate(
                **inputs, max_new_tokens=4096, top_p=0.8, top_k=20,
                temperature=0.7, repetition_penalty=1.0
            )
        print("✅ Generation complete")
        
        generated_ids_trimmed = [
            out_ids[len(in_ids):] 
            for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        
        output_text = self._processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True,
            clean_up_tokenization_spaces=False
        )[0]
        
        # Clean up temp file if created
        if image_path != image_path:
            Path(image_path).unlink(missing_ok=True)
        
        # Strip markdown code fences if present
        if output_text.startswith("```json"):
            output_text = output_text.split("```json")[1].split("```")[0].strip()
        elif output_text.startswith("```"):
            output_text = output_text.split("```")[1].split("```")[0].strip()
        
        # Parse and validate with Pydantic
        data = json.loads(output_text)
        return schema_class(**data)


# Global singleton instance
qwen3vl_service = Qwen3VLService()

