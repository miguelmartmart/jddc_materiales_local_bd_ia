// interjddcia/install.py
import os
import sys

def install_dependencies():
    # Instalar dependencias necesarias
    os.system("pip install -r requirements.txt")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "install":
        install_dependencies()
    else:
        print("Por favor, use el comando 'python install.py install' para instalar las dependencias.")