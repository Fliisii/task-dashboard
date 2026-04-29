import os
import json
import logging
import urllib.request
from datetime import datetime, timedelta, date
import ydb
import ydb.iam
import re
import dateparser
import string
import random
from PIL import Image, ImageDraw, ImageFont
import io
import requests

# Настраиваем логирование
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Глобальный драйвер YDB
_driver = None
TABLE_PATH = "tasks"

# Часовой пояс: MSK = UTC+3
TIMEZONE_OFFSET_HOURS = 3

def create_tasks_image(tasks, user_id):
    print("🖼 Начинаем создание изображения")

    # Настройки изображения
    width = 800
    height = 400
    BG_COLOR = (30, 30, 30)      # Тёмный фон
    TEXT_COLOR = (220, 220, 220) # Светлый текст
    ACCENT_COLOR = (70, 115, 223) # Синий акцент
    DONE_COLOR = (0, 180, 0)     # Зелёный
    PENDING_COLOR = (255, 165, 0) # Оранжевый
    ERROR_COLOR = (220, 60, 60)  # Красный для низкого прогресса

    # Создаём изображение
    image = Image.new('RGB', (width, height), BG_COLOR)
    draw = ImageDraw.Draw(image)

    # Пытаемся загрузить шрифт
    try:
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        font_title = ImageFont.truetype(font_path, 28)
        font_header = ImageFont.truetype(font_path, 20)
        font_task = ImageFont.truetype(font_path, 18)
        font_stats = ImageFont.truetype(font_path, 16)
        print("✅ Используем DejaVuSans")
    except Exception as e:
        print(f"❌ Ошибка шрифта: {e}")
        font_title = ImageFont.load_default()
        font_header = ImageFont.load_default()
        font_task = ImageFont.load_default()
        font_stats = ImageFont.load_default()

    # Заголовок
    draw.text((20, 20), "Мои задачи", fill=ACCENT_COLOR, font=font_title)

    # Статистика
    total = len(tasks)
    done = sum(1 for t in tasks.values() if t.get('done'))
    pending = total - done
    progress = done / total if total > 0 else 0

    # Цвет прогресс-бара в зависимости от прогресса
    if progress > 0.7:
        BAR_COLOR = DONE_COLOR
    elif progress > 0.3:
        BAR_COLOR = PENDING_COLOR
    else:
        BAR_COLOR = ERROR_COLOR

    stats_text = f"Всего: {total} | ✓ Выполнено: {done} | ○ Осталось: {pending}"
    draw.text((20, 70), stats_text, fill=TEXT_COLOR, font=font_stats)

    # Прогресс-бар
    bar_x, bar_y = 20, 110
    bar_width, bar_height = 760, 30
    draw.rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + bar_height], outline=(80, 80, 80))
    draw.rectangle([bar_x, bar_y, bar_x + bar_width * progress, bar_y + bar_height], fill=BAR_COLOR)
    draw.text((bar_x + bar_width // 2 - 30, bar_y + 5), f"{int(progress * 100)}%", fill="white", font=font_stats)

    # Задачи
    y = 160
    for task_id, task in list(tasks.items())[:10]:
        status = "✓" if task.get('done') else "○"
        title = task['title'][:40] + "..." if len(task['title']) > 40 else task['title']
        remind_at = task.get('remind_at', '—')

        # Цвет статуса
        status_color = DONE_COLOR if task.get('done') else PENDING_COLOR

        # Рисуем статус
        draw.text((20, y), f"[{status}]", fill=status_color, font=font_task)
        # Название
        draw.text((60, y), f"{task_id}. {title}", fill=TEXT_COLOR, font=font_task)
        # Дата и время
        draw.text((60, y + 20), f"⏰ {remind_at}", fill=(150, 200, 255), font=font_task)

        y += 50
        if y > height - 40:
            draw.text((20, y), "... и ещё", fill=(150, 150, 150), font=font_task)
            break

    # Сохраняем в буфер
    img_buffer = io.BytesIO()
    image.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    return img_buffer

def generate_temp_token(chat_id, expire_minutes=10):
    """
    Генерирует одноразовый токен и сохраняет в БД
    """
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    expires_at = datetime.utcnow() + timedelta(minutes=expire_minutes)

    driver = get_ydb_driver()
    session = driver.table_client.session().create()
    try:
        query = """
        DECLARE $token AS Utf8;
        DECLARE $user_id AS Uint64;
        DECLARE $expires_at AS Timestamp;
        UPSERT INTO auth_tokens (token, user_id, expires_at)
        VALUES ($token, $user_id, $expires_at);
        """
        parameters = {
            '$token': token,
            '$user_id': chat_id,
            '$expires_at': int(expires_at.timestamp() * 1_000_000)
        }
        prepared = session.prepare(query)
        session.transaction().execute(prepared, parameters=parameters, commit_tx=True)
        return token
    except Exception as e:
        logger.error(f"❌ Ошибка генерации токена: {e}")
        return None
    finally:
        session.delete()

def escape_markdown_v2(text):
    """
    Экранирует спецсимволы для MarkdownV2
    """
    escape_chars = r'\_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

def get_ydb_driver():
    global _driver
    if _driver is None:
        endpoint = os.environ['YDB_ENDPOINT']
        database = os.environ['YDB_DATABASE']

        logger.info(f"🔧 Подключение к YDB: {endpoint} | БД: {database}")
        driver_config = ydb.DriverConfig(
            endpoint=endpoint,
            database=database,
            credentials=ydb.iam.MetadataUrlCredentials(),
        )
        _driver = ydb.Driver(driver_config)
        try:
            _driver.wait(timeout=25, fail_fast=True)
            logger.info("✅ YDB: Подключение установлено")
        except Exception as e:
            logger.error(f"❌ YDB: Ошибка подключения: {type(e).__name__}: {e}", exc_info=True)
            raise
    return _driver

def load_tasks_from_ydb(chat_id):
    """Загружает задачи пользователя из YDB"""
    driver = get_ydb_driver()
    session = driver.table_client.session().create()
    try:
        query = """
        DECLARE $user_id AS Uint64;
        SELECT task_id, title, remind_at, is_completed
        FROM tasks
        WHERE user_id = $user_id
        ORDER BY remind_at;
        """
        parameters = {'$user_id': chat_id}
        prepared = session.prepare(query)
        result_sets = session.transaction().execute(prepared, parameters=parameters, commit_tx=True)

        tasks = {}
        for row in result_sets[0].rows:
            dt = datetime.utcfromtimestamp(row.remind_at / 1_000_000) + timedelta(hours=TIMEZONE_OFFSET_HOURS)
            remind_str = dt.strftime("%Y-%m-%d %H:%M")
            tasks[row.task_id] = {
                "title": row.title,
                "remind_at": remind_str,
                "done": row.is_completed
            }
        return tasks
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки задач: {e}")
        return {}
    finally:
        session.delete()

def save_task_to_ydb(chat_id, task_id, title, remind_at, done=False):
    logger.info(f"💾 Сохраняем задачу: chat_id={chat_id}, task_id={task_id}, title='{title}', remind_at={remind_at}")
    """Сохраняет задачу в YDB (в UTC)"""
    driver = get_ydb_driver()
    session = driver.table_client.session().create()
    try:
        dt_msk = datetime.strptime(remind_at, "%Y-%m-%d %H:%M")
        dt_utc = dt_msk - timedelta(hours=TIMEZONE_OFFSET_HOURS)
        timestamp_us = int(dt_utc.timestamp() * 1_000_000)
        created_us = int(datetime.utcnow().timestamp() * 1_000_000)

        query = """
        DECLARE $user_id AS Uint64;
        DECLARE $task_id AS Uint64;
        DECLARE $title AS Utf8;
        DECLARE $remind_at AS Timestamp;
        DECLARE $is_completed AS Bool;
        DECLARE $created_at AS Timestamp;
        UPSERT INTO tasks (user_id, task_id, title, remind_at, is_completed, created_at)
        VALUES ($user_id, $task_id, $title, $remind_at, $is_completed, $created_at);
        """
        parameters = {
            '$user_id': chat_id,
            '$task_id': task_id,
            '$title': title,
            '$remind_at': timestamp_us,
            '$is_completed': done,
            '$created_at': created_us,
        }
        prepared = session.prepare(query)
        session.transaction().execute(prepared, parameters=parameters, commit_tx=True)
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения задачи: {e}")
        raise
    finally:
        session.delete()

def mark_task_done_in_ydb(chat_id, task_id):
    """Отмечает задачу как выполненную"""
    driver = get_ydb_driver()
    session = driver.table_client.session().create()
    try:
        query = """
        DECLARE $user_id AS Uint64;
        DECLARE $task_id AS Uint64;
        UPDATE tasks SET is_completed = TRUE WHERE user_id = $user_id AND task_id = $task_id;
        """
        prepared = session.prepare(query)
        parameters = {'$user_id': chat_id, '$task_id': task_id}
        session.transaction().execute(prepared, parameters=parameters, commit_tx=True)
    except Exception as e:
        logger.error(f"❌ Ошибка обновления задачи: {e}")
        raise
    finally:
        session.delete()

def delete_task_from_ydb(chat_id, task_id):
    """Удаляет задачу из YDB"""
    driver = get_ydb_driver()
    session = driver.table_client.session().create()
    try:
        query = """
        DECLARE $user_id AS Uint64;
        DECLARE $task_id AS Uint64;
        DELETE FROM tasks WHERE user_id = $user_id AND task_id = $task_id;
        """
        prepared = session.prepare(query)
        parameters = {'$user_id': chat_id, '$task_id': task_id}
        session.transaction().execute(prepared, parameters=parameters, commit_tx=True)
    except Exception as e:
        logger.error(f"❌ Ошибка удаления задачи: {e}")
        raise
    finally:
        session.delete()

def send_all_pending_reminders(token):
    """
    Отправляет напоминания для всех просроченных задач, если ещё не отправляли
    """
    driver = get_ydb_driver()
    session = driver.table_client.session().create()
    try:
        query = """
        SELECT user_id, task_id, title
        FROM tasks
        WHERE remind_at <= CurrentUtcTimestamp()
          AND is_completed = false
          AND (is_notified IS NULL OR is_notified = false);
        """
        prepared = session.prepare(query)
        result_sets = session.transaction().execute(prepared, commit_tx=True)

        sent_count = 0
        for row in result_sets[0].rows:
            try:
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                data = json.dumps({
                    "chat_id": row.user_id,
                    "text": f"⏰ Напоминание: {row.title}",
                    "parse_mode": "MarkdownV2"
                }).encode("utf-8")
                req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
                urllib.request.urlopen(req, timeout=10)
                logger.info(f"✅ Напоминание отправлено: {row.title}")

                # Помечаем как уведомленную
                mark_as_notified(session, row.task_id, row.user_id)
                sent_count += 1
            except Exception as e:
                logger.error(f"❌ Не удалось отправить напоминание: {e}")

        logger.info(f"📬 Отправлено {sent_count} напоминаний")
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке напоминаний: {e}")
    finally:
        session.delete()

def mark_as_notified(session, task_id, user_id):
    """Помечает задачу как уведомленную"""
    query = """
    DECLARE $user_id AS Uint64;
    DECLARE $task_id AS Uint64;
    UPDATE tasks SET is_notified = true WHERE user_id = $user_id AND task_id = $task_id;
    """
    parameters = {
        '$user_id': user_id,
        '$task_id': task_id,
    }
    prepared = session.prepare(query)
    session.transaction().execute(prepared, parameters=parameters, commit_tx=True)

def get_user_state(chat_id):
    logger.info(f"🔍 Загружаем состояние для user_id={chat_id}")
    driver = get_ydb_driver()
    session = driver.table_client.session().create()
    try:
        query = """
        DECLARE $user_id AS Uint64;
        SELECT state, data FROM user_state WHERE user_id = $user_id;
        """
        parameters = {'$user_id': chat_id}
        prepared = session.prepare(query)
        result_sets = session.transaction().execute(prepared, parameters=parameters, commit_tx=True)
        if result_sets[0].rows:
            row = result_sets[0].rows[0]
            state = row.state
            raw_data = row.data
            if raw_data is None:
                data = {}
            else:
                try:
                    # Явно парсим как JSON
                    data = json.loads(raw_data)
                    if not isinstance(data, dict):
                        data = {}
                except (json.JSONDecodeError, TypeError):
                    data = {}
            logger.info(f"✅ Найдено состояние: state={state}, data={data}")
            return {'state': state, 'data': data}
        else:
            logger.info("🟢 Состояние не найдено")
            return None
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки состояния: {e}")
        return None
    finally:
        session.delete()

def make_json_serializable(obj):
    """
    Рекурсивно делает объект сериализуемым в JSON
    """
    if isinstance(obj, dict):
        return {str(k): make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [make_json_serializable(i) for i in obj]
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, (int, float, str, bool)) or obj is None:
        return obj
    else:
        # Любые другие типы — в строку
        return str(obj)

def set_user_state(chat_id, state, data=None):
    logger.info(f"🔧 Сохраняем состояние: user_id={chat_id}, state={state}, data={data}")
    driver = get_ydb_driver()
    session = driver.table_client.session().create()
    try:
        if data is not None:
            if not isinstance(data, dict):
                logger.warning(f"⚠️ data не словарь, преобразуем: {type(data)}")
                data = {"value": str(data)}

            # Делаем данные безопасными для JSON
            try:
                clean_data = make_json_serializable(data)
                data_json_str = json.dumps(clean_data, ensure_ascii=False)
            except Exception as e:
                logger.error(f"❌ Ошибка при подготовке data к JSON: {e}, data={data}")
                data_json_str = json.dumps({"error": "invalid_data", "raw": str(data)}, ensure_ascii=False)

            query = """
            DECLARE $user_id AS Uint64;
            DECLARE $state AS Utf8;
            DECLARE $data AS JsonDocument;
            UPSERT INTO user_state (user_id, state, data) VALUES ($user_id, $state, $data);
            """
            parameters = {
                '$user_id': chat_id,
                '$state': state,
                '$data': data_json_str
            }
        else:
            if state is None:
                # Полностью удаляем состояние
                query = """
                DECLARE $user_id AS Uint64;
                DELETE FROM user_state WHERE user_id = $user_id;
                """
                parameters = {'$user_id': chat_id}
            else:
                query = """
                DECLARE $user_id AS Uint64;
                DECLARE $state AS Utf8;
                UPSERT INTO user_state (user_id, state) VALUES ($user_id, $state);
                """
                parameters = {
                    '$user_id': chat_id,
                    '$state': state
                }

        prepared = session.prepare(query)
        session.transaction().execute(prepared, parameters=parameters, commit_tx=True)
        logger.info("✅ Состояние сохранено в YDB")
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения состояния: {e}")
    finally:
        session.delete()

def parse_datetime(text):
    logger.info(f"🔍 Пытаемся распознать время: '{text}'")
    text = text.strip()
    if not text:
        logger.warning("❌ Пустой ввод")
        return None

    # Строгие форматы...
    strict_formats = [
        "%Y-%m-%d %H:%M",
        "%d.%m.%Y %H:%M",
        "%H:%M"
    ]

    now = datetime.now()

    for fmt in strict_formats:
        try:
            dt = datetime.strptime(text, fmt)
            if "%H:%M" in fmt and len(text) <= 5:
                dt = dt.replace(year=now.year, month=now.month, day=now.day)
                if dt < now:
                    dt += timedelta(days=1)
            logger.info(f"✅ Распознано по формату {fmt}: {dt}")
            return dt.strftime("%Y-%m-%d %H:%M")
        except ValueError as e:
            continue

    # Гибкий парсинг
    try:
        logger.info("🔍 Пробуем dateparser...")
        dt = dateparser.parse(
            text,
            languages=['ru'],
            settings={
                'TIMEZONE': 'Europe/Moscow',
                'RETURN_AS_TIMEZONE_AWARE': False,
                'PREFER_DATES_FROM': 'future'
            }
        )
        if dt:
            now_naive = datetime.now().replace(tzinfo=None)
            
            # 🔒 Если год слишком большой (например, 2126 вместо 2026) — исправляем
            if dt.year > 2030:
                dt = dt.replace(year=2026)
            
            # Если дата в прошлом — переносим на следующую неделю
            if dt < now_naive:
                dt += timedelta(days=7)
                
            logger.info(f"✅ dateparser распознал: {dt}")
            return dt.strftime("%Y-%m-%d %H:%M")
        else:
            logger.warning("❌ dateparser ничего не вернул")
    except Exception as e:
        logger.error(f"❌ Ошибка dateparser: {e}")

    logger.error("❌ Не удалось распознать время")
    return None

def handle_telegram_message(event, context, token):
    body = json.loads(event.get('body', '{}'))

    # === ОБРАБОТКА КНОПОК (callback_query) ===
    callback_query = body.get('callback_query')
    if callback_query:
        chat_id = callback_query['message']['chat']['id']
        data = callback_query['data']
        message_id = callback_query['message']['message_id']

        logger.info(f"📩 Callback от chat_id={chat_id}: '{data}'")

        # Снимаем "часики"
        try:
            url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
            req_data = {"callback_query_id": callback_query['id']}
            req = urllib.request.Request(
                url,
                data=json.dumps(req_data).encode("utf-8"),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception as e:
            logger.error(f"❌ Не удалось answerCallbackQuery: {e}")

        reply = ""
        reply_markup = None

        # === ОБРАБОТКА КНОПОК ===
        if data == "add":
            set_user_state(chat_id, "awaiting_title")
            reply = "✍️ Введите название задачи"

        elif data == "list":
            tasks = load_tasks_from_ydb(chat_id)
            if not tasks:
                reply = "📭 У тебя пока нет задач"
            else:
                reply = "📋 *Твои задачи:*\n\n"
                reply_markup = {
                    "inline_keyboard": []
                }
                for task_id, task in tasks.items():
                    status = "✅" if task.get('done') else "⏳"
                    reply += f"{task_id}. {status} *{task['title']}* — {task['remind_at']}\n"

                    row = [
                        {
                            "text": f"✅ {task_id} Выполнено",
                            "callback_data": f"done_{task_id}"
                        },
                        {
                            "text": f"🗑 {task_id} Удалить",
                            "callback_data": f"del_{task_id}"
                        }
                    ]
                    reply_markup["inline_keyboard"].append(row)

        elif data == "today":
            tasks = load_tasks_from_ydb(chat_id)
            today = datetime.now() + timedelta(hours=TIMEZONE_OFFSET_HOURS)
            today_str = today.strftime("%Y-%m-%d")
            tasks_today = [(tid, t) for tid, t in tasks.items() if t['remind_at'].startswith(today_str)]
            if not tasks_today:
                reply = "📭 На сегодня задач нет"
            else:
                reply = "📅 *Задачи на сегодня:*\n\n"
                for task_id, task in tasks_today:
                    reply += f"{task_id}. *{task['title']}* — {task['remind_at']}\n"

        elif data.startswith("done_"):
            task_id = int(data.split("_")[1])
            tasks = load_tasks_from_ydb(chat_id)
            if task_id in tasks:
                mark_task_done_in_ydb(chat_id, task_id)
                reply = f"✅ Задача {task_id} выполнена! 🎉"
                # После выполнения — обновим /list
                text = "/list"
            else:
                reply = f"❌ Задача с ID {task_id} не найдена"
                text = "/list"

        elif data.startswith("del_"):
            task_id = int(data.split("_")[1])
            tasks = load_tasks_from_ydb(chat_id)
            if task_id in tasks:
                delete_task_from_ydb(chat_id, task_id)
                reply = f"🗑 Задача {task_id} удалена"
                # После удаления — обновим /list
                text = "/list"
            else:
                reply = f"❌ Задача с ID {task_id} не найдена"
                text = "/list"

        else:
            reply = "❌ Неизвестная команда"

        # Редактируем сообщение
        try:
            url = f"https://api.telegram.org/bot{token}/editMessageText"
            req_data = {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": escape_markdown_v2(reply),
                "parse_mode": "MarkdownV2"
            }
            if reply_markup:
                req_data["reply_markup"] = reply_markup

            req = urllib.request.Request(
                url,
                data=json.dumps(req_data).encode("utf-8"),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception as e:
            logger.error(f"❌ Не удалось editMessageText: {e}")
            try:
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                req_data = {
                    "chat_id": chat_id,
                    "text": escape_markdown_v2(reply),
                    "parse_mode": "MarkdownV2"
                }
                if reply_markup:
                    req_data["reply_markup"] = reply_markup

                req = urllib.request.Request(
                    url,
                    data=json.dumps(req_data).encode("utf-8"),
                    headers={'Content-Type': 'application/json'},
                    method='POST'
                )
                urllib.request.urlopen(req, timeout=10)
            except Exception as e2:
                logger.error(f"❌ Не удалось sendMessage: {e2}")

        # Если text изменился (например, после done/del) — продолжим
        if 'text' in locals() and text:
            pass  # Ниже продолжится обработка
        else:
            return {'statusCode': 200, 'body': 'ok'}

    # === ОБРАБОТКА ОБЫЧНЫХ СООБЩЕНИЙ ===
    message = body.get('message')
    if not message:
        logger.warning("❌ Нет сообщения")
        return {'statusCode': 200, 'body': 'ok'}

    chat_id = message.get('chat', {}).get('id')
    text = message.get('text', '').strip()

    if not chat_id:
        logger.warning("❌ Не удалось получить chat_id")
        return {'statusCode': 200, 'body': 'ok'}

    logger.info(f"📩 От chat_id={chat_id}: '{text}'")

    # Загружаем состояние
    state_row = get_user_state(chat_id)
    current_state = None
    state_data = {}

    if state_row:
        current_state = state_row.get('state')
        state_data = state_row.get('data') or {}
        logger.info(f"🔍 Текущее состояние: state={current_state}, data={state_data}")
    else:
        logger.info("🟢 Состояние не найдено")

    # Загружаем задачи
    tasks = load_tasks_from_ydb(chat_id)
    logger.info(f"📥 Загружено {len(tasks)} задач из YDB для chat_id={chat_id}")

    reply = ""
    reply_markup = None

    # === /start — всегда сбрасывает всё ===
    if text == '/start':
        set_user_state(chat_id, None)
        reply = (
            "🤖 *Бот-планировщик*\n\n"
            "Я помогу тебе не забыть важное.\n\n"
            "📌 *Основные команды:*\n"
            "• /add — добавить задачу\n"
            "• /list — все задачи\n"
            "• /today — задачи на сегодня\n"
            "• /done ID задачи/задач (через пробел) — отметить как выполненную\n"
            "• /del ID задачи/задач (через пробел) — удалить задачу\n"
            "• /web — открыть панель задач\n\n"
            "Нажми кнопку или введи команду👇"
        )
        reply_markup = {
            "inline_keyboard": [
                [{"text": "➕ Добавить задачу", "callback_data": "add"}],
                [{"text": "📋 Мои задачи", "callback_data": "list"}],
                [{"text": "⏰ На сегодня", "callback_data": "today"}],
                [{"text": "🌐 Открыть панель задач", "url": f"https://musical-pegasus-69abef.netlify.app/?user_id={chat_id}"}]
            ]
        }

    # === ДИАЛОГ: ОЖИДАНИЕ НАЗВАНИЯ ===
    elif current_state == "awaiting_title":
        state_data['title'] = text
        set_user_state(chat_id, "awaiting_time", state_data)
        reply = "⏰ Когда напомнить? (например: завтра в 14:00, через 2 часа)"

    # === ДИАЛОГ: ОЖИДАНИЕ ВРЕМЕНИ ===
    elif current_state == "awaiting_time":
        when_str = parse_datetime(text)
        if not when_str:
            reply = "❌ Не удалось распознать время. Попробуй: `завтра в 15:00`, `через 2 часа`, `2026-04-10 15:30`"
        else:
            try:
                # Проверяем формат: YYYY-MM-DD HH:MM
                datetime.strptime(when_str, "%Y-%m-%d %H:%M")
                title = state_data.get('title', 'Без названия')
                new_id = max(tasks.keys(), default=0) + 1
                save_task_to_ydb(chat_id, new_id, title, when_str, done=False)
                set_user_state(chat_id, None)
                reply = f"✅ Задача *{title}* добавлена!\n⏰ Напомню: {when_str}"
            except ValueError:
                logger.error(f"❌ Неверный формат времени: {when_str}")
                reply = "❌ Время распознано, но в неправильном формате. Попробуй: `завтра в 15:00`, `через 2 часа`, `2026-04-10 15:30`"

    # === ОСНОВНЫЕ КОМАНДЫ ===
    elif text == '/add':
        set_user_state(chat_id, "awaiting_title")
        reply = "✍️ Введите название задачи"

    elif text == '/list':
        tasks = load_tasks_from_ydb(chat_id)
        if not tasks:
            reply = "📭 У тебя пока нет задач"
            try:
                safe_reply = escape_markdown_v2(reply)
                data = {"chat_id": chat_id, "text": safe_reply, "parse_mode": "MarkdownV2"}
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), method='POST')
                req.add_header('Content-Type', 'application/json')
                urllib.request.urlopen(req, timeout=10)
            except:
                pass
            return {'statusCode': 200, 'body': 'ok'}  # ✅ ВЫХОДИМ — НЕ ОТПРАВЛЯЕМ ЕЩЁ РАЗ
        else:
            # Отправляем картинку
            try:
                img_buffer = create_tasks_image(tasks, chat_id)
                import requests
                requests.post(
                    f"https://api.telegram.org/bot{token}/sendPhoto",
                    data={"chat_id": chat_id, "caption": "📋 Твои задачи"},
                    files={"photo": ("tasks.png", img_buffer, "image/png")}
                )
            except Exception as e:
                logger.error(f"❌ Ошибка фото: {e}")

            # Отправляем текст с кнопками
            try:
                reply = "📋 Твои задачи:\n\n"
                reply_markup = {"inline_keyboard": []}
                for task_id, task in tasks.items():
                    status = "✅" if task.get('done') else "⏳"
                    reply += f"{task_id}. {status} *{task['title']}* — {task['remind_at']}\n"
                    row = [
                        {"text": f"✅ {task_id} Выполнено", "callback_data": f"done_{task_id}"},
                        {"text": f"🗑 {task_id} Удалить", "callback_data": f"del_{task_id}"}
                    ]
                    reply_markup["inline_keyboard"].append(row)

                safe_reply = escape_markdown_v2(reply)
                data = {
                    "chat_id": chat_id,
                    "text": safe_reply,
                    "parse_mode": "MarkdownV2",
                    "reply_markup": reply_markup
                }
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), method='POST')
                req.add_header('Content-Type', 'application/json')
                urllib.request.urlopen(req, timeout=10)
            except Exception as e:
                logger.error(f"❌ Ошибка текста: {e}")

            return {'statusCode': 200, 'body': 'ok'}  # ✅ ВЫХОДИМ — НЕ ПОПАДАЕМ В ОБЩИЙ ОТВЕТ

    elif text == '/today':
        today = datetime.now() + timedelta(hours=TIMEZONE_OFFSET_HOURS)
        today_str = today.strftime("%Y-%m-%d")
        tasks_today = [(tid, t) for tid, t in tasks.items() if t['remind_at'].startswith(today_str)]
        if not tasks_today:
            reply = "📭 На сегодня задач нет"
        else:
            reply = "📅 *Задачи на сегодня:*\n\n"
            for task_id, task in tasks_today:
                reply += f"{task_id}. *{task['title']}* — {task['remind_at']}\n"

    elif text == '/help':
        reply = (
            "ℹ️ *Справка по командам:*\n\n"
            "• /start — начать сначала\n"
            "• /add — добавить задачу\n"
            "• /list — показать все задачи\n"
            "• /today — показать задачи на сегодня\n"
            "• /done <ID> — отметить задачу/задачи через пробел как выполненную(ые)\n"
            "  Пример: /done 3\n"
            "• /del <ID> — удалить задачу/задачи через пробел\n"
            "  Пример: /del 3\n"
            "• /web — перейти на сайт \n\n"
            "💡 Чтобы узнать ID задачи — посмотри /list"
        )

    elif text.startswith('/add '):
        try:
            content = text[5:]
            parts = [p.strip() for p in content.split('|')]
            if len(parts) != 2:
                raise ValueError("Wrong format")
            title, remind_at = parts
            datetime.strptime(remind_at, "%Y-%m-%d %H:%M")
            new_id = max(tasks.keys(), default=0) + 1
            save_task_to_ydb(chat_id, new_id, title, remind_at, done=False)
            reply = f"✅ Задача *{title}* добавлена с ID {new_id}!\n⏰ Напомню: {remind_at}"
        except ValueError:
            reply = "❌ Неправильный формат даты. Используй: `2026-04-10 15:30`"
        except Exception as e:
            logger.error(f"Ошибка добавления: {e}")
            reply = "❌ Не удалось добавить задачу. Попробуй ещё раз."

    elif text.startswith('/done '):
        try:
            parts = text.split()
            task_ids = list(map(int, parts[1:]))
            if not task_ids:
                reply = "❌ Укажи ID задач: `/done 1 2 3`"
            else:
                tasks = load_tasks_from_ydb(chat_id)
                done_titles = []
                not_found = []
                for task_id in task_ids:
                    if task_id in tasks:
                        mark_task_done_in_ydb(chat_id, task_id)
                        done_titles.append(tasks[task_id]['title'])
                    else:
                        not_found.append(str(task_id))

                reply = ""
                if done_titles:
                    titles_str = ", ".join(f"*{escape_markdown_v2(t)}*" for t in done_titles)
                    reply += f"✅ Выполнено: {titles_str}\n"
                if not_found:
                    reply += f"❌ Не найдены: {', '.join(not_found)}"
                if not reply:
                    reply = "Ничего не сделано"
        except ValueError:
            reply = "❌ Неверный формат ID. Используй: `/done 1 2 3`"

    elif text.startswith('/del '):
        try:
            parts = text.split()
            task_ids = list(map(int, parts[1:]))
            if not task_ids:
                reply = "❌ Укажи ID задач: `/del 1 2 3`"
            else:
                tasks = load_tasks_from_ydb(chat_id)
                deleted_titles = []
                not_found = []
                for task_id in task_ids:
                    if task_id in tasks:
                        delete_task_from_ydb(chat_id, task_id)
                        deleted_titles.append(tasks[task_id]['title'])
                    else:
                        not_found.append(str(task_id))

                reply = ""
                if deleted_titles:
                    titles_str = ", ".join(f"*{escape_markdown_v2(t)}*" for t in deleted_titles)
                    reply += f"🗑 Удалено: {titles_str}\n"
                if not_found:
                    reply += f"❌ Не найдены: {', '.join(not_found)}"
                if not reply:
                    reply = "Ничего не удалено"
        except ValueError:
            reply = "❌ Неверный формат ID. Используй: `/del 1 2 3`"

    elif text == '/web':
        url = f"https://musical-pegasus-69abef.netlify.app?user_id={chat_id}"
        reply = (
            "🌐 Откройте вашу панель задач:\n"
            f"{url}\n\n"
            "📊 Увидите:\n"
            "• Графики выполнения\n"
            "• Список задач\n"
            "• Прогресс"
        )

    else:
        parsed_time = parse_datetime(text)
        if parsed_time and not any(kw in text.lower() for kw in ['/start', '/add', '/list']):
            # Используем весь текст как название задачи
            title = text.strip()
            # Если название слишком длинное — обрезаем
            if len(title) > 100:
                title = title[:100] + "..."
            new_id = max(tasks.keys(), default=0) + 1
            save_task_to_ydb(chat_id, new_id, title, parsed_time, done=False)
            reply = f"✅ Задача *{escape_markdown_v2(title)}* добавлена!\n⏰ Напомню: {parsed_time}"
        else:
            reply = (
                "📌 Используй команды:\n"
                "• /add — добавить задачу\n"
                "• /list — посмотреть все\n"
                "• /done ID — отметить как выполненную\n"
                "• /del ID — удалить задачу\n"
                "• /web — прсомотреть визуализацию ваших задач"
            )

    # === ОТПРАВКА ОТВЕТА ===
    try:
        safe_reply = escape_markdown_v2(reply)
        data = {
            "chat_id": chat_id,
            "text": safe_reply,
            "parse_mode": "MarkdownV2",
            "disable_web_page_preview": True
        }
        if reply_markup:
            data["reply_markup"] = reply_markup

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        urllib.request.urlopen(req, timeout=10)
        logger.info("✅ Ответ отправлен в Telegram")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки: {e}")
        try:
            data_fallback = json.dumps({
                "chat_id": chat_id,
                "text": reply[:4000],
                "disable_web_page_preview": True
            }).encode("utf-8")
            req = urllib.request.Request(url, data=data_fallback, headers={'Content-Type': 'application/json'}, method='POST')
            urllib.request.urlopen(req, timeout=10)
            logger.info("✅ Ответ отправлен без Markdown")
        except: pass

    return {'statusCode': 200, 'body': 'ok'}

# === ОСНОВНОЙ ОБРАБОТЧИК ===
def handler(event, context):
    logger.info("=== ЗАПУСК БОТА ===")

    try:
        token = os.environ.get('TG_TOKEN')
        if not token:
            logger.error("❌ TG_TOKEN не найден!")
            return {'statusCode': 500, 'body': 'Token not found'}

        # Проверяем: это вебхук от Telegram?
        body_raw = event.get('body', '')
        is_telegram = bool(body_raw)

        if is_telegram:
            # Это сообщение от пользователя
            return handle_telegram_message(event, context, token)
        else:
            # Это вызов от триггера — проверяем напоминания
            logger.info("⏰ Проверка напоминаний по расписанию...")
            send_all_pending_reminders(token)
            return {'statusCode': 200, 'body': 'Reminders checked'}

    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        return {'statusCode': 500, 'body': 'Internal error'}
