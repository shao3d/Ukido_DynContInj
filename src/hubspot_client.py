"""
hubspot_client.py - Клиент для интеграции с HubSpot API
"""

import httpx
import json
from typing import Dict, Optional, List
from datetime import datetime
import os
from config import Config


class HubSpotClient:
    """Клиент для работы с HubSpot API"""

    def __init__(self):
        self.api_key = Config.HUBSPOT_PRIVATE_APP_TOKEN
        self.portal_id = Config.HUBSPOT_PORTAL_ID
        self.base_url = f"https://api.hubapi.com/crm/v3/objects"

        if not self.api_key:
            raise ValueError("HUBSPOT_PRIVATE_APP_TOKEN не установлен в .env файле")

        # HTTP клиент с таймаутом
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            timeout=30.0
        )

    async def create_or_update_contact(
        self,
        email: str,
        first_name: str,
        last_name: str,
        phone: Optional[str] = None,
        additional_data: Optional[Dict] = None
    ) -> Dict:
        """
        Создает или обновляет контакт в HubSpot

        Args:
            email: Email контакта
            first_name: Имя
            last_name: Фамилия
            phone: Телефон (опционально)
            additional_data: Дополнительные данные (источник, utm метки и т.д.)

        Returns:
            Dict: Результат операции с ID контакта
        """

        # Базовые свойства контакта
        properties = {
            "email": email,
            "firstname": first_name,
            "lastname": last_name
        }

        # Добавляем телефон если есть
        if phone:
            properties["phone"] = phone

        # Добавляем дополнительные данные
        if additional_data:
            properties.update(additional_data)

        # Ищем существующий контакт по email
        existing_contact = await self.find_contact_by_email(email)

        if existing_contact:
            # Обновляем существующий контакт
            contact_id = existing_contact.get("id")
            result = await self.update_contact(contact_id, properties)

            return {
                "action": "updated",
                "contact_id": contact_id,
                "existing": True,
                "result": result
            }
        else:
            # Создаем новый контакт
            result = await self.create_contact(properties)

            return {
                "action": "created",
                "contact_id": result.get("id"),
                "existing": False,
                "result": result
            }

    async def find_contact_by_email(self, email: str) -> Optional[Dict]:
        """Ищет контакт по email"""

        search_payload = {
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName": "email",
                            "operator": "EQ",
                            "value": email
                        }
                    ]
                }
            ],
            "properties": ["id", "email", "firstname", "lastname", "createdate"],
            "limit": 1
        }

        try:
            response = await self.client.post(
                f"{self.base_url}/contacts/search",
                json=search_payload
            )

            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])

                if results:
                    return results[0]  # Возвращаем первый найденный контакт

            return None

        except Exception as e:
            print(f"❌ Ошибка поиска контакта в HubSpot: {e}")
            return None

    async def create_contact(self, properties: Dict) -> Dict:
        """Создает новый контакт"""

        payload = {
            "properties": properties
        }

        try:
            response = await self.client.post(
                f"{self.base_url}/contacts",
                json=payload
            )

            if response.status_code == 201:
                result = response.json()
                print("✅ Контакт создан в HubSpot")
                return result
            else:
                print(f"❌ Ошибка создания контакта: {response.status_code} - {response.text}")
                raise Exception(f"HubSpot API error: {response.status_code}")

        except Exception as e:
            print(f"❌ Ошибка создания контакта в HubSpot: {e}")
            raise

    async def update_contact(self, contact_id: str, properties: Dict) -> Dict:
        """Обновляет существующий контакт"""

        payload = {
            "properties": properties
        }

        try:
            response = await self.client.patch(
                f"{self.base_url}/contacts/{contact_id}",
                json=payload
            )

            if response.status_code == 200:
                result = response.json()
                print("✅ Контакт обновлен в HubSpot")
                return result
            else:
                print(f"❌ Ошибка обновления контакта: {response.status_code} - {response.text}")
                raise Exception(f"HubSpot API error: {response.status_code}")

        except Exception as e:
            print(f"❌ Ошибка обновления контакта в HubSpot: {e}")
            raise

    async def close(self):
        """Закрывает HTTP клиент"""
        await self.client.aclose()


# Тестовая функция для проверки работы
async def test_hubspot_client():
    """Тестирует работу с HubSpot API"""

    try:
        client = HubSpotClient()

        # Тест создания/обновления контакта
        result = await client.create_or_update_contact(
            email="test@example.com",
            first_name="Тестовый",
            last_name="Пользователь",
            phone="+380501234567",
            additional_data={
                "source": "trial_lesson_form",
                "trial_lesson_requested": datetime.now().isoformat()
            }
        )

        print(f"🧪 Тест HubSpot клиента: {result}")

        await client.close()
        return result

    except Exception as e:
        print(f"❌ Тест HubSpot клиента провален: {e}")
        return None


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_hubspot_client())
