"""Generate placeholder icons for Chrome extension."""
from PIL import Image, ImageDraw, ImageFont
import os

def create_icon(size, output_path):
    """Create a simple colored square icon with 'PAI' text."""
    # Create a new image with a nice gradient-like background
    img = Image.new('RGBA', (size, size), (76, 175, 80, 255))  # Green background
    draw = ImageDraw.Draw(img)
    
    # Add a subtle border
    border_width = max(1, size // 32)
    draw.rectangle([border_width, border_width, size-border_width-1, size-border_width-1], 
                   outline=(255, 255, 255, 100), width=border_width)
    
    # Draw a circle in the center
    padding = size // 4
    draw.ellipse([padding, padding, size-padding, size-padding], 
                 fill=(255, 255, 255, 230))
    
    # Try to add text
    try:
        font_size = size // 3
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        font = ImageFont.load_default()
    
    # Draw 'P' text in the circle
    text = "P"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (size - text_width) // 2
    y = (size - text_height) // 2 - text_height // 4
    
    draw.text((x, y), text, fill=(76, 175, 80, 255), font=font)
    
    # Save the image
    img.save(output_path)
    print(f"Created: {output_path}")

# Create icons directory
os.makedirs('icons', exist_ok=True)

# Generate icons in different sizes
sizes = [16, 48, 128]
for size in sizes:
    create_icon(size, f'icons/icon{size}.png')

print("All icons generated successfully!")
