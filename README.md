# QRGenPro

**Professional QR Code Generator** - A modern, feature-rich desktop application for creating customizable QR codes.

![QRGenPro](assets/screenshot_placeholder.png)

## Features

- **Live Preview** - See your QR code update in real-time as you type
- **Multiple Presets** - Quick generation for WiFi, Email, Phone, SMS, vCard, Website, and Geo locations
- **Logo Embedding** - Add custom logos to your QR codes with automatic error correction adjustment
- **Transparent Backgrounds** - Create QR codes with transparent backgrounds for seamless integration
- **Batch Generation** - Generate multiple QR codes at once from a list
- **Custom Colors** - Choose any color combination for your QR codes
- **Multiple Export Formats** - Save as PNG or JPEG
- **Clipboard Support** - Copy QR codes directly to clipboard
- **Settings Persistence** - Your preferences are saved between sessions
- **Keyboard Shortcuts** - Quick access to common actions
- **Dark/Light Themes** - Choose your preferred appearance

## Screenshots

> Add screenshots here showing the application interface

## Installation

### Option 1: Portable Executable (Recommended for Windows)

1. Download `QRGenPro.exe` from the [Releases](../../releases) page
2. Double-click to run - no installation required!
3. The application runs completely standalone with no dependencies

### Option 2: Run from Source

**Prerequisites:**
- Python 3.10 or higher
- pip (Python package manager)

**Steps:**

```bash
# Clone the repository
git clone https://github.com/yourusername/QRGenPro.git
cd QRGenPro

# Install dependencies
pip install -r requirements.txt

# Run the application
python src/QRGenPro.py
```

## Usage Guide

### Creating a Basic QR Code

1. Launch QRGenPro
2. Type or paste your content (URL, text, etc.) in the **Content** field
3. The QR code preview updates automatically
4. Click **Save** to export or **Copy** to copy to clipboard

### Using Presets

Click any preset button to quickly generate formatted QR codes:

- **Web** - Enter a URL (automatically adds https:// if missing)
- **WiFi** - Enter network name and password for easy WiFi sharing
- **Email** - Create mailto: links with optional subject and body
- **Phone** - Generate tel: links for phone numbers
- **SMS** - Create SMS links with optional pre-filled message
- **vCard** - Generate contact cards with name, phone, email, organization
- **Geo** - Create location QR codes with latitude/longitude

### Customizing Appearance

- **QR Color** - Click to choose the color of the QR code modules
- **Background** - Click to choose background color
- **Transparent** - Check to make background transparent (great for overlays)
- **Reset Colors** - Quickly reset to black on white

### Adding a Logo

1. Click **Select Logo...** in the Style & Options section
2. Choose an image file (PNG, JPG, GIF, BMP, SVG supported)
3. The logo will be centered with a white padding
4. Error correction is automatically increased to maintain scannability

### Batch Generation

1. Go to the **Batch** tab
2. Enter one item per line (URLs, text, etc.)
3. Configure naming template and format
4. Click **Start Batch** and choose output folder
5. Progress is shown in real-time

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+S` | Save QR code |
| `Ctrl+C` | Copy image to clipboard |
| `Ctrl+G` | Generate/refresh preview |
| `Ctrl+L` | Add logo |
| `Ctrl+T` | Test & Inspect |

## Folder Structure

```
QRGenPro/
├── src/
│   └── QRGenPro.py      # Main application source
├── assets/
│   └── favicon.ico      # Application icon
├── build/
│   ├── build.bat        # Windows build script (CMD)
│   └── build.ps1        # Windows build script (PowerShell)
├── dist/
│   └── QRGenPro.exe     # Portable executable (after build)
├── requirements.txt     # Python dependencies
├── README.md           # This file
├── LICENSE             # MIT License
└── .gitignore          # Git ignore rules
```

## Building from Source

To create your own portable executable:

### Windows

```powershell
# Navigate to build folder
cd build

# Option 1: Using batch file
.\build.bat

# Option 2: Using PowerShell
.\build.ps1
```

The executable will be created in the `dist/` folder.

### Requirements for Building

- Python 3.10+
- PyInstaller (`pip install pyinstaller`)
- All dependencies from requirements.txt

## Troubleshooting

### Application won't start

- **Windows:** Right-click and "Run as administrator" if blocked
- **Antivirus:** Some antivirus software may flag PyInstaller executables. Add an exception if needed.

### QR code won't scan

- Ensure sufficient contrast between QR color and background
- If using a logo, try a smaller logo size
- Increase error correction level (H - 30% recommended for logos)

### Transparent background appears white

- Make sure you're saving as PNG (JPEG doesn't support transparency)
- The preview shows a checkerboard pattern to indicate transparency

### Fonts look wrong

- The application uses "Segoe UI" which is standard on Windows
- On other systems, a fallback system font will be used

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [PySide6](https://www.qt.io/qt-for-python) (Qt for Python)
- QR code generation by [python-qrcode](https://github.com/lincolnloop/python-qrcode)
- Image processing by [Pillow](https://python-pillow.org/)

---

**Made with ❤️ for the QR code community**
