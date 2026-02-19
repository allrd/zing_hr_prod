import base64
import os

# ----------------------------
# SAFE DECRYPT FUNCTIONS
# ----------------------------

def safe_decrypt_text(enc_value):
    """
    Decrypts Base64 text safely.
    If invalid base64 -> returns empty string instead of crashing.
    """
    try:
        return base64.b64decode(enc_value).decode("utf-8")
    except:
        return ""


def safe_decrypt_file(enc_file_bytes):
    """
    Decrypts Base64 file bytes and returns raw file bytes.
    """
    try:
        return base64.b64decode(enc_file_bytes)
    except:
        return b""


# ----------------------------
# BASE64 IMAGE FUNCTIONS
# ----------------------------

def encode_image_to_base64(image_path):
    try:
        with open(image_path, "rb") as image_file:
            base64_string = base64.b64encode(image_file.read()).decode("utf-8")
        return base64_string

    except FileNotFoundError:
        return "Error: File not found!"
    except Exception as e:
        return f"Error: {e}"


def create_text_file(file_name, base64_string):
    try:
        # Save Base64 text
        with open(file_name, "w") as file:
            file.write(base64_string)

        print(f"✓ Base64 text file saved: {file_name}")

        # Decode Base64 → image
        output_image = os.path.join(os.path.dirname(file_name), "output_image.jpg")

        image_data = base64.b64decode(base64_string)

        with open(output_image, "wb") as img:
            img.write(image_data)

        print(f"✓ Image successfully saved: {output_image}")

    except Exception as e:
        print(f"Error: {e}")


def decode_base64_to_image(base64_string, output_file):
    try:
        image_data = base64.b64decode(base64_string)
        with open(output_file, "wb") as file:
            file.write(image_data)

        print(f"✓ Image saved: {output_file}")

    except Exception as e:
        print(f"Error: {e}")


# -------------------------
# DEMO RUN (optional)
# -------------------------
if __name__ == "__main__":
    img_path = r"C:\newproj\Screenshot 2025-10-09 174619.png"
    txt_output = r"C:\newproj\text output\response.txt"

    base64_img = encode_image_to_base64(img_path)

    if "Error" not in base64_img:
        create_text_file(txt_output, base64_img)
    else:
        print(base64_img)
