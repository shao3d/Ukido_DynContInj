#!/bin/bash

echo "===== ТЕСТИРОВАНИЕ ВСЕХ DIVERSE ПЕРСОН ====="
echo ""

# Массив персон
personas=(
    "1:Агрессивный отец Виктор"
    "2:Паническая мама Светлана"
    "3:Корпоративный заказчик Елена"
    "4:Бабушка-опекун Раиса"
    "5:Молодая мама-блогер Карина"
    "6:Дедушка-скептик Борис"
    "7:Многодетная мама Оля"
)

# Счетчики
total_score=0
count=0

# Тестируем каждую персону
for persona_data in "${personas[@]}"; do
    IFS=':' read -r num name <<< "$persona_data"
    
    echo "Testing $num. $name..."
    
    # Запускаем тест и извлекаем оценку
    output=$(python collaborative_test.py --diverse $num 2>&1)
    score=$(echo "$output" | grep "Общая оценка:" | grep -o '[0-9]\+\.[0-9]\+' | head -1)
    
    if [ -n "$score" ]; then
        echo "✅ $name: $score/10"
        total_score=$(echo "$total_score + $score" | bc)
        count=$((count + 1))
    else
        echo "❌ $name: Failed to get score"
    fi
    
    echo ""
done

# Средний балл
if [ $count -gt 0 ]; then
    avg_score=$(echo "scale=1; $total_score / $count" | bc)
    echo "===== ИТОГОВЫЙ РЕЗУЛЬТАТ ====="
    echo "Средний балл: $avg_score/10"
    echo "Протестировано: $count/7 персон"
else
    echo "❌ Не удалось получить результаты"
fi