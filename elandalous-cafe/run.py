#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════╗
║  EL ANDALOUS — Lanceur Rapide                   ║
║  Double-cliquez ou : python run.py              ║
╚══════════════════════════════════════════════════╝
"""

import subprocess
import sys
import os

def install_dependencies():
    """Installer les dépendances nécessaires"""
    print("📦 Vérification des dépendances...")
    try:
        import flask
        import flask_socketio
        print("✅ Dépendances déjà installées")
    except ImportError:
        print("📥 Installation des dépendances...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Installation terminée")

def main():
    print("""
    ╔══════════════════════════════════════╗
    ║     ☕ EL ANDALOUS — CAFÉ ☕         ║
    ║     Système de commande QR          ║
    ╚══════════════════════════════════════╝
    """)
    
    # Installer les dépendances
    install_dependencies()
    
    # Lancer le serveur
    print("\n🚀 Démarrage du serveur...\n")
    os.system(f"{sys.executable} server.py")

if __name__ == '__main__':
    main()