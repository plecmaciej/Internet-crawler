import os
import re
import shutil

input_file = "graph.txt"
backup_file = "graph_backup.txt"
output_file = "graph_fixed.txt"

# 1. Przywracamy oryginalny plik z backupu (żeby zacząć na świeżo)
if os.path.exists(backup_file):
    print("🔄 Znaleziono backup. Przywracam oryginalny plik...")
    shutil.copy(backup_file, input_file)

print("🛠️ Rozpoczynam ostateczne czyszczenie pliku...")

try:
    with open(input_file, 'r', encoding='utf-8') as f_in, open(output_file, 'w', encoding='utf-8') as f_out:
        for line in f_in:
            line = line.strip()

            # Usunięcie pustego słownika na końcu
            if line.endswith("{}"):
                line = line[:-2].strip()

            # maxsplit=1 gwarantuje podział tylko przy PIERWSZYM białym znaku.
            # Wszystko po lewej to źródło, wszystko po prawej to cel.
            parts = line.split(maxsplit=1)

            if len(parts) == 2:
                src = parts[0]
                dst = parts[1]

                # Używamy re.sub('\s+', ...) - to niszczy spacje, tabulacje, entery
                # i twarde spacje, zastępując je bezpiecznym '%20'
                src_fixed = re.sub(r'\s+', '%20', src)
                dst_fixed = re.sub(r'\s+', '%20', dst)

                # Zapisujemy dokładnie ze sprawną JEDNĄ spacją pomiędzy adresami
                f_out.write(f"{src_fixed} {dst_fixed}\n")

    # Podmiana plików
    os.remove(input_file)
    os.rename(output_file, input_file)

    print("✅ SUKCES! Plik został wyczyszczony ze wszystkich spacji, tabulacji i enterów w linkach.")
    print("👉 Możesz teraz uruchomić skrypt z Zadania 3. Będzie działał!")

except Exception as e:
    print(f"❌ Wystąpił błąd: {e}")