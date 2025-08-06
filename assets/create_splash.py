import base64
from pathlib import Path

PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII="
)

def generate_splash(path: Path) -> None:
    data = base64.b64decode(PNG_BASE64)
    path.write_bytes(data)


def main() -> None:
    assets_dir = Path(__file__).resolve().parent
    splash_path = assets_dir / "splash.png"
    generate_splash(splash_path)


if __name__ == "__main__":
    main()
