#!/usr/bin/env python3
"""
Генератор диаграмм для проекта Ukido AI Assistant
Конвертирует PlantUML диаграммы в PNG/SVG форматы

Требования:
- plantuml (brew install plantuml или apt install plantuml)
- Java Runtime Environment
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

# Цвета для вывода в терминал
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def check_plantuml_installed() -> bool:
    """Проверяет, установлен ли PlantUML"""
    try:
        result = subprocess.run(['plantuml', '-version'], 
                              capture_output=True, 
                              text=True, 
                              check=False)
        if result.returncode == 0:
            print(f"{GREEN}✓ PlantUML найден{RESET}")
            return True
    except FileNotFoundError:
        pass
    
    print(f"{RED}✗ PlantUML не установлен{RESET}")
    print(f"{YELLOW}Установите PlantUML:{RESET}")
    print("  macOS:  brew install plantuml")
    print("  Ubuntu: sudo apt-get install plantuml")
    print("  Или скачайте jar: https://plantuml.com/download")
    return False


def find_puml_files(directory: Path) -> List[Path]:
    """Находит все .puml файлы в директории"""
    puml_files = list(directory.glob("*.puml"))
    print(f"{BLUE}Найдено {len(puml_files)} диаграмм:{RESET}")
    for file in puml_files:
        print(f"  • {file.name}")
    return puml_files


def generate_diagram(puml_file: Path, output_format: str = "png") -> Tuple[bool, str]:
    """
    Генерирует диаграмму из PlantUML файла
    
    Args:
        puml_file: Путь к .puml файлу
        output_format: Формат вывода (png, svg, pdf)
    
    Returns:
        (success, message) - результат генерации
    """
    try:
        # Формируем команду для PlantUML
        cmd = [
            'plantuml',
            f'-t{output_format}',
            '-charset', 'UTF-8',
            str(puml_file)
        ]
        
        # Запускаем генерацию
        result = subprocess.run(cmd, 
                              capture_output=True, 
                              text=True, 
                              timeout=30)
        
        if result.returncode == 0:
            output_file = puml_file.with_suffix(f'.{output_format}')
            return True, f"{GREEN}✓{RESET} {puml_file.name} → {output_file.name}"
        else:
            return False, f"{RED}✗{RESET} {puml_file.name}: {result.stderr}"
            
    except subprocess.TimeoutExpired:
        return False, f"{RED}✗{RESET} {puml_file.name}: Таймаут (>30 сек)"
    except Exception as e:
        return False, f"{RED}✗{RESET} {puml_file.name}: {str(e)}"


def generate_all_diagrams(formats: List[str] = None):
    """
    Генерирует все диаграммы проекта
    
    Args:
        formats: Список форматов для генерации (по умолчанию png и svg)
    """
    if formats is None:
        formats = ['png', 'svg']
    
    # Определяем путь к диаграммам
    project_root = Path(__file__).parent.parent
    diagrams_dir = project_root / 'docs' / 'architecture'
    
    if not diagrams_dir.exists():
        print(f"{RED}Директория {diagrams_dir} не найдена{RESET}")
        return
    
    # Проверяем PlantUML
    if not check_plantuml_installed():
        return
    
    # Находим все .puml файлы
    puml_files = find_puml_files(diagrams_dir)
    if not puml_files:
        print(f"{YELLOW}Не найдено .puml файлов{RESET}")
        return
    
    print(f"\n{BLUE}Генерация диаграмм...{RESET}")
    
    # Генерируем диаграммы для каждого формата
    for format_type in formats:
        print(f"\n{YELLOW}Формат: {format_type.upper()}{RESET}")
        
        success_count = 0
        for puml_file in puml_files:
            success, message = generate_diagram(puml_file, format_type)
            print(f"  {message}")
            if success:
                success_count += 1
        
        print(f"{BLUE}Результат: {success_count}/{len(puml_files)} успешно{RESET}")
    
    # Показываем итоговую статистику
    print(f"\n{GREEN}{'='*50}{RESET}")
    print(f"{GREEN}Генерация завершена!{RESET}")
    print(f"Диаграммы сохранены в: {diagrams_dir}")
    
    # Выводим список сгенерированных файлов
    generated_files = []
    for format_type in formats:
        generated = list(diagrams_dir.glob(f"*.{format_type}"))
        generated_files.extend(generated)
    
    if generated_files:
        print(f"\n{BLUE}Сгенерированные файлы:{RESET}")
        for file in sorted(generated_files):
            size_kb = file.stat().st_size / 1024
            print(f"  • {file.name} ({size_kb:.1f} KB)")


def main():
    """Главная функция"""
    print(f"{BLUE}{'='*50}{RESET}")
    print(f"{BLUE}Генератор диаграмм Ukido AI Assistant{RESET}")
    print(f"{BLUE}{'='*50}{RESET}\n")
    
    # Парсим аргументы командной строки
    formats = ['png', 'svg']  # По умолчанию
    
    if len(sys.argv) > 1:
        # Пользователь указал форматы
        formats = sys.argv[1:]
        valid_formats = ['png', 'svg', 'pdf', 'eps', 'txt']
        formats = [f for f in formats if f in valid_formats]
        
        if not formats:
            print(f"{RED}Неверные форматы. Доступны: {', '.join(valid_formats)}{RESET}")
            sys.exit(1)
    
    print(f"Форматы для генерации: {', '.join(formats)}\n")
    
    # Генерируем диаграммы
    generate_all_diagrams(formats)


if __name__ == "__main__":
    main()