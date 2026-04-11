import os

replacements = {
    # Чиним "разными способами" и остаток фарси
    "♻️ Вы можете пополнить баланс разными способами:": "♻️ Вы можете пополнить баланс разными способами:",
    "Вы можете пополнить баланс": "Вы можете пополнить баланс",
    "разными способами:": "разными способами:",
    
    # Убираем дублирование меню, если оно зашито в коде
    "🏠 Главное меню\n🏠 Главное меню": "🏠 Главное меню",
    "🏠 Главное меню": "🏠 Главное меню",
}

root_dir = '.' 

for subdir, dirs, files in os.walk(root_dir):
    if any(x in subdir for x in ['.git', '__pycache__', 'docker-volumes']):
        continue
        
    for file in files:
        if file.endswith((".py", ".json", ".yml", ".yaml")):
            file_path = os.path.join(subdir, file)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                new_content = content
                for old, new in replacements.items():
                    new_content = new_content.replace(old, new)
                
                if new_content != content:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    print(f"✅ Исправлено в: {file_path}")
            except:
                continue
