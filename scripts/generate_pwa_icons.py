#!/usr/bin/env python3
"""
PWA Icon Generator for Irish Historical Sites GIS
=================================================
Generates all required PWA icons from a base SVG.

Requirements:
    pip install cairosvg pillow

Usage:
    python scripts/generate_pwa_icons.py
"""

import os
import sys
from pathlib import Path

# Try to import required libraries
try:
    from PIL import Image, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("Warning: Pillow not installed. Install with: pip install pillow")

try:
    import cairosvg
    HAS_CAIRO = True
except ImportError:
    HAS_CAIRO = False
    print("Warning: cairosvg not installed. Install with: pip install cairosvg")


# Configuration
BASE_DIR = Path(__file__).resolve().parent.parent
IMAGES_DIR = BASE_DIR / 'static' / 'images'
FAVICON_SVG = IMAGES_DIR / 'favicon.svg'

# Icon sizes required for PWA
ICON_SIZES = [16, 32, 72, 96, 128, 144, 152, 167, 180, 192, 384, 512]
MASKABLE_SIZES = [192, 512]
SPLASH_SIZES = [
    (640, 1136),   # iPhone 5
    (750, 1334),   # iPhone 6/7/8
    (1242, 2208),  # iPhone 6/7/8 Plus
    (1125, 2436),  # iPhone X/XS
    (1536, 2048),  # iPad
]

# Brand colors
PRIMARY_COLOR = '#1a5f4a'  # Pine green
ACCENT_COLOR = '#ff8c00'   # Orange
BG_COLOR = '#ffffff'


def create_icon_svg():
    """Create a proper PWA icon SVG if favicon.svg doesn't exist or is unsuitable."""
    svg_content = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#1a5f4a"/>
      <stop offset="100%" style="stop-color:#145040"/>
    </linearGradient>
  </defs>
  <!-- Background circle -->
  <circle cx="256" cy="256" r="256" fill="url(#bg)"/>
  <!-- Celtic knot / shamrock inspired design -->
  <g fill="#ffffff" transform="translate(256, 256)">
    <!-- Location pin shape -->
    <path d="M0,-180 C-80,-180 -140,-120 -140,-40 C-140,60 0,180 0,180 C0,180 140,60 140,-40 C140,-120 80,-180 0,-180 Z M0,-10 C-30,-10 -55,-35 -55,-65 C-55,-95 -30,-120 0,-120 C30,-120 55,-95 55,-65 C55,-35 30,-10 0,-10 Z" 
          opacity="0.95"/>
    <!-- Inner castle icon -->
    <g transform="translate(0, -65) scale(0.4)">
      <path d="M-60,-60 L-60,40 L-30,40 L-30,0 L30,0 L30,40 L60,40 L60,-60 L40,-60 L40,-80 L20,-80 L20,-60 L-20,-60 L-20,-80 L-40,-80 L-40,-60 Z" 
            fill="#ff8c00"/>
    </g>
  </g>
</svg>'''
    return svg_content


def generate_png_from_svg(svg_path, output_path, size):
    """Generate a PNG from SVG using cairosvg."""
    if not HAS_CAIRO:
        return False
    
    try:
        cairosvg.svg2png(
            url=str(svg_path),
            write_to=str(output_path),
            output_width=size,
            output_height=size
        )
        return True
    except Exception as e:
        print(f"Error generating {output_path}: {e}")
        return False


def generate_png_fallback(output_path, size, is_maskable=False):
    """Generate a PNG icon using PIL if cairosvg is not available."""
    if not HAS_PIL:
        return False
    
    try:
        # Create image with background
        if is_maskable:
            # Maskable icons need safe zone (80% center)
            img = Image.new('RGBA', (size, size), PRIMARY_COLOR)
        else:
            img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        
        draw = ImageDraw.Draw(img)
        
        # Draw circular background
        padding = int(size * 0.05)
        draw.ellipse(
            [padding, padding, size - padding, size - padding],
            fill=PRIMARY_COLOR
        )
        
        # Draw a simple location pin icon
        center_x, center_y = size // 2, size // 2
        pin_width = int(size * 0.35)
        pin_height = int(size * 0.5)
        
        # Pin body (white)
        pin_top = center_y - int(pin_height * 0.4)
        pin_bottom = center_y + int(pin_height * 0.6)
        
        # Simplified pin shape
        draw.ellipse(
            [center_x - pin_width//2, pin_top, 
             center_x + pin_width//2, pin_top + pin_width],
            fill='white'
        )
        draw.polygon(
            [(center_x - pin_width//3, center_y),
             (center_x, pin_bottom),
             (center_x + pin_width//3, center_y)],
            fill='white'
        )
        
        # Inner circle (orange accent)
        inner_r = int(pin_width * 0.25)
        inner_y = pin_top + pin_width//2
        draw.ellipse(
            [center_x - inner_r, inner_y - inner_r,
             center_x + inner_r, inner_y + inner_r],
            fill=ACCENT_COLOR
        )
        
        img.save(output_path, 'PNG')
        return True
    except Exception as e:
        print(f"Error generating fallback {output_path}: {e}")
        return False


def generate_splash_screen(output_path, width, height):
    """Generate a splash screen image."""
    if not HAS_PIL:
        return False
    
    try:
        img = Image.new('RGB', (width, height), PRIMARY_COLOR)
        draw = ImageDraw.Draw(img)
        
        # Draw a centered icon
        icon_size = min(width, height) // 4
        center_x, center_y = width // 2, height // 2 - icon_size // 4
        
        # Simple circular icon
        draw.ellipse(
            [center_x - icon_size, center_y - icon_size,
             center_x + icon_size, center_y + icon_size],
            fill='white',
            outline='white'
        )
        
        # Inner pin shape (simplified)
        pin_r = int(icon_size * 0.6)
        draw.ellipse(
            [center_x - pin_r, center_y - pin_r,
             center_x + pin_r, center_y + pin_r],
            fill=PRIMARY_COLOR
        )
        
        # Orange center
        center_r = int(icon_size * 0.2)
        draw.ellipse(
            [center_x - center_r, center_y - int(icon_size * 0.2) - center_r,
             center_x + center_r, center_y - int(icon_size * 0.2) + center_r],
            fill=ACCENT_COLOR
        )
        
        img.save(output_path, 'PNG')
        return True
    except Exception as e:
        print(f"Error generating splash {output_path}: {e}")
        return False


def main():
    """Generate all PWA icons."""
    print("=" * 60)
    print("PWA Icon Generator - Irish Historical Sites GIS")
    print("=" * 60)
    
    # Ensure images directory exists
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    
    # Create base SVG if needed
    icon_svg = IMAGES_DIR / 'icon.svg'
    if not icon_svg.exists():
        print(f"Creating base icon SVG: {icon_svg}")
        with open(icon_svg, 'w') as f:
            f.write(create_icon_svg())
    
    # Determine which generator to use
    svg_source = icon_svg if icon_svg.exists() else FAVICON_SVG
    use_svg = HAS_CAIRO and svg_source.exists()
    
    if use_svg:
        print(f"Using cairosvg with: {svg_source}")
    else:
        print("Using PIL fallback (install cairosvg for better quality)")
    
    generated = 0
    failed = 0
    
    # Generate standard icons
    print("\nGenerating standard icons...")
    for size in ICON_SIZES:
        output_path = IMAGES_DIR / f'icon-{size}.png'
        
        if use_svg:
            success = generate_png_from_svg(svg_source, output_path, size)
        else:
            success = generate_png_fallback(output_path, size)
        
        if success:
            print(f"  ✓ icon-{size}.png")
            generated += 1
        else:
            print(f"  ✗ icon-{size}.png (failed)")
            failed += 1
    
    # Generate maskable icons
    print("\nGenerating maskable icons...")
    for size in MASKABLE_SIZES:
        output_path = IMAGES_DIR / f'icon-maskable-{size}.png'
        
        if use_svg:
            success = generate_png_from_svg(svg_source, output_path, size)
        else:
            success = generate_png_fallback(output_path, size, is_maskable=True)
        
        if success:
            print(f"  ✓ icon-maskable-{size}.png")
            generated += 1
        else:
            print(f"  ✗ icon-maskable-{size}.png (failed)")
            failed += 1
    
    # Generate splash screens
    print("\nGenerating splash screens...")
    for width, height in SPLASH_SIZES:
        output_path = IMAGES_DIR / f'splash-{width}x{height}.png'
        
        if generate_splash_screen(output_path, width, height):
            print(f"  ✓ splash-{width}x{height}.png")
            generated += 1
        else:
            print(f"  ✗ splash-{width}x{height}.png (failed)")
            failed += 1
    
    # Generate Open Graph image
    print("\nGenerating social sharing image...")
    og_path = IMAGES_DIR / 'og-image.png'
    if generate_splash_screen(og_path, 1200, 630):
        print(f"  ✓ og-image.png")
        generated += 1
    else:
        print(f"  ✗ og-image.png (failed)")
        failed += 1
    
    # Generate screenshot placeholders
    print("\nGenerating screenshot placeholders...")
    screenshots = [
        ('screenshot-wide.png', 1280, 720),
        ('screenshot-mobile.png', 750, 1334),
    ]
    for name, w, h in screenshots:
        output_path = IMAGES_DIR / name
        if generate_splash_screen(output_path, w, h):
            print(f"  ✓ {name}")
            generated += 1
        else:
            print(f"  ✗ {name} (failed)")
            failed += 1
    
    # Generate shortcut icons
    print("\nGenerating shortcut icons...")
    shortcuts = ['shortcut-map.png', 'shortcut-journey.png', 'shortcut-about.png']
    for name in shortcuts:
        output_path = IMAGES_DIR / name
        if generate_png_fallback(output_path, 96):
            print(f"  ✓ {name}")
            generated += 1
        else:
            print(f"  ✗ {name} (failed)")
            failed += 1
    
    # Summary
    print("\n" + "=" * 60)
    print(f"Generation complete: {generated} succeeded, {failed} failed")
    print("=" * 60)
    
    if failed > 0:
        print("\nTo fix failures, install dependencies:")
        print("  pip install pillow cairosvg")
    
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())

