from gerenciador_postgres.gui.main_window import MainWindow
from PyQt6.QtWidgets import QApplication, QSplashScreen
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import QTimer
from pathlib import Path
import subprocess
import sys


def main():
    app = QApplication(sys.argv)

    assets_dir = Path(__file__).resolve().parent / "assets"
    splash_path = assets_dir / "splash.png"
    if not splash_path.exists():
        subprocess.run([sys.executable, str(assets_dir / "create_splash.py")], check=True)

    pixmap = QPixmap(str(splash_path))
    splash = QSplashScreen(pixmap)
    splash.show()
    app.processEvents()

    window = MainWindow()
    window.show()

    QTimer.singleShot(1000, lambda: splash.finish(window))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
