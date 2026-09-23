from cryptography.fernet import Fernet
import os

CHEMIN_CLE = 'cle_secrete.key'

def obtenir_cle():
    if not os.path.exists(CHEMIN_CLE):
        cle = Fernet.generate_key()
        with open(CHEMIN_CLE, 'wb') as f:
            f.write(cle)
    else:
        with open(CHEMIN_CLE, 'rb') as f:
            cle = f.read()
    return cle

fernet = Fernet(obtenir_cle())

def chiffrer(valeur):
    if valeur is None:
        return None
    return fernet.encrypt(str(valeur).encode()).decode()

def dechiffrer(valeur_chiffree):
    if valeur_chiffree is None:
        return None
    return fernet.decrypt(valeur_chiffree.encode()).decode()
