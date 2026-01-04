# buffer_generator.py

START = 4000
END = 4200

y_value = 0
time_value = 0.80

output_lines = []

for x in range(START, END + 1):
    output_lines.append(
        f"<Buffer><x>{x}</x><y>{y_value}</y><time>{time_value}</time></Buffer>"
    )

# Tüm çıktıyı tek string yap
generated_xml = "\n".join(output_lines)

# Dosyaya yaz
with open("generated_buffers.xml", "w", encoding="utf-8") as f:
    f.write(generated_xml)

# Konsola bilgi bas
print("=== GENERATION COMPLETE ===")
print(f"Range        : {START} -> {END}")
print(f"Total Buffer : {len(output_lines)}")
print("===========================")

# İstersen konsola da bastır
print("\n--- GENERATED XML ---\n")
print(generated_xml)
