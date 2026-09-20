import os
import re

bundle_dir = r"e:\TS - Copy\app\styles"
dark_path = os.path.join(bundle_dir, "dark_theme.qss")
light_path = os.path.join(bundle_dir, "light_theme.qss")

with open(dark_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace rules mapping Dark -> Light colors
# We use regex or simple replace for exact hex colors.
replacements = {
    "#1E1E2E": "#F5F6F8", # main bg
    "#E0E0E0": "#2C303A", # main text
    "#FFD54F": "#E67E22", # title/subtitle amber -> orange/amber dark
    "#9E9E9E": "#7F8C8D", # gray text
    "#B0BEC5": "#95A5A6", # another gray
    "#4CAF50": "#27AE60", # green accent (slightly darker for contrast)
    "#2F3147": "#E2E6EA", # button bg
    "#4A4E69": "#CED4DA", # standard border
    "#373B53": "#D2D7DC", # button hover
    "#252736": "#E9ECEF", # alt bg / groupbox bg
    "#5C6BC0": "#2980B9", # focus border
    "#333333": "#E0E0E0", # disabled border (might just be #333)
    "#333": "#E0E0E0",
    "#FF5252": "#E74C3C", # danger
    "#3E1E1E": "#FADBD8", # danger hover
    "#2E7D32": "#2ECC71", # accent button
    "#388E3C": "#27AE60", # accent button hover
    "#2B2D42": "#FFFFFF", # line edit / combo bg
    "#3A3D50": "#DEE2E6", # grid lines
    "white": "#FFFFFF",
    # Specific tweaks: 
    # QMenu selected text should remain white if bg is green
    # QTabBar selected bg should be #F5F6F8, text #2C303A.
}

for old, new in replacements.items():
    # Make sure we don't double replace. E0E0E0 to 2C303A is fine.
    # The dictionary order matters if there are prefixes, but these are all unique 6-hex or names.
    if old == "white":
        # we will handle white separately for specific selectors if needed.
        pass
    else:
        content = re.sub(old, new, content, flags=re.IGNORECASE)

# Manual fixes for text on dark backgrounds like selected items
# QMenu selected item has background #27AE60, text should be white
content = content.replace("color: #2C303A;\n}", "color: #2C303A;\n}\n\nQMenu::item:selected {\n    color: white;\n}")
content = content.replace("selection-color: #2C303A;", "selection-color: white;")
content = content.replace("color: #2C303A;\n}", "color: #2C303A;\n}")
# Let's just fix it manually where needed.

with open(light_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Created light_theme.qss")
