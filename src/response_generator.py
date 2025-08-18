from pathlib import Path
from typing import List, Dict, Optional
from config import Config
from openrouter_client import OpenRouterClient
from standard_responses import DEFAULT_FALLBACK
from offers_catalog import get_offer, get_tone_adaptation, get_dynamic_example
import re

class ResponseGenerator:
    """
    Генератор ответа:
    - Принимает результат роутера (status=success, documents, decomposed_questions)
    - Подгружает MD документы из data/documents_compressed (оптимизированные версии)
    - Собирает составной промпт (системная роль + документы + история[последние 10] + вопросы)
    - Вызывает LLM и возвращает итоговый ответ ассистента
    """

    def __init__(self, docs_dir: Optional[Path] = None):
        cfg = Config()
        # Используем Claude 3.5 Haiku для одноэтапной генерации с естественным стилем
        self.client = OpenRouterClient(
            cfg.OPENROUTER_API_KEY,
            seed=cfg.SEED,
            max_tokens=550,  # Увеличено для полных ответов без обрезки
            temperature=0.1,  # Минимальная температура для точности
            model="anthropic/claude-3.5-haiku",  # Claude Haiku для качественных ответов
        )
        self.docs_dir = docs_dir or (Path(__file__).parent.parent / "data" / "documents_compressed")
        self.history_limit = cfg.HISTORY_LIMIT  # Используем настройку из конфига

    async def generate(
        self,
        router_result: Dict,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        if router_result.get("status") != "success":
            return DEFAULT_FALLBACK

        docs = router_result.get("documents") or []
        questions = router_result.get("decomposed_questions") or []
        if not docs or not questions:
            return DEFAULT_FALLBACK

        # Получаем user_signal для персонализации
        user_signal = router_result.get("user_signal", "exploring_only")
        
        doc_texts = self._load_docs(docs)
        
        # Одноэтапная генерация с Claude Haiku + dynamic few-shot
        messages = self._build_messages(doc_texts, questions, history or [], router_result)

        try:
            reply = await self.client.chat(messages)
            cleaned = (reply or "").strip()
            if not cleaned:
                return "Извините, не удалось сформировать ответ. Попробуйте переформулировать вопрос."
            
            # Базовая очистка ответа
            sanitized = self._strip_source_citations(cleaned)
            polished = self._remove_question_headings(sanitized)
            humanized = self._humanize_missing_info(polished)
            no_labels = self._strip_service_labels(humanized)
            no_cta = self._strip_generic_cta(no_labels)
            
            # Финальная санитизация (убираем восклицания и дедупликация)
            final_text = self._final_sanitize(no_cta)
            
            # Добавляем персонализированное предложение в конец (если есть)
            offer = get_offer(user_signal)
            if offer and offer["priority"] in ["high", "medium"]:
                final_text = self._inject_offer(final_text, offer)
            
            return final_text
        except Exception as e:
            print(f"❌ Ошибка генерации ответа: {e}")
            return "Извините, временная техническая неполадка. Попробуйте еще раз."

    def _load_docs(self, docs: List[str]) -> Dict[str, str]:
        """Читает документы целиком из data/documents_compressed.
        Загружаем ВСЕ уникальные документы, выбранные Router (до 4 штук)."""
        texts: Dict[str, str] = {}
        
        # Дедупликация - убираем повторы
        unique_docs = list(dict.fromkeys(docs))  # Сохраняем порядок
        
        # Загружаем ВСЕ уникальные документы (Router уже ограничил до 4)
        docs_to_load = unique_docs
        
        for name in docs_to_load:
            try:
                path = self.docs_dir / name
                content = path.read_text(encoding="utf-8")
                texts[name] = content
            except FileNotFoundError:
                print(f"⚠️ Документ не найден: {name} ({self.docs_dir})")
            except Exception as e:
                print(f"⚠️ Ошибка чтения {name}: {e}")
        return texts

    def _build_messages(
        self,
        doc_texts: Dict[str, str],
        questions: List[str],
        history: List[Dict[str, str]],
        router_result: Dict,
    ) -> List[Dict[str, str]]:
        # Получаем user_signal для адаптации тона
        user_signal = router_result.get("user_signal", "exploring_only")
        tone_adaptation = get_tone_adaptation(user_signal)
        dynamic_example = get_dynamic_example(user_signal)
        
        # Объединённый промпт для Claude Haiku - факты + стиль + адаптация
        system_role = (
            "Ты — консультант детской школы soft skills Ukido. "
            "Отвечай живым разговорным языком от лица школы (используй 'мы', не 'я'). "
            "Говори как будто коллектив школы советует родителю. "
            "ИСПОЛЬЗУЙ ТОЛЬКО информацию из предоставленных документов. "
            "Если данных нет в документах — скажи: 'В наших материалах этого нет.' "
            "Все факты, цифры, цены — ТОЛЬКО из документов."
        )
        
        # Добавляем адаптацию тона если есть
        if tone_adaptation.get("style"):
            system_role += f"\n\nАДАПТАЦИЯ ТОНА:\n{tone_adaptation['style']}"

        # Разрешённые документы
        allowed_docs = list(doc_texts.keys())

        # Полные тексты документов (без тримминга)
        docs_block_lines = []
        for name, text in doc_texts.items():
            docs_block_lines.append(f"=== Документ: {name} ===\n{text}\n")
        docs_block = "\n".join(docs_block_lines) if docs_block_lines else "=== Документы не найдены ==="

        system_content = (
            f"{system_role}\n\n"
            f"Разрешённые источники: {', '.join(allowed_docs) if allowed_docs else '—'}\n\n"
            f"=== База знаний ===\n{docs_block}\n\n"
        )
        
        # Добавляем динамический пример если есть
        if dynamic_example:
            system_content += f"=== ПРИМЕР АДАПТАЦИИ СТИЛЯ ===\n{dynamic_example}\n\n"
        
        system_content += (
            "Стиль ответа:\n"
            "• Естественный разговорный язык от лица школы (используй 'мы', 'у нас', 'наши')\n"
            "• Короткие предложения, простые слова вместо канцелярских\n"
            "• 100-150 слов, не больше\n\n"
            "КРИТИЧЕСКИ ВАЖНО - Структура ответа:\n"
            "• ПЕРВЫЕ 2 ПРЕДЛОЖЕНИЯ должны содержать ключевую информацию!\n"
            "• Начинай с главного ответа, а не с вводных слов\n"
            "• Если родитель раздражён - первое предложение должно снизить напряжение\n"
            "• Если вопрос о цене - сразу называй цену, потом объясняй ценность\n"
            "• Детали и пояснения - только после ключевой информации\n\n"
            "Примеры хороших начал:\n"
            "• Вопрос о цене → 'Месяц обучения стоит 6,000 грн. За эти деньги ребёнок получает...'\n"
            "• Сомнения в пользе → 'Дети учатся выступать публично и управлять эмоциями. После курса 85% становятся увереннее...'\n"
            "• Раздражение → 'Понимаем ваши опасения о цене. Давайте разберём что входит в стоимость...'\n\n"
            "Факты и цифры:\n"
            "• Все цифры, цены, проценты - ТОЛЬКО из документов, точно\n"
            "• Не выдумывай, не добавляй от себя\n"
            "• Если чего-то нет - скажи 'В наших материалах этого нет'\n\n"
            "Обработка повторов:\n"
            "• Ты видишь историю последних 10 сообщений\n"
            "• Если пользователь задает вопрос, на который ты уже отвечал, или просит повторить/уточнить:\n"
            "  - Вежливо напомни информацию, используя: 'Как я упоминал...', 'Напомню, что...', 'Да, еще раз - ...'\n"
            "  - НЕ используй грубые формулировки типа 'вы уже спрашивали' или 'я уже отвечал'\n"
            "• Адаптируй ответ к причине повтора (забыл/не понял/уточняет)\n\n"
            "Избегай:\n"
            "• Восклицательных знаков\n"
            "• Клише: 'Знаете', 'Многие родители отмечают', 'так что', 'не переживайте'\n"
            "• Официальных формулировок: 'осуществляется', 'предоставляется', 'производится'\n"
            "• Повторов информации\n"
            "• Навязчивых CTA в конце ('Пишите', 'Звоните', 'Остались вопросы?')\n"
            "• Приветствий ('Здравствуйте', 'Привет') если диалог уже начался - сразу отвечай по сути\n\n"
            "Примеры замен:\n"
            "• 'осуществляется' → 'делаем'\n"
            "• 'предоставляется возможность' → 'можно'\n"
            "• 'наши квалифицированные преподаватели' → 'наши преподаватели'\n"
        )

        messages: List[Dict[str, str]] = [{"role": "system", "content": system_content}]

        # История: только последние сообщения согласно настройке (по умолчанию 10)
        trimmed_history = history[-self.history_limit :] if len(history) > self.history_limit else history
        if trimmed_history:
            messages.extend(trimmed_history)

        # Добавляем социальный контекст если есть
        social_context = router_result.get("social_context")
        social_instruction = ""
        if social_context:
            # Router уже определил правильный social_context (greeting или repeated_greeting)
            # Больше не нужна дополнительная проверка истории
            social_map = {
                "greeting": "Пользователь поздоровался. Начни ответ с короткого приветствия.",
                "repeated_greeting": "ВАЖНО: Пользователь здоровается повторно. НЕ здоровайся снова! Можешь мягко отметить это ('Мы уже поздоровались :)' или 'Еще раз здравствуйте!'), затем сразу отвечай по сути вопроса.",
                "thanks": "Пользователь поблагодарил. Начни с благодарности или подтверждения готовности помочь.",
                "apology": "Пользователь извинился. Начни с успокаивающей фразы, показывающей что всё хорошо и не стоит беспокоиться.",
                "farewell": "Пользователь прощается. Добавь прощание в конце ответа."
            }
            social_instruction = social_map.get(social_context, "") + "\n"
        
        questions_block = "\n".join(f"- {q}" for q in questions)
        messages.append(
            {
                "role": "user",
                "content": (
                    social_instruction +
                    "Ответь на вопросы естественным живым языком. "
                    "Объём 100-150 слов. Не повторяй то, что уже было сказано.\n"
                    "Аспекты для учёта:\n" + questions_block
                ),
            }
        )
        return messages

    def _strip_source_citations(self, text: str) -> str:
        """Полностью удаляет метки источников вида [doc: filename.md] из текста ответа."""
        pattern = re.compile(r"\[doc:\s*[^\]]+\]")
        return pattern.sub("", text)

    # --- Постобработка для гладкого ответного текста ---
    def _remove_question_headings(self, text: str) -> str:
        """Убирает строки-заголовки, которые дублируют декомпозированные вопросы,
        вида '1. **...?...**' или '- **...?...**' в начале блоков. Не трогает обычные списки.
        """
        lines = text.splitlines()
        cleaned_lines: List[str] = []
        heading_re = re.compile(r"^\s*(?:\d+\.|-)\s*\*\*[^*\n]*\?\*\*\s*$")
        for ln in lines:
            if heading_re.match(ln):
                # Пропускаем такие заголовки
                continue
            cleaned_lines.append(ln)
        # Сжать избыточные пустые строки
        out: List[str] = []
        empty = 0
        for ln in cleaned_lines:
            if ln.strip() == "":
                empty += 1
                if empty <= 2:
                    out.append(ln)
            else:
                empty = 0
                out.append(ln)
        return "\n".join(out).strip()

    def _humanize_missing_info(self, text: str) -> str:
        """Заменяет сухие формулировки об отсутствующих данных на более дружелюбные.
        Примеры: "Нет данных в документах", "в документах не указано" → человеческая фраза.
        """
        replacements = [
            r"нет\s+данных\s+в\s+документ(ах|ахах|ахах)?",
            r"в\s+документ(ах|ахах|ахах)?\s+не\s+указано",
            r"информац(ии|ия)\s+в\s+документ(ах|ахах|ахах)?\s+отсутствует",
        ]
        friendly = "В наших материалах этого нет."
        out = text
        for pat in replacements:
            out = re.sub(pat, friendly, out, flags=re.IGNORECASE)
        return out

    def _strip_service_labels(self, text: str) -> str:
        """Удаляет служебные заголовки вида 'Коротко:', 'Важно:', 'Итого:', 'Могу помочь:'
        При этом сохраняет содержимое после двоеточия (если есть)."""
        out_lines: List[str] = []
        label_re = re.compile(r"^\s*(Коротко|Важно|Итого|Могу помочь)\s*:\s*(.*)$", re.IGNORECASE)
        for ln in text.splitlines():
            m = label_re.match(ln)
            if m:
                content_after = m.group(2).strip()
                if content_after:
                    out_lines.append(content_after)
                # если только лейбл без текста — пропускаем строку
            else:
                out_lines.append(ln)
        return "\n".join(out_lines)

    def _strip_generic_cta(self, text: str) -> str:
        """Убирает навязчивые финальные CTA вроде 'Если у вас есть дополнительные вопросы...' и похожие."""
        patterns = [
            r"^\s*Если у вас есть .*вопрос",
            r"^\s*Если будут вопросы",
            r"^\s*Готов(а|ы)? помочь",
            r"^\s*Могу уточнить у менеджера",
            r"^\s*Я могу .* (уточнить|помочь)",
        ]
        lines = [ln for ln in text.splitlines() if not any(re.search(p, ln, flags=re.IGNORECASE) for p in patterns)]
        # также удалим лишние пустые строки в конце
        while lines and lines[-1].strip() == "":
            lines.pop()
        return "\n".join(lines)

    # Удаляем метод _stylize_response, так как теперь стилизация встроена в основной промпт
    
    def _final_sanitize(self, text: str) -> str:
        """Финальная очистка: убираем восклицания и дедуплицируем предложения."""
        out = text
        
        # Убираем восклицания
        out = out.replace("!", ".")
        
        # Дедупликация предложений с защитой от сокращений
        safe = out
        safe = re.sub(r"\bт\.д\.", "т_д", safe)
        safe = re.sub(r"\bт\.п\.", "т_п", safe)
        
        chunks = re.split(r"(?<=[\.\?\!])\s+|\n", safe)
        sentences: List[str] = []
        for ch in chunks:
            s = ch.strip()
            if s:
                sentences.append(s)
        
        seen = set()
        deduped: List[str] = []
        for s in sentences:
            key = re.sub(r"\s+", " ", s.lower()).strip()
            if key and key not in seen:
                seen.add(key)
                deduped.append(s)
        
        # Склейка и восстановление сокращений
        text_out = " ".join(deduped)
        text_out = text_out.replace("т_д", "т.д.").replace("т_п", "т.п.")
        text_out = "\n".join(line.rstrip() for line in text_out.splitlines())
        text_out = re.sub(r"\n{3,}", "\n\n", text_out)
        return text_out.strip()
    
    def _sanitize_style(self, text: str) -> str:
        """Старый метод оставляем для обратной совместимости."""
        return self._final_sanitize(text)
    
    def _inject_offer(self, response: str, offer: dict) -> str:
        """Органично добавляет персонализированное предложение в конец ответа
        
        Args:
            response: Основной ответ
            offer: Словарь с предложением из offers_catalog
            
        Returns:
            Ответ с добавленным предложением
        """
        # Убираем последнюю точку если есть
        response_trimmed = response.rstrip()
        if response_trimmed.endswith('.'):
            response_trimmed = response_trimmed[:-1]
        
        # Определяем переход в зависимости от placement
        if offer.get("placement") == "end_with_urgency":
            transition = "!\n\n"  # Восклицательный знак для urgency
        else:
            transition = ".\n\n"  # Обычная точка
        
        # Добавляем предложение
        return f"{response_trimmed}{transition}{offer['text']}"
