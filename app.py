import os
import sys
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel

class TroyanDetector(QWidget):
    def __init__(self):
        super().__init__()

        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        self.label = QLabel("Troyan Detector")
        layout.addWidget(self.label)

        button = QPushButton("Scanear")
        button.clicked.connect(self.scanear)
        layout.addWidget(button)

        self.setLayout(layout)
        self.setWindowTitle('Troyan Detector')
        self.show()

    def scanear(self):
        # Aquí irá la lógica para scanear el equipo
        print("Scaneando...")

def main():
    app = QApplication(sys.argv)
    ex = TroyanDetector()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()