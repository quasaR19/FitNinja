# workouts/bot.py

import os
import django
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from django.contrib.auth.models import User
from django.utils import timezone
from asgiref.sync import sync_to_async
from .models import Workout, Exercise, ExerciseLog, PersonalRecord

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fitninja_project.settings')
django.setup()

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен бота (получите у @BotFather)
BOT_TOKEN = "ВАШ_ТОКЕН_ОТ_BOTFATHER"

# URL вашего сайта (для Telegram Web App)
WEBAPP_URL = "https://ваш-сайт.ру"  # Заменить на реальный URL


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (синхронные обёртки для async)
# ============================================================

@sync_to_async
def get_or_create_user(telegram_id, username, first_name):
    """Получить или создать пользователя по telegram_id"""
    user, created = User.objects.get_or_create(
        username=f"tg_{telegram_id}",
        defaults={
            'first_name': first_name,
            'email': f"{telegram_id}@tg.local"
        }
    )
    if created:
        # Создаём профиль пользователя (если нужно)
        pass
    return user, created


@sync_to_async
def get_today_workout(user):
    """Получить или создать сегодняшнюю тренировку"""
    today = timezone.now().date()
    workout, created = Workout.objects.get_or_create(
        user=user,
        date=today,
        defaults={'is_finished': False}
    )
    return workout, created


@sync_to_async
def get_exercise_logs(workout):
    """Получить все подходы в тренировке"""
    return list(workout.exercise_logs.all())


@sync_to_async
def add_exercise_log(user, workout, exercise_name, weight, reps, sets):
    """Добавить подход"""
    exercise, _ = Exercise.objects.get_or_create(
        name=exercise_name,
        user=user
    )
    
    log = ExerciseLog.objects.create(
        workout=workout,
        exercise=exercise,
        weight=weight,
        reps=reps,
        sets=sets,
        order=workout.exercise_logs.count() + 1
    )
    
    # Проверка рекорда
    is_pr = check_pr(user, exercise, weight, reps, sets)
    if is_pr:
        log.is_pr = True
        log.save()
        PersonalRecord.objects.create(
            user=user,
            exercise=exercise,
            weight=weight,
            reps=reps,
            sets=sets,
            workout=workout
        )
    
    return log, is_pr


@sync_to_async
def check_pr(user, exercise, weight, reps, sets):
    """Проверить, является ли подход личным рекордом"""
    existing_pr = PersonalRecord.objects.filter(
        user=user,
        exercise=exercise
    ).order_by('-weight', '-reps').first()
    
    if not existing_pr:
        return True
    
    # Рекорд: вес больше или (вес равен, но повторений больше)
    if weight > existing_pr.weight:
        return True
    if weight == existing_pr.weight and reps > existing_pr.reps:
        return True
    
    return False


@sync_to_async
def finish_workout(workout):
    """Завершить тренировку"""
    workout.is_finished = True
    workout.end_time = timezone.now()
    workout.save()
    return workout


# ============================================================
# ОБРАБОТЧИКИ КОМАНД
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start — приветствие и главное меню"""
    user = update.effective_user
    
    # Создаём/получаем пользователя
    db_user, created = await get_or_create_user(
        user.id, user.username or f"user_{user.id}", user.first_name
    )
    context.user_data['user_id'] = db_user.id
    
    # Кнопка для открытия Web App
    keyboard = [
        [InlineKeyboardButton(
            text="🏋️ Открыть FitNinja",
            web_app=WebAppInfo(url=f"{WEBAPP_URL}/?tg_id={user.id}")
        )],
        [InlineKeyboardButton(
            text="📊 Сегодняшняя тренировка",
            callback_data="today"
        )],
        [InlineKeyboardButton(
            text="📝 Добавить подход",
            callback_data="add_set"
        )],
        [InlineKeyboardButton(
            text="🏆 Мои рекорды",
            callback_data="records"
        )],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"""
🏋️ *Привет, {user.first_name}!*

Добро пожаловать в FitNinja — твой личный дневник тренировок!

📌 Что умеет бот:
• Записывать подходы (вес × повторы × подходы)
• Отслеживать личные рекорды
• Показывать статистику
• Открывать полный сайт с аналитикой

👇 Нажми на кнопку ниже, чтобы открыть приложение!
    """
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def today_workout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать сегодняшнюю тренировку"""
    query = update.callback_query
    await query.answer()
    
    user_id = context.user_data.get('user_id')
    if not user_id:
        await query.edit_message_text("⚠️ Пожалуйста, используйте /start для авторизации.")
        return
    
    db_user = await sync_to_async(User.objects.get)(id=user_id)
    workout, created = await get_today_workout(db_user)
    logs = await get_exercise_logs(workout)
    
    if not logs and not created:
        await query.edit_message_text(
            "📭 Сегодня ещё нет тренировок.\n"
            "Используй /add Упражнение вес×повторы×подходы\n"
            "Например: /add Приседания 80×5×3"
        )
        return
    
    # Формируем отчёт
    text = f"📅 *{workout.date.strftime('%d.%m.%Y')}*\n\n"
    
    if logs:
        for log in logs:
            pr_mark = " 🔥 PR!" if log.is_pr else ""
            text += f"• {log.exercise.name}: {log.weight}×{log.reps}×{log.sets}{pr_mark}\n"
        
        total_volume = await sync_to_async(workout.total_volume)()
        text += f"\n📊 Общий объём: *{total_volume} кг*"
    
    if workout.is_finished:
        text += "\n\n✅ Тренировка завершена!"
    else:
        text += "\n\n🔄 Тренировка активна. Добавляй подходы!"
    
    # Кнопки
    keyboard = [
        [InlineKeyboardButton("➕ Добавить подход", callback_data="add_set")],
    ]
    if not workout.is_finished:
        keyboard.append([InlineKeyboardButton("✅ Завершить тренировку", callback_data="finish")])
    keyboard.append([InlineKeyboardButton("🏋️ Открыть сайт", web_app=WebAppInfo(url=f"{WEBAPP_URL}/"))])
    
    await query.edit_message_text(
        text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def add_set_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запросить ввод подхода"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📝 *Добавь подход в формате:*\n"
        "`Упражнение вес×повторы×подходы`\n\n"
        "Например:\n"
        "`Приседания 80×5×3`\n"
        "`Жим лёжа 60×8×3`\n\n"
        "Или отправь сообщение в этом же чате."
    )


async def handle_add_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода подхода через сообщение"""
    text = update.message.text.strip()
    user = update.effective_user
    
    db_user = await sync_to_async(User.objects.get)(username=f"tg_{user.id}")
    workout, _ = await get_today_workout(db_user)
    
    try:
        # Парсим: "Упражнение 80×5×3"
        parts = text.split()
        if len(parts) < 2:
            await update.message.reply_text("⚠️ Неправильный формат. Используй: Упражнение 80×5×3")
            return
        
        exercise_name = " ".join(parts[:-1])
        weight_reps_sets = parts[-1]
        
        weight_reps_sets = weight_reps_sets.replace('x', '×')
        if '×' not in weight_reps_sets:
            await update.message.reply_text("⚠️ Неправильный формат. Используй: Упражнение 80×5×3")
            return
        
        wrs = weight_reps_sets.split('×')
        weight = float(wrs[0])
        reps = int(wrs[1])
        sets = int(wrs[2])
        
        log, is_pr = await add_exercise_log(db_user, workout, exercise_name, weight, reps, sets)
        
        pr_text = " 🔥 НОВЫЙ РЕКОРД!" if is_pr else ""
        await update.message.reply_text(
            f"✅ Добавлено: {exercise_name} {weight}×{reps}×{sets}{pr_text}\n"
            f"💪 Тренировка продолжается! Используй /today для просмотра."
        )
        
    except Exception as e:
        await update.message.reply_text(f"⚠️ Ошибка: {str(e)}\nИспользуй формат: Упражнение 80×5×3")


async def finish_workout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершить тренировку"""
    query = update.callback_query
    await query.answer()
    
    user_id = context.user_data.get('user_id')
    if not user_id:
        await query.edit_message_text("⚠️ Ошибка авторизации")
        return
    
    db_user = await sync_to_async(User.objects.get)(id=user_id)
    workout, _ = await get_today_workout(db_user)
    
    if workout.is_finished:
        await query.edit_message_text("✅ Тренировка уже завершена!")
        return
    
    await finish_workout(workout)
    
    logs = await get_exercise_logs(workout)
    total_volume = await sync_to_async(workout.total_volume)()
    
    text = f"✅ *Тренировка завершена!*\n\n"
    for log in logs:
        pr_mark = " 🔥 PR!" if log.is_pr else ""
        text += f"• {log.exercise.name}: {log.weight}×{log.reps}×{log.sets}{pr_mark}\n"
    
    text += f"\n📊 Общий объём: *{total_volume} кг*"
    
    await query.edit_message_text(text, parse_mode='Markdown')


async def records_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать личные рекорды"""
    query = update.callback_query
    await query.answer()
    
    user_id = context.user_data.get('user_id')
    if not user_id:
        await query.edit_message_text("⚠️ Ошибка авторизации")
        return
    
    db_user = await sync_to_async(User.objects.get)(id=user_id)
    records = await sync_to_async(list)(PersonalRecord.objects.filter(user=db_user).order_by('-weight', '-reps'))
    
    if not records:
        await query.edit_message_text(
            "🏆 У вас пока нет личных рекордов.\n"
            "Тренируйтесь и ставьте новые рекорды! 💪"
        )
        return
    
    text = "🏆 *Мои рекорды:*\n\n"
    for rec in records[:10]:
        date_str = rec.date.strftime('%d.%m.%Y')
        text += f"• {rec.exercise.name}: *{rec.weight}×{rec.reps}* ({date_str})\n"
    
    await query.edit_message_text(text, parse_mode='Markdown')


# ============================================================
# ЗАПУСК БОТА
# ============================================================

def run_bot():
    """Запуск Telegram бота"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Команды
    application.add_handler(CommandHandler("start", start))
    
    # Callback кнопки
    application.add_handler(CallbackQueryHandler(today_workout, pattern="^today$"))
    application.add_handler(CallbackQueryHandler(add_set_prompt, pattern="^add_set$"))
    application.add_handler(CallbackQueryHandler(finish_workout_handler, pattern="^finish$"))
    application.add_handler(CallbackQueryHandler(records_handler, pattern="^records$"))
    
    # Обработка сообщений (для добавления подходов)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_set))
    
    # Запуск
    logger.info("Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    run_bot()
