"""
URL configuration for DI4D_Portal project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from DI4D_app import views
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('test', views.hello_world, name='hello_world'),
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('student_registration/', views.student_registration, name='student_registration'),
    path('preview_files/', views.preview_files, name='preview_files'),
    path('delete_preview_file/', views.delete_preview_file, name='delete_preview_file'),
    path('news/', views.news, name='news'),
    path('techtalks/', views.tech_talks, name='tech_talks'),
    path('techtalks/<int:talk_id>/', views.tech_talk_detail, name='tech_talk_detail'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('logout/', views.logout_view, name='logout'),
    path('users/', views.users, name='users'),
    path('settings/', views.settings_view, name='settings'),
    path('export_data/', views.export_data, name='export_data'),
    path('users_data/', views.users_data, name='users_data'),
    path('learninggoals_data/', views.learninggoals_data, name='learninggoals_data'),
    path('news/edit/', views.edit_news, name='edit_news'),
    path('news/edit/<str:mediaPath>/', views.edit_news, name='edit_news'),
    path('news/<str:mediaPath>/', views.view_news_item, name='view_news_item'),
    path('forms/', views.forms_view, name='forms'),
    path('forms/new/', views.form_builder_view, name='form_builder_new'),
    path('forms/<int:form_id>/', views.form_detail_view, name='form_detail'),
    path('forms/<int:form_id>/edit/', views.form_builder_view, name='form_builder'),
    path('forms/<int:form_id>/autosave/', views.form_autosave, name='form_autosave'),
    path('forms/<int:form_id>/submissions/', views.form_submissions, name='form_submissions'),
    path('forms/<int:form_id>/submissions/<str:username>/', views.form_submission_detail, name='form_submission_detail'),
    path('forms/<int:form_id>/questions/', views.manage_questions, name='manage_questions'),
    path('forms/<int:form_id>/questions/<int:question_id>/', views.manage_question_detail, name='manage_question_detail'),
    path('forms/<int:form_id>/questions/<int:question_id>/options/', views.manage_question_options, name='manage_question_options'),
    path('student_registrations/', views.student_registrations, name='student_registrations'),
    path('student_registrations/<int:submission_number>/', views.student_registration_detail, name='student_registration_detail'),
    path('ckeditor5/', include('django_ckeditor_5.urls')),
    # Docs : https://docs.djangoproject.com/en/6.0/topics/auth/default/#all-authentication-views
    path("password_reset/", auth_views.PasswordResetView.as_view(
        template_name="auth/forgot_password.jinja"
    ), name="password_reset"),
    path("password_reset/done/", auth_views.PasswordResetDoneView.as_view(
        template_name="auth/reset_send.jinja"
    ), name="password_reset_done"),
    path("reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="auth/reset_password.jinja"
    ), name="password_reset_confirm"),
    path("reset/done/", auth_views.PasswordResetCompleteView.as_view(
        template_name="auth/reset_complete.jinja"
    ), name="password_reset_complete"),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
handler404 = 'DI4D_app.views.page_not_found'