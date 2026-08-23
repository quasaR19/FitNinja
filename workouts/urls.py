from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('workouts/', views.workout_list, name='workout_list'),
    path('workouts/<int:pk>/', views.workout_detail, name='workout_detail'),
    path('workouts/create/', views.workout_create, name='workout_create'),
    path('workouts/<int:pk>/edit/', views.workout_edit, name='workout_edit'),
    path('workouts/<int:pk>/delete/', views.workout_delete, name='workout_delete'),
    path('exercises/', views.exercise_list, name='exercise_list'),
    path('exercises/create/', views.exercise_create, name='exercise_create'),
    path('records/', views.records_list, name='records_list'),
    path('api/workouts/today/', views.api_today_workout, name='api_today_workout'),
    path('api/exercise-log/create/', views.api_exercise_log_create, name='api_exercise_log_create'),
]