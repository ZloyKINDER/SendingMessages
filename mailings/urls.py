from django.urls import path
from . import views

app_name = 'mailings'

urlpatterns = [
    # Главная страница
    path('', views.home, name='home'),

    # Сообщения
    path('messages/', views.MessageListView.as_view(), name='message_list'),
    path('messages/<int:pk>/', views.MessageDetailView.as_view(), name='message_detail'),
    path('messages/create/', views.MessageCreateView.as_view(), name='message_create'),
    path('messages/<int:pk>/update/', views.MessageUpdateView.as_view(), name='message_update'),
    path('messages/<int:pk>/delete/', views.MessageDeleteView.as_view(), name='message_delete'),

    # Получатели
    path('recipients/', views.RecipientListView.as_view(), name='recipient_list'),
    path('recipients/<int:pk>/', views.RecipientDetailView.as_view(), name='recipient_detail'),
    path('recipients/create/', views.RecipientCreateView.as_view(), name='recipient_create'),
    path('recipients/<int:pk>/update/', views.RecipientUpdateView.as_view(), name='recipient_update'),
    path('recipients/<int:pk>/delete/', views.RecipientDeleteView.as_view(), name='recipient_delete'),

    # Рассылки
    path('mailings/', views.MailingListView.as_view(), name='mailing_list'),
    path('mailings/<int:pk>/', views.MailingDetailView.as_view(), name='mailing_detail'),
    path('mailings/create/', views.MailingCreateView.as_view(), name='mailing_create'),
    path('mailings/<int:pk>/update/', views.MailingUpdateView.as_view(), name='mailing_update'),
    path('mailings/<int:pk>/delete/', views.MailingDeleteView.as_view(), name='mailing_delete'),
    path('mailings/<int:pk>/send/', views.send_mailing, name='send_mailing'),
    path('mailings/<int:pk>/toggle/', views.toggle_mailing_active, name='toggle_mailing'),

    # Попытки рассылок
    path('attempts/', views.MailingAttemptListView.as_view(), name='attempt_list'),
]