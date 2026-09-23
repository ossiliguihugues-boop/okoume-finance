import shutil
from datetime import datetime
import os

os.makedirs('sauvegardes', exist_ok=True)
horodatage = datetime.now().strftime('%Y%m%d_%H%M%S')
shutil.copy('tontine.db', f'sauvegardes/tontine_{horodatage}.db')
print(f"Sauvegarde creee : sauvegardes/tontine_{horodatage}.db")