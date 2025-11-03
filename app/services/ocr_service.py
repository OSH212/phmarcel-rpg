"""
OCR and document classification service using PaddleOCR-VL
THIS FILE IS DEPRECATED. NOT USING PADDLE-OCR-VL ANYMORE.
"""
import json
from pathlib import Path
from typing import Tuple, Optional, Dict, List
from paddleocr import PaddleOCRVL
from app.models.enums import DocKind


class OCRService:
    """
    Service for OCR text extraction and document classification.

    Uses PaddleOCR-VL with layout detection (PP-DocLayoutV2 + PaddleOCR-VL-0.9B).
    Layout detection is REQUIRED to prevent T4 GPU crashes.
    """

    def __init__(self):
        """
        Initialize PaddleOCR-VL pipeline with layout detection enabled.

        Note: use_layout_detection=True is critical for T4 GPU stability.
        """
        self.pipeline = PaddleOCRVL(use_layout_detection=True)

    def extract_document_data(self, image_path: str) -> Dict:
        """
        Extract structured data from document using PaddleOCR-VL.

        Args:
            image_path: Path to the image or PDF file

        Returns:
            Dict with 'text', 'layout_blocks', and 'raw_result'
        """
        try:
            output = self.pipeline.predict(image_path)

            if not output or len(output) == 0:
                return {"text": "", "layout_blocks": [], "raw_result": None}

            # Get first page result
            res = output[0]
            # Access result via res.json['res'] (not res.res)
            result_dict = res.json.get('res', {})

            # Extract parsing results
            parsing_res = result_dict.get('parsing_res_list', [])

            # Combine all block content into full text
            text_parts = [block.get('block_content', '') for block in parsing_res]
            full_text = "\n".join(text_parts)

            return {
                "text": full_text,
                "layout_blocks": parsing_res,
                "raw_result": result_dict
            }
        except Exception as e:
            raise RuntimeError(f"OCR extraction failed for {image_path}: {str(e)}")
    
    def classify_document(self, image_path: str) -> Tuple[DocKind, float, str]:
        """
        Classify document type and extract text using PaddleOCR-VL.

        Extracts text using PaddleOCR-VL, then classifies based on content.

        Args:
            image_path: Path to the document file

        Returns:
            Tuple of (DocKind, confidence_score, extracted_text)
        """
        doc_data = self.extract_document_data(image_path)
        text = doc_data["text"]

        text_lower = text.lower()

        t4_keywords = [
            't4', 'statement of remuneration', 'employment income',
            'box 14', 'box 22', 'canada revenue', 'revenus d\'emploi',
            'income tax deducted', 'employer name', 'employee name'
        ]

        id_keywords = [
            'driver', 'license', 'licence', 'date of birth', 'dob',
            'identification', 'id number', 'expires', 'issued',
            'class', 'restrictions', 'height', 'eyes', 'sex'
        ]

        receipt_keywords = [
            'receipt', 'total', 'subtotal', 'tax', 'amount',
            'merchant', 'payment', 'transaction', 'purchase',
            'paid', 'balance', 'change', 'cash', 'credit'
        ]

        t4_score = sum(1 for kw in t4_keywords if kw in text_lower)
        id_score = sum(1 for kw in id_keywords if kw in text_lower)
        receipt_score = sum(1 for kw in receipt_keywords if kw in text_lower)

        max_score = max(t4_score, id_score, receipt_score)

        if max_score == 0:
            return DocKind.UNKNOWN, 0.0, text

        if t4_score == max_score and t4_score >= 2:
            confidence = min(0.95, 0.5 + (t4_score * 0.05))
            return DocKind.T4, confidence, text

        if id_score == max_score and id_score >= 2:
            confidence = min(0.95, 0.5 + (id_score * 0.05))
            return DocKind.ID, confidence, text

        if receipt_score == max_score and receipt_score >= 2:
            confidence = min(0.95, 0.5 + (receipt_score * 0.05))
            return DocKind.RECEIPT, confidence, text

        return DocKind.UNKNOWN, 0.3, text

    def extract_and_save(self, image_path: str, output_dir: str = "extractions") -> Dict:
        """
        Extract document data and save to JSON file for verification.

        Args:
            image_path: Path to the document file
            output_dir: Directory to save extraction results

        Returns:
            Dict with extraction results
        """
        doc_data = self.extract_document_data(image_path)

        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        # Generate output filename (same as input but .json)
        input_file = Path(image_path)
        output_file = output_path / f"{input_file.stem}.json"

        # Prepare output data
        output_data = {
            "source_file": str(image_path),
            "extracted_text": doc_data["text"],
            "layout_blocks": doc_data["layout_blocks"],
            "model_settings": doc_data["raw_result"].get("model_settings", {}),
            "layout_detection_boxes": doc_data["raw_result"].get("layout_det_res", {}).get("boxes", [])
        }

        # Save to JSON
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        return {
            "output_file": str(output_file),
            "text_length": len(doc_data["text"]),
            "num_blocks": len(doc_data["layout_blocks"]),
            "num_layout_boxes": len(output_data["layout_detection_boxes"])
        }


_ocr_service_instance: Optional[OCRService] = None


def get_ocr_service() -> OCRService:
    """
    Get singleton instance of OCRService.
    
    Returns:
        OCRService instance
    """
    global _ocr_service_instance
    if _ocr_service_instance is None:
        _ocr_service_instance = OCRService()
    return _ocr_service_instance
