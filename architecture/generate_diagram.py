#!/usr/bin/env python3
"""
Генератор архитектурной диаграммы Ukido AI Assistant
Создает визуализацию архитектуры с помощью Python
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib.lines as mlines

# Создание фигуры и осей
fig, ax = plt.subplots(1, 1, figsize=(16, 12))
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)
ax.axis('off')

# Заголовок
ax.text(50, 95, 'Архитектура Ukido AI Assistant v0.7.6', 
        fontsize=20, fontweight='bold', ha='center')
ax.text(50, 91, '2-компонентный Pipeline с потоком данных', 
        fontsize=14, ha='center', style='italic')

# Цветовая схема
colors = {
    'user': '#E8F4F8',
    'api': '#FFE5CC',
    'router': '#E8D4F1',
    'generator': '#D4F1F4',
    'db': '#FFF9E6',
    'external': '#F0F0F0',
    'social': '#FFE8F1'
}

# Пользователь
user_box = FancyBboxPatch((5, 75), 15, 8, 
                          boxstyle="round,pad=0.1",
                          facecolor=colors['user'],
                          edgecolor='black', linewidth=2)
ax.add_patch(user_box)
ax.text(12.5, 79, '👤 Родитель', fontsize=12, ha='center', fontweight='bold')
ax.text(12.5, 76.5, 'Дети 7-14 лет', fontsize=9, ha='center')

# FastAPI Server
api_box = FancyBboxPatch((35, 70), 20, 18, 
                         boxstyle="round,pad=0.1",
                         facecolor=colors['api'],
                         edgecolor='black', linewidth=2)
ax.add_patch(api_box)
ax.text(45, 84, 'FastAPI Server', fontsize=12, ha='center', fontweight='bold')
ax.text(45, 81, '🐍 Python/FastAPI', fontsize=9, ha='center')
ax.text(45, 78, '• Оркестратор', fontsize=8, ha='center')
ax.text(45, 75.5, '• История (10 сообщ.)', fontsize=8, ha='center')
ax.text(45, 73, '• Управление сессиями', fontsize=8, ha='center')

# Gemini Router
router_box = FancyBboxPatch((10, 40), 25, 20, 
                           boxstyle="round,pad=0.1",
                           facecolor=colors['router'],
                           edgecolor='black', linewidth=2)
ax.add_patch(router_box)
ax.text(22.5, 56, 'Gemini Router', fontsize=12, ha='center', fontweight='bold')
ax.text(22.5, 53, '🧠 Gemini 2.5 Flash', fontsize=9, ha='center')
ax.text(22.5, 50, '• Классификация', fontsize=8, ha='center')
ax.text(22.5, 47.5, '• Подбор документов', fontsize=8, ha='center')
ax.text(22.5, 45, '• Социальные интенты', fontsize=8, ha='center')
ax.text(22.5, 42, '$0.30/1M токенов', fontsize=8, ha='center', style='italic', color='green')

# Claude Generator
generator_box = FancyBboxPatch((55, 40), 25, 20, 
                              boxstyle="round,pad=0.1",
                              facecolor=colors['generator'],
                              edgecolor='black', linewidth=2)
ax.add_patch(generator_box)
ax.text(67.5, 56, 'Claude Generator', fontsize=12, ha='center', fontweight='bold')
ax.text(67.5, 53, '🤖 Claude 3.5 Haiku', fontsize=9, ha='center')
ax.text(67.5, 50, '• Ответы 100-150 слов', fontsize=8, ha='center')
ax.text(67.5, 47.5, '• Стиль "мы"', fontsize=8, ha='center')
ax.text(67.5, 45, '• Эмпатия', fontsize=8, ha='center')
ax.text(67.5, 42, '$0.25/$1.25 за 1M', fontsize=8, ha='center', style='italic', color='green')

# База знаний
kb_box = FancyBboxPatch((35, 15), 20, 15, 
                        boxstyle="round,pad=0.1",
                        facecolor=colors['db'],
                        edgecolor='black', linewidth=2)
ax.add_patch(kb_box)
ax.text(45, 26, 'База знаний', fontsize=12, ha='center', fontweight='bold')
ax.text(45, 23, '📚 13 документов', fontsize=9, ha='center')
ax.text(45, 20, '• Курсы и цены', fontsize=8, ha='center')
ax.text(45, 17.5, '• Методология', fontsize=8, ha='center')

# Social Components
social_box = FancyBboxPatch((70, 70), 18, 12, 
                           boxstyle="round,pad=0.1",
                           facecolor=colors['social'],
                           edgecolor='black', linewidth=1.5)
ax.add_patch(social_box)
ax.text(79, 78, 'Social Components', fontsize=10, ha='center', fontweight='bold')
ax.text(79, 75, '• State Tracker', fontsize=8, ha='center')
ax.text(79, 72.5, '• Responder', fontsize=8, ha='center')

# Внешние API
openrouter_box = FancyBboxPatch((55, 5), 20, 8, 
                               boxstyle="round,pad=0.1",
                               facecolor=colors['external'],
                               edgecolor='gray', linewidth=1.5, linestyle='--')
ax.add_patch(openrouter_box)
ax.text(65, 9, 'OpenRouter API', fontsize=10, ha='center')
ax.text(65, 6.5, 'Claude 3.5 Haiku', fontsize=8, ha='center', style='italic')

gemini_api_box = FancyBboxPatch((10, 5), 20, 8, 
                               boxstyle="round,pad=0.1",
                               facecolor=colors['external'],
                               edgecolor='gray', linewidth=1.5, linestyle='--')
ax.add_patch(gemini_api_box)
ax.text(20, 9, 'Google Gemini API', fontsize=10, ha='center')
ax.text(20, 6.5, 'Gemini 2.5 Flash', fontsize=8, ha='center', style='italic')

# Стрелки и связи
def draw_arrow(x1, y1, x2, y2, label='', style='solid', color='black', curved=False):
    if curved:
        arrow = FancyArrowPatch((x1, y1), (x2, y2),
                              connectionstyle="arc3,rad=0.3",
                              arrowstyle='->', mutation_scale=20,
                              linestyle=style, color=color, linewidth=2)
    else:
        arrow = FancyArrowPatch((x1, y1), (x2, y2),
                              arrowstyle='->', mutation_scale=20,
                              linestyle=style, color=color, linewidth=2)
    ax.add_patch(arrow)
    if label:
        mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mid_x, mid_y + 1, label, fontsize=8, ha='center',
               bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.8))

# Основной поток
draw_arrow(20, 79, 35, 79, 'POST /chat')
draw_arrow(45, 70, 30, 60, '1. Классификация')
draw_arrow(30, 40, 45, 30, 'Подбор док.')
draw_arrow(35, 50, 55, 50, 'success →', curved=True)
draw_arrow(55, 79, 70, 79, 'Соц. контекст')
draw_arrow(55, 50, 45, 70, '2. Генерация', curved=True)
draw_arrow(67.5, 40, 55, 30, 'Документы')
draw_arrow(45, 88, 12.5, 83, 'Ответ', curved=True)

# Связи с внешними API
draw_arrow(22.5, 40, 20, 13, style='dashed', color='gray')
draw_arrow(67.5, 40, 65, 13, style='dashed', color='gray')

# Метрики производительности
metrics_box = FancyBboxPatch((82, 30), 16, 20, 
                            boxstyle="round,pad=0.1",
                            facecolor='#F5F5F5',
                            edgecolor='navy', linewidth=1)
ax.add_patch(metrics_box)
ax.text(90, 47, '📊 Метрики', fontsize=11, ha='center', fontweight='bold')
ax.text(90, 44, '⏱️ Время:', fontsize=9, ha='center', fontweight='bold')
ax.text(90, 41.5, 'Router: 1-2.2с', fontsize=8, ha='center')
ax.text(90, 39, 'Generator: 4.7-6.6с', fontsize=8, ha='center')
ax.text(90, 36.5, 'Общее: 5-7с', fontsize=8, ha='center', color='darkgreen')
ax.text(90, 33, '💰 Стоимость:', fontsize=9, ha='center', fontweight='bold')
ax.text(90, 30.5, '~$0.0015/ответ', fontsize=8, ha='center', color='darkgreen')

# Алгоритм выбора документов
algo_text = """Алгоритм подбора:
• 1 вопрос → 1-2 док
• 2 вопроса → 2-4 док
• 3+ вопроса → max 4
• Fuzzy match 85%"""
ax.text(3, 25, algo_text, fontsize=7, ha='left',
       bbox=dict(boxstyle="round,pad=0.5", facecolor='lightyellow', alpha=0.8))

# Типы классификации
class_text = """Классификация:
✅ success → Generator
❌ offtopic → стандарт
⚠️ simplify → упрощение"""
ax.text(3, 35, class_text, fontsize=7, ha='left',
       bbox=dict(boxstyle="round,pad=0.5", facecolor='lavender', alpha=0.8))

# Легенда
legend_elements = [
    mlines.Line2D([], [], color='black', marker='>', markersize=8, label='Основной поток'),
    mlines.Line2D([], [], color='gray', linestyle='--', label='Внешние API'),
    patches.Patch(facecolor=colors['api'], label='Core система'),
    patches.Patch(facecolor=colors['router'], label='AI Router'),
    patches.Patch(facecolor=colors['generator'], label='AI Generator')
]
ax.legend(handles=legend_elements, loc='lower right', fontsize=8)

# Сохранение
plt.tight_layout()
plt.savefig('/Users/andreysazonov/Documents/Projects/Ukido_DynContInj/architecture/ukido_architecture.png', 
            dpi=150, bbox_inches='tight', facecolor='white')
plt.savefig('/Users/andreysazonov/Documents/Projects/Ukido_DynContInj/architecture/ukido_architecture.pdf', 
            format='pdf', bbox_inches='tight', facecolor='white')

print("✅ Диаграммы успешно созданы:")
print("  - ukido_architecture.png")
print("  - ukido_architecture.pdf")