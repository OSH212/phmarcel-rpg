"""
DEPRECATED. NOT USING PADDLE-OCR-VL ANYMORE.
Test different PaddleOCR-VL parameters to achieve 100% field extraction.

This script tests various parameter combinations to find the optimal settings
for extracting ALL fields from T4 forms, driver's licenses, and receipts.
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from paddleocr import PaddleOCRVL


def test_parameters(image_path: str, test_name: str, **kwargs):
    """Test extraction with specific parameters."""
    print(f"\n{'='*80}")
    print(f"TEST: {test_name}")
    print(f"Image: {image_path}")
    print(f"Parameters: {kwargs}")
    print('='*80)
    
    pipeline = PaddleOCRVL(use_layout_detection=True)
    output = pipeline.predict(image_path, **kwargs)
    
    res = output[0]
    result_dict = res.json.get('res', {})
    parsing_res = result_dict.get('parsing_res_list', [])
    layout_boxes = result_dict.get('layout_det_res', {}).get('boxes', [])
    
    # Combine all text
    text_parts = [block.get('block_content', '') for block in parsing_res]
    full_text = "\n".join(text_parts)
    
    print(f"\n✅ RESULTS:")
    print(f"   Layout boxes detected: {len(layout_boxes)}")
    print(f"   Text blocks extracted: {len(parsing_res)}")
    print(f"   Total text length: {len(full_text)} chars")
    
    print(f"\n📊 Layout Detection Boxes:")
    for i, box in enumerate(layout_boxes[:10]):  # Show first 10
        print(f"   {i+1}. {box['label']:15s} (score: {box['score']:.3f})")
    if len(layout_boxes) > 10:
        print(f"   ... and {len(layout_boxes) - 10} more boxes")
    
    print(f"\n📝 Extracted Text Blocks:")
    for i, block in enumerate(parsing_res[:10]):  # Show first 10
        content = block.get('block_content', '')[:60].replace('\n', ' ')
        print(f"   {i+1}. [{block.get('block_label')}]: {content}...")
    if len(parsing_res) > 10:
        print(f"   ... and {len(parsing_res) - 10} more blocks")
    
    # Save results
    output_dir = Path("extractions/parameter_tests")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{test_name}.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            "test_name": test_name,
            "image_path": image_path,
            "parameters": kwargs,
            "num_layout_boxes": len(layout_boxes),
            "num_text_blocks": len(parsing_res),
            "text_length": len(full_text),
            "layout_boxes": layout_boxes,
            "text_blocks": parsing_res,
            "full_text": full_text
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Saved to: {output_file}")
    
    return {
        "num_boxes": len(layout_boxes),
        "num_blocks": len(parsing_res),
        "text_length": len(full_text)
    }


def main():
    """Run parameter tuning tests."""
    
    print("="*80)
    print("PADDLEOCR-VL PARAMETER TUNING FOR 100% FIELD EXTRACTION")
    print("="*80)
    
    test_image = "sample_docs/T4_sample.JPG"
    
    results = []
    
    # Test 1: Baseline (current settings)
    results.append(("Baseline (default)", test_parameters(
        test_image,
        "01_baseline",
    )))
    
    # Test 2: Lower layout threshold (detect more boxes)
    results.append(("Lower threshold (0.3)", test_parameters(
        test_image,
        "02_low_threshold",
        layout_threshold=0.3
    )))
    
    # Test 3: Even lower threshold
    results.append(("Very low threshold (0.1)", test_parameters(
        test_image,
        "03_very_low_threshold",
        layout_threshold=0.1
    )))
    
    # Test 4: Increase unclip ratio (expand boxes)
    results.append(("Unclip ratio 2.0", test_parameters(
        test_image,
        "04_unclip_2",
        layout_unclip_ratio=2.0
    )))
    
    # Test 5: Combination - low threshold + high unclip
    results.append(("Low threshold + unclip", test_parameters(
        test_image,
        "05_combined",
        layout_threshold=0.2,
        layout_unclip_ratio=2.0
    )))
    
    # Test 6: Disable NMS (keep all boxes)
    results.append(("Disable NMS", test_parameters(
        test_image,
        "06_no_nms",
        layout_nms=False
    )))
    
    # Test 7: Use prompt to guide extraction
    results.append(("With prompt", test_parameters(
        test_image,
        "07_with_prompt",
        prompt_label="Extract all form fields, labels, and values from this tax document"
    )))
    
    # Test 8: Kitchen sink - all optimizations
    results.append(("All optimizations", test_parameters(
        test_image,
        "08_all_optimizations",
        layout_threshold=0.1,
        layout_unclip_ratio=2.5,
        layout_nms=False,
        prompt_label="Extract all text, form fields, labels, and values"
    )))
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY - Parameter Tuning Results")
    print("="*80)
    print(f"\n{'Test Name':<30s} {'Boxes':>8s} {'Blocks':>8s} {'Text Len':>10s}")
    print("-"*80)
    
    for name, result in results:
        print(f"{name:<30s} {result['num_boxes']:>8d} {result['num_blocks']:>8d} {result['text_length']:>10d}")
    
    # Find best
    best = max(results, key=lambda x: x[1]['num_blocks'])
    print(f"\n🏆 BEST RESULT: {best[0]}")
    print(f"   Extracted {best[1]['num_blocks']} text blocks ({best[1]['text_length']} chars)")
    
    print("\n" + "="*80)
    print("✅ All test results saved to extractions/parameter_tests/")
    print("   Review JSON files to verify extraction completeness")
    print("="*80)


if __name__ == "__main__":
    main()

