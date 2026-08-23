from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Exercise(models.Model):
    """Упражнение (Приседания, Жим лёжа и т.д.)"""
    name = models.CharField('Название', max_length=100)
    description = models.TextField('Описание', blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Пользователь')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Упражнение'
        verbose_name_plural = 'Упражнения'
        unique_together = ['name', 'user']

    def __str__(self):
        return self.name


class Workout(models.Model):
    """Тренировка (дата, время)"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Пользователь')
    date = models.DateField('Дата', default=timezone.now)
    start_time = models.DateTimeField('Время начала', auto_now_add=True)
    end_time = models.DateTimeField('Время окончания', null=True, blank=True)
    notes = models.TextField('Заметки', blank=True)
    is_finished = models.BooleanField('Завершена', default=False)

    class Meta:
        verbose_name = 'Тренировка'
        verbose_name_plural = 'Тренировки'
        ordering = ['-date', '-start_time']

    def __str__(self):
        return f"{self.date} - {self.user.username}"

    def total_volume(self):
        """Общий объём (вес × повторы × подходы)"""
        total = 0
        for log in self.exercise_logs.all():
            total += log.weight * log.reps * log.sets
        return total


class ExerciseLog(models.Model):
    """Запись упражнения в тренировке (вес × повторы × подходы)"""
    workout = models.ForeignKey(Workout, on_delete=models.CASCADE, verbose_name='Тренировка', related_name='exercise_logs')
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE, verbose_name='Упражнение')
    weight = models.DecimalField('Вес (кг)', max_digits=5, decimal_places=1)
    reps = models.IntegerField('Повторения')
    sets = models.IntegerField('Подходы')
    is_pr = models.BooleanField('Личный рекорд', default=False)
    notes = models.TextField('Заметки', blank=True)
    order = models.IntegerField('Порядок', default=0)

    class Meta:
        verbose_name = 'Подход'
        verbose_name_plural = 'Подходы'
        ordering = ['workout', 'order']

    def __str__(self):
        return f"{self.exercise.name} {self.weight}×{self.reps}×{self.sets}"

    def volume(self):
        return self.weight * self.reps * self.sets


class PersonalRecord(models.Model):
    """Личный рекорд"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Пользователь')
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE, verbose_name='Упражнение')
    weight = models.DecimalField('Вес (кг)', max_digits=5, decimal_places=1)
    reps = models.IntegerField('Повторения')
    sets = models.IntegerField('Подходы')
    date = models.DateField('Дата', auto_now_add=True)
    workout = models.ForeignKey(Workout, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = 'Личный рекорд'
        verbose_name_plural = 'Личные рекорды'
        ordering = ['-weight', '-reps']

    def __str__(self):
        return f"{self.exercise.name}: {self.weight}×{self.reps}"