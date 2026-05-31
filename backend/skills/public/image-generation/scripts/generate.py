import binascii
import mimetypes
import os

import requests
from dashscope import MultiModalConversation
from PIL import Image


def validate_image(image_path: str) -> bool:
    """
    Validate if an image file can be opened and is not corrupted.

    Args:
        image_path: Path to the image file

    Returns:
        True if the image is valid and can be opened, False otherwise
    """
    try:
        with Image.open(image_path) as img:
            img.verify()  # Verify that it's a valid image
        # Re-open to check if it can be fully loaded (verify() may not catch all issues)
        with Image.open(image_path) as img:
            img.load()  # Force load the image data
        return True
    except Exception as e:
        print(f"Warning: Image '{image_path}' is invalid or corrupted: {e}")
        return False


def generate_image(
    prompt_file: str,
    reference_images: list[str],
    output_file: str,
    aspect_ratio: str = "16:9",
) -> str:
    with open(prompt_file, encoding="utf-8") as f:
        prompt = f.read()
    content_parts: list[dict[str, str]] = []

    # Filter out invalid reference images
    valid_reference_images = []
    for ref_img in reference_images:
        if validate_image(ref_img):
            valid_reference_images.append(ref_img)
        else:
            print(f"Skipping invalid reference image: {ref_img}")

    if len(valid_reference_images) < len(reference_images):
        print(
            f"Note: {len(reference_images) - len(valid_reference_images)} reference image(s) were skipped due to validation failure."
        )

    for reference_image in valid_reference_images:
        mime_type, _ = mimetypes.guess_type(reference_image)
        if not mime_type:
            mime_type = "image/jpeg"
        with open(reference_image, "rb") as f:
            image_b64 = binascii.b2a_base64(f.read(), newline=False).decode("utf-8")
        content_parts.append({"image": f"data:{mime_type};base64,{image_b64}"})

    content_parts.append({"text": prompt})

    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        return "DASHSCOPE_API_KEY is not set"

    size_map = {
        "1:1": "1024*1024",
        "16:9": "1280*720",
        "9:16": "720*1280",
        "4:3": "960*720",
        "3:4": "720*960",
    }
    size = size_map.get(aspect_ratio, "1024*1024")

    response = MultiModalConversation.call(
        api_key=api_key,
        model="qwen-image-2.0",
        messages=[{"role": "user", "content": content_parts}],
        result_format="message",
        stream=False,
        n=1,
        watermark=True,
        negative_prompt="",
        size=size,
    )
    status_code = getattr(response, "status_code", None)
    if status_code not in (None, 200):
        error_message = getattr(response, "message", None) or getattr(
            response, "code", "unknown_error"
        )
        raise Exception(f"Failed to generate image: {error_message}")

    response_dict = response if isinstance(response, dict) else response.to_dict()
    choices = response_dict.get("output", {}).get("choices", [])
    if not choices:
        raise Exception("Failed to generate image: empty output choices")

    message = choices[0].get("message", {})
    generated_parts = message.get("content", [])
    if not generated_parts:
        raise Exception("Failed to generate image: empty message content")

    image_url = None
    image_b64 = None
    for part in generated_parts:
        if isinstance(part, dict):
            if isinstance(part.get("image"), str):
                image_url = part["image"]
                break
            if isinstance(part.get("image_url"), str):
                image_url = part["image_url"]
                break
            if isinstance(part.get("image_base64"), str):
                image_b64 = part["image_base64"]
                break

    if image_url:
        image_response = requests.get(image_url, timeout=30)
        image_response.raise_for_status()
        with open(output_file, "wb") as f:
            f.write(image_response.content)
        return f"Successfully generated image to {output_file}"

    if image_b64:
        with open(output_file, "wb") as f:
            f.write(binascii.a2b_base64(image_b64))
        return f"Successfully generated image to {output_file}"

    raise Exception("Failed to generate image: no image content found")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate images using qwen-image-2.0")
    parser.add_argument(
        "--prompt-file",
        required=True,
        help="Absolute path to JSON prompt file",
    )
    parser.add_argument(
        "--reference-images",
        nargs="*",
        default=[],
        help="Absolute paths to reference images (space-separated)",
    )
    parser.add_argument(
        "--output-file",
        required=True,
        help="Output path for generated image",
    )
    parser.add_argument(
        "--aspect-ratio",
        required=False,
        default="16:9",
        help="Aspect ratio of the generated image",
    )

    args = parser.parse_args()

    try:
        print(
            generate_image(
                args.prompt_file,
                args.reference_images,
                args.output_file,
                args.aspect_ratio,
            )
        )
    except Exception as e:
        print(f"Error while generating image: {e}")
