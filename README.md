# Commentator_Telegram README

## Описание
`commentator_telegram.py` — скрипт для автоматического комментирования постов в Telegram-каналах с использованием OpenAI и Pyrogram.

Скрипт комментирует все подписки, если у них открыты комментарии, скрипт не комментирует, то что не имеет текста, скрипт имеет встроенный промпт и настройки для работы. Вам нужно добавить ключ OpenAI и свой телеграм аккаунт! 

Скрипт позволяет привлекать посетителей в свой телеграм канал / чат / телеграм бота / на внешний сайт. 

Стоимость 1000 комментариев < 1$.

ВНИМАНИЕ. ACHTUNG. WARNING. Мы используем только рабочие аккаунты, свой личный аккаунт не подключаем!!! 

Новые телеграм аккаунты на временныхх номерахх блокируются сразу. Телеграм аккаунт на физической сим карте российского оператора работает без банов. Премиум увеличивает живучесть аккаунта, но я не измерял. 

## Требования
- Python 3.8+
- Установленные библиотеки:
pip install pyrogram openai aiohttp

- Telegram API ID и Hash (получить на https://my.telegram.org)
- OpenAI API Key (получить на https://platform.openai.com)
- Telegram Bot Token (получить через @BotFather)
- Telegram User ID или @username (получить через @userinfobot)

## Установка
1. Установите Python 3.8+.
2. Клонируйте или скачайте `commentator_telegram.py`.
3. Установите зависимости:
pip install pyrogram openai aiohttp

4. Подготовьте учетные данные:
- Telegram API ID и Hash.
- Номер телефона (с кодом страны, например, +1234567890).
- OpenAI API Key.
- Telegram Bot Token.
- Telegram User ID или @username для уведомлений.

## Подготовка к работе
1. Откройте `commentator_telegram.py` в текстовом редакторе.
2. Замените значения переменных в начале файла:
API_ID = "YOUR_API_ID"           # Ваш Telegram API ID
API_HASH = "YOUR_API_HASH"       # Ваш Telegram API Hash
PHONE_NUMBER = "+YOUR_PHONE"     # Ваш номер телефона
OPENAI_API_KEY = "YOUR_OPENAI_KEY" # Ваш OpenAI API Key
BOT_TOKEN = "YOUR_BOT_TOKEN"     # Ваш Telegram Bot Token
NOTIFY_USERS = ["USER_ID", "@USERNAME"] # Ваш User ID или @username

Вставьте свои данные вместо `YOUR_API_ID`, `YOUR_API_HASH`, `+YOUR_PHONE`, `YOUR_OPENAI_KEY`, `YOUR_BOT_TOKEN`, `USER_ID` или `@USERNAME`.
3. Сохраните файл.

## Использование со своим номером телефона и OpenAI API Key
1. Убедитесь, что номер телефона зарегистрирован в Telegram.
2. Убедитесь, что OpenAI API Key действителен.
3. Запустите скрипт:
python commentator_telegram.py

4. При первом запуске введите код авторизации, отправленный Telegram на ваш номер.
5. Скрипт начнёт мониторить каналы, генерировать комментарии через OpenAI и публиковать их в привязанных чатах.

## Настройка
- Измените `COMMENT_DELAY` (задержка для одного канала, сек) и `GLOBAL_COMMENT_DELAY` (глобальная задержка, сек) в коде, если нужно.
- Настройте `ALLOWED_POST_TYPES` для выбора типов постов для комментирования (например, `photo: True` для фото).
- Логи, blacklist и отчёты сохраняются в:
- `blacklist.txt` — каналы, где нельзя комментировать.
- `reports.csv` — отчёты о комментариях.
- `processed_posts.txt` — обработанные посты.

## Примечания
- Сессия Telegram сохраняется в `my_account.session`.
- Если сессия устарела, удалите `my_account.session` и перезапустите скрипт.
- Логи выводятся в консоль и содержат информацию об ошибках и действиях.

## Проблемы
- Ошибка `[401 AUTH_KEY_UNREGISTERED]`: удалите `my_account.session` и перезапустите.
- Ошибка `[401 USER_DEACTIVATED_BAN]`: аккаунт заблокирован, обратитесь в поддержку Telegram.
- Ошибка OpenAI: проверьте правильность `OPENAI_API_KEY`.
- Убедитесь, что `BOT_TOKEN` и `NOTIFY_USERS` корректны для уведомлений.
