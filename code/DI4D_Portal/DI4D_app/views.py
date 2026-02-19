from django.http import HttpResponse, FileResponse
from urllib import request
from django.utils import timezone
from django.core.mail import send_mail
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.contrib.auth import authenticate, login
from .models import ApplicationSetting, News, User, Question, FormAnswer, TechTalk, Form, UserType, Partner, LearningGoal, LearninggoalCourse, HistoryStudentApplicationForm, StatusStudentRegistration, DataType, FileItem

from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.crypto import get_random_string
from django.contrib.auth import update_session_auth_hash
from django.urls import reverse
from django.core import signing
from django.core.signing import BadSignature
from django.views.decorators.csrf import csrf_exempt
import os
import uuid
import filetype
from django.core.files.storage import default_storage
import json
from django.forms import modelform_factory
import puremagic
from django_ckeditor_5.widgets import CKEditor5Widget

import logging
from .features.files import views as files_feature_views

logger = logging.getLogger(__name__)

def page_not_found(request, exception=None):
    return render(request, 'errors/404.jinja', status=404)

# Create your views here.
def hello_world(request):
    return render(request, 'test.jinja')

def home(request):
    data = {}
    today = timezone.now().date() 
    # Check if user is already logged in
    if request.user.is_authenticated:
        return redirect('dashboard')

    # Check if there is a form send
    if request.method == "POST":
        # Get data from form
        name = request.POST.get("name")
        email = request.POST.get("email")
        message = request.POST.get("message")
        
        # Get mails of admins
        admin_emails = User.objects.filter(userTypeId__name='admin').values_list('email', flat=True)
        # if everything is filled in
        if name and email and message:
            # Send email via SMTP
            if len(admin_emails) > 0:
                result = send_mail(
                    subject=f"Contact Form DI4D Portal - Message from {name}",
                    message=f"Name : {name}\nEmail: {email}\nMessage:\n{message}",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=admin_emails,
                    fail_silently=False
                )
                if result:
                    data["success"] = "Your message has been sent successfully."
                else:
                    data["error"] = "There was an error sending your message. Please try again later."

    # Check if student can register himself
    application_setting = ApplicationSetting.objects.first()
    if application_setting and application_setting.startDate and application_setting.endDate and application_setting.startDate <= today <= application_setting.endDate and application_setting.studentApplicationFormId:
        data["register"] = True
    else:
        data["register"] = False

    # If there is an application setting, give start and end date
    if application_setting and application_setting.startDate and application_setting.endDate and application_setting.studentApplicationFormId:
        data["startDate"] = application_setting.startDate.strftime('%B %d, %Y')
        data["endDate"] = application_setting.endDate.strftime('%B %d, %Y')
    
    # Get news articles (- : for latest news articles, then we limit to 2 articles)
    data["news"] = News.objects.filter(isPublic=True).order_by('-lastEditDate')[:2]

    return render(request, 'public/home.jinja',  data)

def login_view(request):
    data={}
    # Check if user is already logged in
    if request.user.is_authenticated:
        return redirect('dashboard')

    # Handle login form
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            data["error"] = "Invalid username and/or password"
    return render(request, 'auth/login.jinja', data)

def logout_view(request):
    logout(request)
    return redirect('home')

def preview_files(request):
    """
    HTMX endpoint to preview selected files.
    Stores file names in session and returns HTML with file names for display.
    """
    if request.method == 'POST':
        files = request.FILES.getlist(list(request.FILES.keys())[0]) if request.FILES else []
        file_names = [f.name for f in files]
        # Store in session (append to existing)
        existing = request.session.get('preview_files', [])
        existing.extend(file_names)
        request.session['preview_files'] = existing
        return render(request, 'components/file_list_preview_htmx.jinja', {'file_names': existing})
    return render(request, 'components/file_list_preview_htmx.jinja', {'file_names': []})

def delete_preview_file(request):
    """
    HTMX endpoint to remove a file from the preview list.
    """
    if request.method == 'POST':
        filename = request.POST.get('filename', '')
        existing = request.session.get('preview_files', [])
        if filename in existing:
            existing.remove(filename)
        request.session['preview_files'] = existing
        return render(request, 'components/file_list_preview_htmx.jinja', {'file_names': existing})
    return render(request, 'components/file_list_preview_htmx.jinja', {'file_names': []})

def student_registration(request):
    """
    Display and handle student registration form application.
    Uses the form configuration from ApplicationSetting.
    """
    
    data = {}
    today = timezone.now().date()
    
    # Clear preview files from session on initial GET request
    if request.method == 'GET':
        request.session.pop('preview_files', None)
    
    # Check for success message from previous submission
    data['show_success_modal'] = request.session.pop('show_success_modal', False)

    # Get the application setting (form configuration)
    application_setting = ApplicationSetting.objects.first()
    
    # Check if registration is properly configured
    if not application_setting or not application_setting.studentApplicationFormId or not application_setting.startDate or not application_setting.endDate:
        data['registration_closed'] = True
        return render(request, 'public/student_registration.jinja', data)
    
    # Check if registration is currently open
    if not (application_setting.startDate <= today <= application_setting.endDate):
        data['registration_closed'] = True
        return render(request, 'public/student_registration.jinja', data)
    
    # Get the form and its questions
    form = application_setting.studentApplicationFormId
    questions = Question.objects.filter(formId=form, isActive=True).order_by('id')
    
    data['form'] = form
    data['questions'] = questions
    data['registration_open'] = True
    
    # Handle form submission
    if request.method == 'POST':
        try:
            
            # Get the user's name from the first question
            first_question = questions.first()
            user_name = request.POST.get(f'question_{first_question.id}', '').strip()
            # Clean the name for use in filename (replace spaces and special chars)
            user_name_clean = user_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
            
            # Get submission timestamp as integer (yyyymmddhhmmss format)
            submission_timestamp = int(timezone.now().strftime('%Y%m%d%H%M%S'))
            
            # Save answers for each question
            for question in questions:
                question_id = f'question_{question.id}'
                datatype_name = question.datatype.name.lower()
                answer_value = None
                
                # Handle file upload (multiple files allowed)
                if datatype_name == 'file' and f'{question_id}_file' in request.FILES:
                    uploaded_files = request.FILES.getlist(f'{question_id}_file')
                    file_paths = []
                    
                    for uploaded_file in uploaded_files:
                        # Create unique filename with user info and timestamp
                        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
                        filename = f"{user_name_clean}_{timestamp}_{uploaded_file.name}"
                        
                        # Save file to media/studentregistration/
                        file_path = f'studentregistration/{filename}'
                        default_storage.save(file_path, uploaded_file)
                        file_paths.append(file_path)
                    
                    # Store the file paths as JSON array in the answer
                    answer_value = json.dumps(file_paths) if len(file_paths) > 1 else file_paths[0]
                elif datatype_name == 'multiple_choice':
                    # Multiple choice: store as JSON array
                    selected_values = request.POST.getlist(question_id)
                    if selected_values:
                        answer_value = json.dumps(selected_values)
                else:
                    # Text, Email, Singular_Choice, Bool
                    answer_value = request.POST.get(question_id)
                
                # Only save if answer is provided
                if answer_value:
                    FormAnswer.objects.create(
                    answer=answer_value,
                    questionId=question,
                    answerDate=today,
                    submission_number=submission_timestamp
                    )
            
            # Clear session preview files after successful submission
            request.session.pop('preview_files', None)
            
            # Set success modal for next request
            request.session['show_success_modal'] = True

            # Redirect to home on successful submission
            if request.headers.get('HX-Request') == 'true':
                request.session['show_success_modal'] = True
                response = HttpResponse()
                response['HX-Redirect'] = '/student_registration'
                return response
            return redirect('student_registration')
        except Exception as e:
            data['error'] = f"An error occurred while submitting the form: {str(e)}"
    
    return render(request, 'public/student_registration.jinja', data)

def news(request):
    search_query = ""
    active_page = 'news'

    # User logged in
    if request.user.is_authenticated:
        all_articles = News.objects.filter().order_by("-lastEditDate")
        total_articles = all_articles.count()

        # Check is user is admin
        if request.user.role_is_admin():
            # Check if admin want to delete a news article
            if request.method == "POST" and request.POST.get("delete_id"):
                delete_id = request.POST.get("delete_id")
                news_to_delete = News.objects.get(id=delete_id)
                if news_to_delete:
                    news_to_delete.delete()
                    return  redirect('news')
    # User not logged in
    else:
        all_articles = News.objects.filter(isPublic=True).order_by("-lastEditDate")
        total_articles = all_articles.count()
    
    # Check if somebody want to sort by oldest
    if request.POST.get("sort_by") == "oldest":
        all_articles = all_articles.order_by("lastEditDate")

    # Check if somebody searched for something
    if request.method == "POST":
        search_query = request.POST.get("q", "").strip() or request.GET.get("q", "").strip()
        # Check if search query is not empty
        if search_query:
            all_articles = all_articles.filter(Q(title__icontains=search_query) | Q(lastEditDate__icontains=search_query))
        # Check if there is HTMX request
        if request.headers.get("HX-Request") == "true":
            return render(request, 'components/news_htmx.jinja', {"all_articles": all_articles, "total_articles": total_articles, "search_query": search_query, "active_page": active_page})
    if request.user.is_authenticated:
        return render(request, 'sharepoint/news.jinja', {"all_articles": all_articles, "total_articles": total_articles, "search_query": search_query, "active_page": active_page})
    else:
        return render(request, 'public/news.jinja', {"all_articles": all_articles, "total_articles": total_articles, "search_query": search_query, "active_page": active_page})

@login_required(login_url='login')
def dashboard(request):
    active_page = 'dashboard'
    news = News.objects.all().order_by('-lastEditDate')[:2]
    return render(request, 'sharepoint/dashboard.jinja', {'active_page': active_page, 'news': news})

@login_required(login_url='login')
def files_view(request):
    return files_feature_views.files_view(request)

@login_required(login_url='login')
def files_action(request, action):
    return files_feature_views.files_action(request, action)


@login_required(login_url='login')
def files_download(request, item_token):
    return files_feature_views.files_download(request, item_token)


@login_required(login_url='login')
def files_wopi_open(request, item_token):
    return files_feature_views.files_wopi_open(request, item_token)


@csrf_exempt
def wopi_check_file_info(request, file_id):
    return files_feature_views.wopi_check_file_info(request, file_id)


@csrf_exempt
def wopi_get_file(request, file_id):
    return files_feature_views.wopi_get_file(request, file_id)


@csrf_exempt
def wopi_contents(request, file_id):
    return files_feature_views.wopi_contents(request, file_id)


@csrf_exempt
def wopi_put_file(request, file_id):
    return files_feature_views.wopi_put_file(request, file_id)


@csrf_exempt
def wopi_lock(request, file_id):
    return files_feature_views.wopi_lock(request, file_id)

@login_required(login_url='login')
def users(request):
    search_query = ""
    items_per_page = int(request.GET.get('items_per_page', 10))
    active_page = 'users'
    usertypes = UserType.objects.all()
    partners = Partner.objects.all()
    filteredusertype = "nofilter"

    # Check if user is admin (then show all users)
    if request.user.role_is_admin():
        users = User.objects.filter(is_active=True).order_by('firstname', 'lastname')
    # Check if user is partner (then show only users of that partner)
    if request.user.role_is_partner():
        if request.user.partnerId:
            users = User.objects.filter(partnerId=request.user.partnerId, is_active=True).order_by('firstname', 'lastname')
        else:
            users = User.objects.none()

    # Check if somebody clicked on the delete button / or create/edit user
    if request.method == "POST":
        delete_id = request.POST.get("delete_id")
        if delete_id:
            # Get user to delete (do soft delete)
            user_to_delete = User.objects.get(id=delete_id)
            if user_to_delete:
                user_to_delete.is_active = False
                user_to_delete.save()
                return  redirect('users')
        user_id = request.POST.get("user_id")
        if user_id:
            # Check if we want to create or edit a user
            if user_id == "newuser":
                # Create new user
                user = User()
                temporary_password = get_random_string(length=12)
                user.set_password(temporary_password)
                # Send mail with temporary password
                send_mail(
                    subject="Your DI4D Portal Account",
                    message=f"An account has been created for you on the DI4D Portal.\n\nUsername: {request.POST.get('username')}\nTemporary Password: {temporary_password}\n\nPlease log in and change your password as soon as possible.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[request.POST.get("email")],
                    fail_silently=False
                )
            else:
                # Edit existing user
                user = User.objects.get(id=user_id)
            # Set user data
            try:
                user.username = request.POST.get("username")
                user.firstname = request.POST.get("firstname")
                user.lastname = request.POST.get("lastname")
                user.email = request.POST.get("email")
                user.userTypeId = UserType.objects.get(id=request.POST.get("usertype"))
                user.is_alumni = True if request.POST.get("isalumni") == "on" else False
                # Check if partner is set or empty
                if request.POST.get("partner") != "":
                    user.partnerId = Partner.objects.get(id=request.POST.get("partner"))
                else:
                    user.partnerId = None
                user.save()
            except Exception as e:
                error_message = str(e)
                if 'UNIQUE constraint failed: DI4D_app_user.username' in error_message:
                    error = "Username already exists!"
                elif 'UNIQUE constraint failed: DI4D_app_user.email' in error_message:
                    error = "Email already exists!"
                else:
                    error = "An error occurred while saving the user. Please check the entered data."
                # Return with error message + pagination
                paginator = Paginator(users, items_per_page)
                page_number = request.GET.get('page', 1)
                users = paginator.get_page(page_number)
                return  render(request, 'admin/users.jinja', {"users": users, "search_query": search_query, "active_page": active_page, "usertypes": usertypes, "filteredusertype": filteredusertype, "partners": partners, "error": error, "items_per_page": items_per_page})
            return  redirect('users')

    # Check if user is  admin or partner (otherwise redirect to home)
    if request.user.role_is_admin() or request.user.role_is_partner():
        # Check if somebody used a filter
        usertype = request.POST.get("usertype") or request.GET.get("usertype")
        if usertype and usertype != "nofilter":
            if request.user.role_is_admin():
                users = User.objects.filter(userTypeId__name=usertype, is_active=True)
            if request.user.role_is_partner():
                users = User.objects.filter(userTypeId__name=usertype, partnerId=request.user.partnerId, is_active=True)
            filteredusertype = usertype

        # Check if somebody searched for something
        if request.method == "POST":
            search_query = request.POST.get("q").strip()
            # Check if search query is not empty
            if search_query:
                if request.POST.get("usertype") != "nofilter":
                    users = users.filter(Q(username__icontains=search_query) | Q(firstname__icontains=search_query) | Q(lastname__icontains=search_query) | Q(email__icontains=search_query), is_active=True)
                else:
                    users = User.objects.filter(Q(username__icontains=search_query) | Q(firstname__icontains=search_query) | Q(lastname__icontains=search_query) | Q(email__icontains=search_query), is_active=True)
        
        # Check if there is HTMX request
        if request.headers.get("HX-Request") == "true":
            # Pagination 
            paginator = Paginator(users, items_per_page)
            page_number = request.GET.get('page', 1)
            users = paginator.get_page(page_number)
            return render(request, 'components/user_htmx.jinja', {"users": users, "search_query": search_query, "active_page": active_page, "usertypes": usertypes, "filteredusertype": filteredusertype, "partners": partners, "items_per_page": items_per_page})
        # Pagination
        paginator = Paginator(users, items_per_page)
        page_number = request.GET.get('page', 1)
        users = paginator.get_page(page_number)

        return render(request, 'admin/users.jinja', {"users": users, "search_query": search_query, "active_page": active_page, "usertypes": usertypes, "filteredusertype": filteredusertype, "partners": partners, "items_per_page": items_per_page})
    else:
        return redirect('home')

def tech_talks(request):
    search_query = ""
    active_page = 'Tech Talks'
    
    # Get all tech talks (authenticated users) or public only
    if request.user.is_authenticated:
        all_techtalks = TechTalk.objects.all().order_by("-date", "-id")
    else:
        all_techtalks = TechTalk.objects.filter(isPublic=True).order_by("-date", "-id")
    total_techtalks = all_techtalks.count()
    
    # Check if somebody searched for something
    if request.method == "POST":
        action = request.POST.get("action")
        delete_id = request.POST.get("delete_id")
        if request.user.is_authenticated and (action in ["create", "edit", "delete"] or delete_id):
            if action == "delete" or delete_id:
                if delete_id:
                    TechTalk.objects.filter(id=delete_id).delete()
                return redirect('tech_talks')

            title = request.POST.get("title", "").strip()
            speaker = request.POST.get("speaker", "").strip()
            description = request.POST.get("description", "").strip()
            date_value = request.POST.get("date")
            thubnail = request.POST.get("thubnail", "").strip()
            video_path = request.POST.get("videoPath", "").strip()
            is_public = request.POST.get("isPublic") == "on"

            if action == "create":
                if title and speaker and description and date_value and thubnail and video_path:
                    TechTalk.objects.create(
                        title=title,
                        speaker=speaker,
                        description=description,
                        date=date_value,
                        thubnail=thubnail,
                        videoPath=video_path,
                        isPublic=is_public,
                    )
                return redirect('tech_talks')

            if action == "edit":
                talk_id = request.POST.get("talk_id")
                if talk_id:
                    talk = TechTalk.objects.filter(id=talk_id).first()
                    if talk:
                        talk.title = title
                        talk.speaker = speaker
                        talk.description = description
                        if date_value:
                            talk.date = date_value
                        talk.thubnail = thubnail
                        talk.videoPath = video_path
                        talk.isPublic = is_public
                        talk.save()
                return redirect('tech_talks')

        search_query = request.POST.get("q", "").strip()
        # Check if search query is not empty
        if search_query:
            all_techtalks = all_techtalks.filter(Q(title__icontains=search_query) | Q(speaker__icontains=search_query) | Q(description__icontains=search_query))
        # Check if there is HTMX request
        if request.headers.get("HX-Request") == "true":
            return render(request, 'components/techtalks_htmx.jinja', {"all_techtalks": all_techtalks, "total_techtalks": total_techtalks, "search_query": search_query, "active_page": active_page})
    
    if request.user.is_authenticated:
        return render(request, 'sharepoint/techtalks.jinja', {"all_techtalks": all_techtalks, "total_techtalks": total_techtalks, "search_query": search_query, "active_page": active_page})
    return render(request, 'public/techtalks.jinja', {"all_techtalks": all_techtalks, "total_techtalks": total_techtalks, "search_query": search_query, "active_page": active_page})

def tech_talk_detail(request, talk_id):

    talk = TechTalk.objects.get(id=talk_id, isPublic=True)
    recent_talks = TechTalk.objects.filter(isPublic=True).exclude(id=talk.id).order_by("-date", "-id")[:2]

    video_url = (talk.videoPath or "").strip()
    # Normalize backslashes to forward slashes for URL
    video_url = video_url.replace("\\", "/")
    
    def is_video_by_header(file_path: str) -> bool:
        try:
            kind = filetype.guess(file_path)
            return kind is not None and kind.mime.startswith('video/')
        except Exception:
            return False

    def is_video_by_url(url: str) -> bool:
        try:
            url_request = request.Request(url, method="HEAD")
            with request.urlopen(url_request, timeout=5) as response:
                content_type = response.headers.get('Content-Type', '')
            return content_type.startswith('video/')
        except Exception:
            return False

    is_local_video = False
    if video_url.startswith(('http://', 'https://')):
        is_local_video = is_video_by_url(video_url)
    else:
        local_path = os.path.join(settings.MEDIA_ROOT, video_url.lstrip('/'))
        is_local_video = is_video_by_header(local_path)

    # Build full media URL for local videos
    if is_local_video and not video_url.startswith(('http://', 'https://')):
        # Remove leading slash if present to avoid double slashes
        video_url = video_url.lstrip('/')
        video_url = settings.MEDIA_URL + video_url

    context = {
        "talk": talk,
        "recent_talks": recent_talks,
        "video_url": video_url,
        "is_local_video": is_local_video,
    }

    if request.headers.get("HX-Request") == "true":
        if request.user.is_authenticated:
            return render(request, 'components/techtalk_detail_private_htmx.jinja', context)
        return render(request, 'components/techtalk_detail_htmx.jinja', context)

    if request.user.is_authenticated:
        return render(request, 'sharepoint/techtalk_detail.jinja', context)
    return render(request, 'public/techtalk_detail.jinja', context)

def tech_talk_detail(request, talk_id):

    talk = TechTalk.objects.get(id=talk_id, isPublic=True)
    recent_talks = TechTalk.objects.filter(isPublic=True).exclude(id=talk.id).order_by("-date", "-id")[:2]

    video_url = (talk.videoPath or "").strip()
    # Normalize backslashes to forward slashes for URL
    video_url = video_url.replace("\\", "/")
    
    def is_video_by_header(file_path: str) -> bool:
        try:
            kind = filetype.guess(file_path)
            return kind is not None and kind.mime.startswith('video/')
        except Exception:
            return False

    def is_video_by_url(url: str) -> bool:
        try:
            url_request = request.Request(url, method="HEAD")
            with request.urlopen(url_request, timeout=5) as response:
                content_type = response.headers.get('Content-Type', '')
            return content_type.startswith('video/')
        except Exception:
            return False

    is_local_video = False
    if video_url.startswith(('http://', 'https://')):
        is_local_video = is_video_by_url(video_url)
    else:
        local_path = os.path.join(settings.MEDIA_ROOT, video_url.lstrip('/'))
        is_local_video = is_video_by_header(local_path)

    # Build full media URL for local videos
    if is_local_video and not video_url.startswith(('http://', 'https://')):
        # Remove leading slash if present to avoid double slashes
        video_url = video_url.lstrip('/')
        video_url = settings.MEDIA_URL + video_url

    context = {
        "talk": talk,
        "recent_talks": recent_talks,
        "video_url": video_url,
        "is_local_video": is_local_video,
    }

    if request.headers.get("HX-Request") == "true":
        return render(request, 'components/techtalk_detail_htmx.jinja', context)

    return render(request, 'public/techtalk_detail.jinja', context)

@login_required(login_url='login')
def settings_view(request):
    active_page = 'settings'
    
    # Chek if application settings exist, otherwise create default one
    application_setting, created = ApplicationSetting.objects.get_or_create(id=1)

    current_application_setting = {
        "startDate": application_setting.startDate,
        "endDate": application_setting.endDate,
        "studentApplicationFormId": application_setting.studentApplicationFormId
    }
    forms = Form.objects.filter(isActive=True)
    if request.method == 'POST':
        # Check if it is to change password
        if request.POST.get("changepassword"):
            new_password = request.POST.get("newpassword")
            confirm_password = request.POST.get("confirmnewpassword")
            if new_password == confirm_password and new_password != "" and confirm_password != "":
                request.user.set_password(new_password)
                request.user.save()
                # Keep the user logged in after changing password
                update_session_auth_hash(request, request.user)

                return render(request, 'sharepoint/settings.jinja', {'active_page': active_page, 'success_password': "Password changed successfully", 'forms': forms, 'current_application_setting': current_application_setting})
            else:
                return render(request, 'sharepoint/settings.jinja', {'active_page': active_page, 'error_password': "Passwords do not match and/or are empty", 'forms': forms, 'current_application_setting': current_application_setting})
        # Check if it is to change profile settings
        if request.POST.get("changeprofile"):
            try: 
                firstname = request.POST.get("firstname")
                lastname = request.POST.get("lastname")
                email = request.POST.get("email")

                # Check if email already exists (for another user)
                if User.objects.filter(email=email).exclude(id=request.user.id).exists():
                    return render(request, 'sharepoint/settings.jinja', {'active_page': active_page, 'error_profile': "Email already exists!", 'forms': forms, 'current_application_setting': current_application_setting})

                # Update user info
                request.user.first_name = firstname
                request.user.last_name = lastname
                request.user.email = email
                # Check if there was a profile picture uploaded
                if request.FILES.get("profilepicture"):
                    # Image will be automatically saved to the correct location because of the ImageField in the User model (pillow)
                    request.user.profilePicture = request.FILES["profilepicture"]
                request.user.save()
            except Exception as e:
                return render(request, 'sharepoint/settings.jinja', {'active_page': active_page, 'error_profile': f"An error occurred while updating profile: {e}", 'forms': forms, 'current_application_setting': current_application_setting})
            return render(request, 'sharepoint/settings.jinja', {'active_page': active_page, 'success_profile': "Profile updated successfully", 'forms': forms, 'current_application_setting': current_application_setting})
        
        # Check if application settings is changed
        if request.POST.get("applicationsettings"):
            applicationsetting = ApplicationSetting.objects.get(id=1)
            applicationsetting.startDate = None if request.POST.get("startdatestudentregistrationform") == "" else request.POST.get("startdatestudentregistrationform")
            applicationsetting.endDate = None if request.POST.get("enddatestudentregistrationform") == "" else request.POST.get("enddatestudentregistrationform")
            applicationsetting.studentApplicationFormId = None if request.POST.get("studentregistrationform") == "noform" else Form.objects.get(id=request.POST.get("studentregistrationform"))
            applicationsetting.save()

            # Check if student application form is currently in our history
            if applicationsetting.studentApplicationFormId and applicationsetting.startDate:
                history_form = HistoryStudentApplicationForm.objects.get_or_create(formId=applicationsetting.studentApplicationFormId, year=applicationsetting.startDate[:4])

            # Change current application setting
            current_application_setting = {
                "startDate": applicationsetting.startDate,
                "endDate": applicationsetting.endDate,
                "studentApplicationFormId": applicationsetting.studentApplicationFormId
            }
            return render(request, 'sharepoint/settings.jinja', {'active_page': active_page, 'success_application': "Application settings updated successfully", 'forms': forms, 'current_application_setting': current_application_setting})
    return render(request, 'sharepoint/settings.jinja', {'active_page': active_page, 'forms': forms, 'current_application_setting': current_application_setting})

@login_required(login_url='login')
def export_data(request):
    active_page = 'export_data'
    # Check if user is admin
    if request.user.role_is_admin():
        return render(request, 'admin/export.jinja', {'active_page': active_page})
    else:
        return redirect('dashboard')

@login_required(login_url='login')
def users_data(request):
    # Check if user is admin
    if request.user.role_is_admin():        
        # Get all users
        all_users = User.objects.all().order_by("username")
        csv_data = "Username,FirstName,LastName,Email,IsActive,UserType,Partner,IsActive,IsAlumni\n"
        
        for user in all_users:
            csv_data += f"{user.username},{user.firstname},{user.lastname},{user.email},{user.is_active},{user.userTypeId.name},{user.partnerId.name if user.partnerId else ''},{user.is_active},{user.is_alumni}\n"

        # Create response with CSV data
        response = HttpResponse(csv_data, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="users_data.csv"'
        return response

@login_required(login_url='login')
def learninggoals_data(request):
    # Check if user is admin
    if request.user.role_is_admin():        
        # Get all learning goals
        all_learninggoals = LearningGoal.objects.all().order_by("id")
        csv_data = "Objective,learningPath,IsActive,Courses\n"

        for learninggoal in all_learninggoals:
            courses = LearninggoalCourse.objects.filter(learningGoalId=learninggoal)
            courses_list = [course.courseId.name for course in courses]
            # Split courses by ;
            courses_list = ";".join(courses_list)
            csv_data += f"{learninggoal.objective},{learninggoal.learningPath.name},{learninggoal.isActive},{courses_list}\n"

        # Create response with CSV data
        response = HttpResponse(csv_data, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="learninggoals_data.csv"'
        return response
   
@login_required(login_url='login')
def edit_news(request, mediaPath=None):
    active_page = 'news'
    # Check if user is admin
    if not request.user.role_is_admin():
        return redirect('dashboard')

    # Create form for editing/creating news without using a predefined form class
    NewsForm = modelform_factory(News, fields=['title', 'isPublic', 'showAuthor', 'picture', 'description', 'content'], widgets={'content': CKEditor5Widget()})
    # check if there is an existing news article to edit
    instance = get_object_or_404(News, mediaPath=mediaPath) if mediaPath else None
    # Create the form instance
    form = NewsForm(request.POST or None, request.FILES or None, instance=instance)

    # Check if form is submitted
    if request.method == "POST":
        #  Because we do form save it automatically handles create and edit
        news_article = form.save(commit=False)
        news_article.lastEditDate = timezone.now()
        news_article.author = request.user
        news_article.save()

        # Redirect to news page after saving with saved in session
        request.session['news_saved'] = True
        return redirect(f'/news/edit/{news_article.mediaPath}/')

    # Check if saved parameter is in session
    saved = request.session.pop('news_saved', False)

    # Check if mediaPath is provided
    if mediaPath:
        return render(request, 'admin/edit_news.jinja', {'mediaPath': mediaPath, 'active_page': active_page, 'form': form, 'saved': saved})
    return render(request, 'admin/edit_news.jinja', {'active_page': active_page, 'form': form, 'saved': saved})

def view_news_item(request, mediaPath):
    # Check if user is logged in
    if request.user.is_authenticated:
        active_page = 'news'
        # Get the news article by mediaPath (private + public)
        news_article = get_object_or_404(News, mediaPath=mediaPath)
        # Take 2 other random news articles for suggestion at the bottom
        news = News.objects.all().exclude(id=news_article.id).order_by('?')[:2]
        return render(request, 'sharepoint/news_item.jinja', {'news_article': news_article, 'news': news, 'active_page': active_page})
    else:
        # Get the news article by mediaPath (only public)
        news_article = get_object_or_404(News, mediaPath=mediaPath, isPublic=True)
        # Take 2 other random news articles for suggestion at the bottom
        news = News.objects.filter(isPublic=True).exclude(id=news_article.id).order_by('?')[:2]
        return render(request, 'public/news_item.jinja', {'news_article': news_article, 'news': news})

@login_required(login_url='login')
def forms_view(request):
    """
    Display all available forms for SharePoint users.
    Shows form status (not started, in progress, completed) and allows filtering.
    """
    active_page = 'forms'
    search_query = ""
    filter_status = request.POST.get('filter_status') or request.GET.get('filter_status') or 'all'
    items_per_page = int(request.GET.get('items_per_page', 6))
    today = timezone.now().date()
    
    # Get all active forms
    all_forms = Form.objects.filter(isActive=True).order_by('-startDate', 'title')
    
    # Exclude student registration
    history_application_form = HistoryStudentApplicationForm.objects.all()
    excluded_form_ids = history_application_form.values_list('formId', flat=True)
    if excluded_form_ids:
        if not request.user.role_is_admin():
            all_forms = all_forms.exclude(id__in=excluded_form_ids)
        else:
            for excluded_id in excluded_form_ids:
                # For admins, make a mark that this form is the student registration form
                for form in all_forms:
                    if form.id == excluded_id:
                        form.is_student_registration = True
    
    # Handle CRUD actions (admin only)
    if request.method == "POST" and request.user.role_is_admin():
        delete_id = request.POST.get("delete_id")
        action = request.POST.get("action")

        if delete_id:
            form_to_delete = Form.objects.filter(id=delete_id).first()
            if form_to_delete:
                # Soft-delete: mark form as inactive instead of removing from DB
                form_to_delete.isActive = False
                form_to_delete.save()
            return redirect('forms')

        if action == "create":
            title = request.POST.get("title", "").strip()
            start_date = request.POST.get("startDate")
            end_date = request.POST.get("endDate", "NoEndDate")
            if title and start_date:
                new_form = Form.objects.create(
                    userId=request.user,
                    title=title,
                    startDate=start_date,
                    isActive=True
                )
                if end_date and end_date != "NoEndDate":
                    new_form.endDate = end_date
                    new_form.save()
                return redirect('form_builder', form_id=new_form.id)
            return redirect('forms')

        if action == "edit":
            form_id = request.POST.get("form_id")
            title = request.POST.get("title", "").strip()
            start_date = request.POST.get("startDate")
            end_date = request.POST.get("endDate", "NoEndDate")
            is_active = request.POST.get("isActive") == "on"
            form_to_edit = Form.objects.filter(id=form_id).first()
            if form_to_edit and title and start_date and end_date:
                form_to_edit.title = title
                form_to_edit.startDate = start_date
                form_to_edit.endDate = end_date if end_date != "NoEndDate" else None
                form_to_edit.isActive = is_active
                form_to_edit.save()
            return redirect('forms')

        # Search filter
        search_query = request.POST.get("q", "").strip()
        if search_query:
            all_forms = all_forms.filter(Q(title__icontains=search_query))
    
    # Build form data with status for current user
    forms_with_status = []
    for form in all_forms:
        # Check if user has answered any questions for this form
        questions = Question.objects.filter(formId=form, isActive=True)
        mandatory_questions = questions.filter(isMandatory=True)
        submitted_answers = FormAnswer.objects.filter(
            questionId__in=questions,
            userId=request.user
        )
        
        # Determine status
        deadline_passed = form.endDate and form.endDate < today
        total_questions = questions.count()
        total_mandatory_questions = mandatory_questions.count()
        answered_questions = submitted_answers.values('questionId').distinct().count()
        answered_mandatory_questions = submitted_answers.filter(
            questionId__isMandatory=True
        ).values('questionId').distinct().count()

        if total_mandatory_questions > 0:
            is_completed = answered_mandatory_questions >= total_mandatory_questions
        else:
            is_completed = answered_questions >= total_questions and total_questions > 0
        
        if is_completed:
            status = 'completed'
        elif answered_questions > 0:
            status = 'in_progress'
        else:
            status = 'not_started'
        
        forms_with_status.append({
            'form': form,
            'status': status,
            'deadline_passed': deadline_passed,
            'answered_count': answered_questions,
            'total_count': total_questions
        })
    
    # Filter by status
    if filter_status and filter_status != 'all':
        forms_with_status = [f for f in forms_with_status if f['status'] == filter_status]
    
    # Pagination
    paginator = Paginator(forms_with_status, items_per_page)
    page_number = request.GET.get('page', 1)
    forms_page = paginator.get_page(page_number)
    
    context = {
        'all_forms': forms_page,
        'search_query': search_query,
        'filter_status': filter_status,
        'items_per_page': items_per_page,
        'active_page': active_page,
        'today': today.strftime('%Y-%m-%d')
    }
    
    # Check if HTMX request
    if request.headers.get("HX-Request") == "true":
        return render(request, 'components/forms_htmx.jinja', context)
    
    return render(request, 'sharepoint/forms.jinja', context)

@login_required(login_url='login')
def form_detail_view(request, form_id):
    """
    Display and handle form submission for SharePoint users.
    Styled with white/grey theme.
    """
    active_page = 'forms'
    data = {'active_page': active_page}
    today = timezone.now().date()
    
    # Clear preview files from session on initial GET request
    if request.method == 'GET':
        request.session.pop('preview_files', None)
    
    # Check for success message from previous submission
    data['show_success_modal'] = request.session.pop('show_form_success_modal', False)
    
    # Get the form
    form = get_object_or_404(Form, id=form_id, isActive=True)
    data['form'] = form
    if form.endDate and form.endDate < today:
        data['form_closed'] = True
        return render(request, 'sharepoint/form_detail.jinja', data)
    
    # Check if form hasn't started yet
    if form.startDate and form.startDate > today:
        data['form_closed'] = True
        data['error'] = f"This form is not yet available. It opens on {form.startDate.strftime('%B %d, %Y')}."
        return render(request, 'sharepoint/form_detail.jinja', data)
    
    # Get questions for this form
    questions = Question.objects.filter(formId=form, isActive=True).order_by('id')
    data['questions'] = questions
    
    # Check if user has already completed the form
    user_answers = FormAnswer.objects.filter(
        questionId__in=questions,
        userId=request.user
    )
    mandatory_questions = questions.filter(isMandatory=True)
    total_questions = questions.count()
    total_mandatory_questions = mandatory_questions.count()
    answered_questions = user_answers.values('questionId').distinct().count()
    answered_mandatory_questions = user_answers.filter(
        questionId__isMandatory=True
    ).values('questionId').distinct().count()

    if total_mandatory_questions > 0:
        already_completed = answered_mandatory_questions >= total_mandatory_questions
    else:
        already_completed = answered_questions >= total_questions and total_questions > 0

    if already_completed:
        data['already_completed'] = True
        return render(request, 'sharepoint/form_detail.jinja', data)
    
    # Build existing answers map for prefilling
    existing_answers = {}
    existing_answers_multi = {}
    all_existing = FormAnswer.objects.filter(
        questionId__in=questions,
        userId=request.user
    ).order_by('-answerDate')
    for answer in all_existing:
        qid = answer.questionId.id
        datatype_name = answer.questionId.datatype.name.lower()
        if datatype_name == 'multiple_choice':
            try:
                existing_answers_multi[qid] = json.loads(answer.answer)
            except Exception:
                existing_answers_multi[qid] = []
        else:
            existing_answers[qid] = answer.answer or ''

    data['existing_answers'] = existing_answers
    data['existing_answers_multi'] = existing_answers_multi
    data['form_open'] = True
    
    # Handle form submission
    if request.method == 'POST':
        try:
            # Save answers for each question
            for question in questions:
                question_id = f'question_{question.id}'
                datatype_name = question.datatype.name.lower()
                answer_value = None
                
                # Handle file upload
                if datatype_name == 'file' and f'{question_id}_file' in request.FILES:
                    uploaded_files = request.FILES.getlist(f'{question_id}_file')
                    file_paths = []
                    
                    for uploaded_file in uploaded_files:
                        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
                        filename = f"{request.user.username}_{timestamp}_{uploaded_file.name}"
                        file_path = f'forms/{form_id}/{filename}'
                        default_storage.save(file_path, uploaded_file)
                        file_paths.append(file_path)
                    
                    answer_value = json.dumps(file_paths) if len(file_paths) > 1 else file_paths[0] if file_paths else None
                elif datatype_name == 'multiple_choice':
                    selected_values = request.POST.getlist(question_id)
                    if selected_values:
                        answer_value = json.dumps(selected_values)
                else:
                    answer_value = request.POST.get(question_id)
                
                # Only save if answer is provided
                if answer_value:
                    FormAnswer.objects.update_or_create(
                        questionId=question,
                        userId=request.user,
                        defaults={
                            'answer': answer_value,
                            'answerDate': today
                        }
                    )
            
            # Clear session preview files
            request.session.pop('preview_files', None)
            
            # Set success modal
            request.session['show_form_success_modal'] = True
            
            # Handle HTMX redirect
            if request.headers.get('HX-Request') == 'true':
                response = HttpResponse()
                response['HX-Redirect'] = f'/forms/{form_id}/'
                return response
            return redirect('form_detail', form_id=form_id)
            
        except Exception as e:
            data['error'] = f"An error occurred while submitting the form: {str(e)}"
    
    return render(request, 'sharepoint/form_detail.jinja', data)

@login_required(login_url='login')
def form_autosave(request, form_id):
    """
    Lightweight autosave for SharePoint forms (non-file fields).
    Saves a single field change with minimal payload.
    """
    if request.method != 'POST':
        return HttpResponse(status=405)

    # Ignore file uploads for autosave
    if request.FILES:
        return HttpResponse(status=204)

    # Determine question id
    question_id = request.POST.get('question_id')
    if not question_id:
        for key in request.POST.keys():
            if key.startswith('question_'):
                question_id = key.replace('question_', '')
                break

    if not question_id:
        return HttpResponse(status=400)

    question = get_object_or_404(Question, id=question_id, formId_id=form_id)
    datatype_name = question.datatype.name.lower()

    if datatype_name == 'multiple_choice':
        selected_values = request.POST.getlist(f'question_{question_id}')
        answer_value = json.dumps(selected_values) if selected_values else ''
    else:
        answer_value = request.POST.get(f'question_{question_id}', '')

    if not answer_value:
        FormAnswer.objects.filter(questionId=question, userId=request.user).delete()
        return HttpResponse(status=204)

    FormAnswer.objects.update_or_create(
        questionId=question,
        userId=request.user,
        defaults={
            'answer': answer_value,
            'answerDate': timezone.now().date()
        }
    )

    return HttpResponse(status=204)

@login_required(login_url='login')
def form_submissions(request, form_id):
    # Only admins can view submissions
    if not request.user.role_is_admin():
        return redirect('forms')
    
    active_page = 'forms'
    form = get_object_or_404(Form, id=form_id, isActive=True)
    questions = Question.objects.filter(formId=form, isActive=True)

    answers = FormAnswer.objects.filter(questionId__in=questions, userId__isnull=False)
    user_ids = answers.values_list('userId', flat=True).distinct()
    users = User.objects.filter(id__in=user_ids).order_by('firstname', 'lastname')

    total_questions = questions.count()
    total_mandatory_questions = questions.filter(isMandatory=True).count()
    user_rows = []
    for user in users:
        user_answer_count = answers.filter(userId=user).values('questionId').distinct().count()
        user_mandatory_answer_count = answers.filter(
            userId=user,
            questionId__isMandatory=True
        ).values('questionId').distinct().count()

        if total_mandatory_questions > 0:
            is_submitted = user_mandatory_answer_count >= total_mandatory_questions
        else:
            is_submitted = total_questions > 0 and user_answer_count >= total_questions

        if is_submitted:
            submitted_date = answers.filter(userId=user).order_by('-answerDate').values_list('answerDate', flat=True).first()
            user_rows.append({
                'user': user,
                'submitted_date': submitted_date
            })

    return render(request, 'sharepoint/form_submissions.jinja', {
        'active_page': active_page,
        'form': form,
        'user_rows': user_rows
    })

@login_required(login_url='login')
def form_submission_detail(request, form_id, username):
    # Only admins can view individual submissions
    if not request.user.role_is_admin():
        return redirect('forms')
    active_page = 'forms'
    form = get_object_or_404(Form, id=form_id, isActive=True)
    questions = Question.objects.filter(formId=form, isActive=True).order_by('id')
    user = get_object_or_404(User, username=username)
    MEDIA_URL = settings.MEDIA_URL

    answers = FormAnswer.objects.filter(questionId__in=questions, userId=user)
    answer_map = {}
    for ans in answers:
        datatype_name = ans.questionId.datatype.name.lower()
        if datatype_name == 'multiple_choice':
            try:
                answer_map[ans.questionId.id] = json.loads(ans.answer)
            except Exception:
                answer_map[ans.questionId.id] = []
        else:
            answer_map[ans.questionId.id] = ans.answer

    return render(request, 'sharepoint/form_submission_detail.jinja', {'active_page': active_page, 'form': form, 'user': user, 'questions': questions, 'answer_map': answer_map, 'MEDIA_URL': MEDIA_URL})

@login_required(login_url='login')
def form_builder_view(request, form_id=None):
    """
    Form builder page for creating/editing forms and questions.
    Admin only.
    """
    # Only admins can access form builder
    if not request.user.role_is_admin():
        return redirect('forms')
    
    active_page = 'forms'
    data_types = DataType.objects.all()
    today = timezone.now().date().strftime('%Y-%m-%d')
    
    if form_id:
        form = get_object_or_404(Form, id=form_id)
        questions = Question.objects.filter(formId=form, isActive=True).order_by('id')
    else:
        form = None
        questions = []
    
    # Handle form settings update
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_settings':
            title = request.POST.get('title', '').strip()
            start_date = request.POST.get('startDate')
            end_date = request.POST.get('endDate', 'NoEndDate')
            
            if title and start_date:
                if form:
                    # Existing form - update directly
                    questions = Question.objects.filter(formId=form, isActive=True).order_by('id')
                    incomplete_questions = []
                    for q in questions:
                        if q.isMandatory:
                            if not q.question or not q.question.strip():
                                incomplete_questions.append(q.id)
                                continue
                            dtype_name = q.datatype.name.lower() if q.datatype else ''
                            if dtype_name in ['multiple_choice', 'singular_choice']:
                                options = [opt.strip() for opt in (q.content or '').split(',') if opt.strip()]
                                if len(options) == 0:
                                    incomplete_questions.append(q.id)

                    if incomplete_questions:
                        return render(request, 'sharepoint/form_builder.jinja', {
                            'active_page': active_page,
                            'form': form,
                            'questions': questions,
                            'question': questions.first() if questions else None,
                            'data_types': data_types,
                            'today': today,
                            'form_error': 'Cannot save: some required questions are incomplete. Please finish them in the editor before saving.'
                        })

                    form.title = title
                    form.startDate = start_date
                    if end_date != "NoEndDate" and end_date:
                        form.endDate = end_date
                    form.save()
                    return redirect('forms')
                else:
                    # New form - create it and stay on page (don't redirect)
                    form = Form.objects.create(
                        userId=request.user,
                        title=title,
                        startDate=start_date,
                        isActive=True
                    )
                    if end_date != "NoEndDate":
                        form.endDate = end_date
                        form.save()
                    questions = []
    
    return render(request, 'sharepoint/form_builder.jinja', {'active_page': active_page, 'form': form, 'questions': questions, 'question': questions.first() if questions else None, 'data_types': data_types, 'today': today})

@login_required(login_url='login')
def form_builder_add_question(request, form_id):
    """
    Add a new question to the form (HTMX endpoint).
    Admin only.
    """
    if not request.user.role_is_admin():
        return HttpResponse(status=403)
    
    form = get_object_or_404(Form, id=form_id)
    data_types = DataType.objects.all()
    default_datatype = data_types.first()
    
    # Create new question
    new_question = Question.objects.create(
        formId=form,
        datatype=default_datatype,
        question='',
        isActive=True,
        isMandatory=False
    )
    
    questions = Question.objects.filter(formId=form, isActive=True).order_by('id')
    
    return render(request, 'components/questions_list_htmx.jinja', {'form': form, 'questions': questions, 'question': new_question,'data_types': data_types,})

@login_required(login_url='login')
def form_builder_delete_question(request, form_id):
    """
    Delete a question from the form (HTMX endpoint).
    Admin only.
    """
    if not request.user.role_is_admin():
        return HttpResponse(status=403)
    
    form = get_object_or_404(Form, id=form_id)
    question_id = request.POST.get('question_id')
    
    if question_id:
        question = Question.objects.filter(id=question_id, formId=form).first()
        if question:
            question.isActive = False
            question.save()
    
    questions = Question.objects.filter(formId=form, isActive=True).order_by('id')
    
    return render(request, 'components/questions_list_htmx.jinja', {'form': form,'questions': questions,})

@login_required(login_url='login')
def form_builder_get_question(request, form_id, question_id):
    """
    Get a single question for editing (HTMX endpoint).
    Admin only.
    """
    if not request.user.role_is_admin():
        return HttpResponse(status=403)
    
    form = get_object_or_404(Form, id=form_id)
    question = get_object_or_404(Question, id=question_id, formId=form, isActive=True)
    data_types = DataType.objects.all()
    
    return render(request, 'components/question_editor_htmx.jinja', {'form': form, 'question': question, 'data_types': data_types})

@login_required(login_url='login')
def form_builder_update_question(request, form_id, question_id):
    """
    Update a question's details (HTMX endpoint).
    Admin only.
    """
    if not request.user.role_is_admin():
        return HttpResponse(status=403)
    
    form = get_object_or_404(Form, id=form_id)
    question = get_object_or_404(Question, id=question_id, formId=form)
    data_types = DataType.objects.all()
    
    question_text = request.POST.get('question_text', '').strip()
    datatype_id = request.POST.get('datatype_id')
    is_mandatory = request.POST.get('is_mandatory') == 'yes'
    explanation = request.POST.get('explanation', '').strip()
    
    # Track if datatype actually changed
    datatype_changed = False
    old_datatype_id = question.datatype.id if question.datatype else None
    
    if question_text:
        question.question = question_text
    if datatype_id:
        new_datatype_id = int(datatype_id)
        if old_datatype_id != new_datatype_id:
            datatype_changed = True
            question.datatype = DataType.objects.get(id=new_datatype_id)
            # Clear content if changing away from choice types
            datatype_name = question.datatype.name.lower()
            if datatype_name not in ['multiple_choice', 'singular_choice']:
                question.content = ''
    question.isMandatory = is_mandatory
    question.explanation = explanation
    question.save()
    
    questions = Question.objects.filter(formId=form, isActive=True).order_by('id')
    
    # If datatype changed, return the editor template with OOB list update
    if datatype_changed:
        return render(request, 'components/question_editor_htmx.jinja', {
            'form': form,
            'question': question,
            'questions': questions,
            'data_types': data_types,
            'update_questions_list': True
        })
    
    # Otherwise just return the list (updates sidebar only)
    return render(request, 'components/questions_list_htmx.jinja', {
        'form': form,
        'questions': questions
    })

@login_required(login_url='login')
def form_builder_add_option(request, form_id, question_id):
    """
    Add an option to a multiple/singular choice question (HTMX endpoint).
    Admin only.
    """
    if not request.user.role_is_admin():
        return HttpResponse(status=403)
    
    form = get_object_or_404(Form, id=form_id)
    question = get_object_or_404(Question, id=question_id, formId=form)
    
    # Get current options
    options = [opt.strip() for opt in question.content.split(',') if opt.strip()] if question.content else []
    
    # Add new option
    options.append(f'Option {len(options) + 1}')
    question.content = ','.join(options)
    question.save()
    
    return render(request, 'components/question_options_htmx.jinja', {
        'form': form,
        'question': question
    })

@login_required(login_url='login')
def form_builder_delete_option(request, form_id, question_id):
    """
    Delete an option from a multiple/singular choice question (HTMX endpoint).
    Admin only.
    """
    if not request.user.role_is_admin():
        return HttpResponse(status=403)
    
    form = get_object_or_404(Form, id=form_id)
    question = get_object_or_404(Question, id=question_id, formId=form)
    option_index = int(request.POST.get('option_index', -1))
    
    # Get current options
    options = [opt.strip() for opt in question.content.split(',') if opt.strip()] if question.content else []
    
    # Remove option at index
    if 0 <= option_index < len(options):
        options.pop(option_index)
        question.content = ','.join(options)
        question.save()
    
    return render(request, 'components/question_options_htmx.jinja', {
        'form': form,
        'question': question
    })

@login_required(login_url='login')
def form_builder_update_option(request, form_id, question_id):
    """
    Update an option value (HTMX endpoint).
    Admin only.
    """
    if not request.user.role_is_admin():
        return HttpResponse(status=403)
    
    form = get_object_or_404(Form, id=form_id)
    question = get_object_or_404(Question, id=question_id, formId=form)
    option_index = int(request.POST.get('option_index', -1))
    option_value = request.POST.get('option_value', '').strip()
    
    # Get current options
    options = [opt.strip() for opt in question.content.split(',') if opt.strip()] if question.content else []
    
    # Update option at index
    if 0 <= option_index < len(options) and option_value:
        options[option_index] = option_value
        question.content = ','.join(options)
        question.save()
    
    return render(request, 'components/question_options_htmx.jinja', {
        'form': form,
        'question': question
    })

# Made to reduce URL count

@login_required(login_url='login')
def manage_questions(request, form_id):
    """
    Consolidated endpoint for managing questions (add/delete).
    Admin only.
    - POST without question_id: add new question
    - POST with question_id: delete question
    """
    if not request.user.role_is_admin():
        return HttpResponse(status=403)
    
    if request.method == 'POST':
        question_id = request.POST.get('question_id')
        if question_id:
            # Delete question
            return form_builder_delete_question(request, form_id)
        else:
            # Add question
            return form_builder_add_question(request, form_id)
    return HttpResponse(status=405)

@login_required(login_url='login')
def manage_question_detail(request, form_id, question_id):
    """
    Consolidated endpoint for individual question operations.
    Admin only.
    - GET: retrieve question for editing
    - POST: update question
    """
    if not request.user.role_is_admin():
        return HttpResponse(status=403)
    
    if request.method == 'GET':
        return form_builder_get_question(request, form_id, question_id)
    elif request.method == 'POST':
        return form_builder_update_question(request, form_id, question_id)
    return HttpResponse(status=405)

@login_required(login_url='login')
def manage_question_options(request, form_id, question_id):
    """
    Consolidated endpoint for managing question options.
    Admin only.
    - POST with action=add: add option
    - POST with action=delete: delete option
    - POST with action=update: update option
    """
    if not request.user.role_is_admin():
        return HttpResponse(status=403)
    
    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'add':
            return form_builder_add_option(request, form_id, question_id)
        elif action == 'delete':
            return form_builder_delete_option(request, form_id, question_id)
        elif action == 'update':
            return form_builder_update_option(request, form_id, question_id)
    return HttpResponse(status=405)

def student_registrations(request):
    # Check if user is admin
    if not request.user.role_is_admin():
        return redirect('dashboard')
    active_page = 'student_registrations'
    search_query = ""
    items_per_page = int(request.GET.get('items_per_page', 10))
    filtered_year = "nofilter"
    filtered_status = "nofilter"

    # Get all student registration submitions
    all_registration_forms = HistoryStudentApplicationForm.objects.all()
    form_ids = all_registration_forms.values_list('formId', flat=True)
    years = all_registration_forms.values_list('year', flat=True)
    student_registrations = FormAnswer.objects.filter(questionId__formId__in=form_ids)
    submission_numbers = student_registrations.values_list('submission_number', 'answerDate').exclude(submission_number__isnull=True).distinct()

    # Format submission date
    submission_numbers = [(num, date.strftime('%d/%m/%Y'), date.year) for num, date in submission_numbers]

    # Get or Create status for each submission a status
    submissions = []
    for submission in submission_numbers:
        status, created = StatusStudentRegistration.objects.get_or_create(submission_number=int(submission[0]))
        submissions.append((submission[0], submission[1], status.status, submission[2]))
    
    # Pagination
    paginator = Paginator(submissions, items_per_page)
    page_number = request.GET.get('page', 1)
    submissions = paginator.get_page(page_number)

    # Check if it is a htmx request
    if request.headers.get("HX-Request") == "true":
        # Check if somebody searched for something or filtered something
        search_query = request.POST.get("q", "").strip()
        year_filter = request.POST.get("year", "nofilter")
        status_filter = request.POST.get("status", "nofilter")
        if search_query:
            # Filter submissions by search query (on submission number or date)
            submissions = [s for s in submissions if search_query.lower() in str(s[0]).lower() or search_query.lower() in str(s[1]).lower()]
        if year_filter != "nofilter":
            submissions = [s for s in submissions if s[3] == int(year_filter)]
            filtered_year = year_filter
        if status_filter != "nofilter":
            submissions = [s for s in submissions if s[2] == status_filter]
            filtered_status = status_filter
        # Pagination
        paginator = Paginator(submissions, items_per_page)
        page_number = request.GET.get('page', 1)
        submissions = paginator.get_page(page_number)
        return render(request, 'components/student_registration_htmx.jinja', {'active_page': active_page, 'search_query': search_query, 'submissions': submissions, 'years': years, 'filtered_year': filtered_year, 'filtered_status': filtered_status, 'items_per_page': items_per_page})

    return render(request, 'admin/student_registrations.jinja', {'active_page': active_page, 'search_query': search_query, 'submissions': submissions, 'years': years, 'filtered_year': filtered_year, 'filtered_status': filtered_status, 'items_per_page': items_per_page})

@login_required(login_url='login')
def student_registration_detail(request, submission_number):
    # Check if user is admin
    if not request.user.role_is_admin():
        return redirect('dashboard')
    active_page = 'student_registrations'
    status = ""
    x_data =  '{"open_info": false}'
    MEDIA_URL = settings.MEDIA_URL

    # Get Status or 404 if not exist
    item = get_object_or_404(StatusStudentRegistration, submission_number=submission_number)

    # Get all answers of the submission
    answers = FormAnswer.objects.filter(submission_number=submission_number)
    for answer in answers:
            # Parse answer
            if answer.questionId.datatype.name == "Multiple_Choice":
                answer.parsed_answer = json.loads(answer.answer) if answer.answer else []
            elif answer.questionId.datatype.name == "File":
                # Get type of file
                full_path = os.path.join(settings.MEDIA_ROOT, str(answer.answer))
                mime_type = None
                try:
                    matches = puremagic.magic_file(full_path)
                    if isinstance(matches, list) and matches:
                        first_match = matches[0]
                        if isinstance(first_match, (list, tuple)) and len(first_match) > 1:
                            mime_type = first_match[1] or None
                except Exception:
                    mime_type = None
                answer.file_type = mime_type.split('/')[0] if mime_type else 'unknown'
    
    # Check if form is submitted to approve or deny the registration
    if request.method == "POST":
        submit_value = request.POST.get("submit")
        if submit_value == "approve":
            item.status = "approved"
            status = "approved"
        elif submit_value == "deny":
            item.status = "denied"
            status = "denied"
        x_data = '{"open_info": true}'
        item.save()
    return render(request, 'admin/registration_detail.jinja', {'active_page': active_page, 'item': item, 'answers': answers, 'MEDIA_URL': MEDIA_URL, 'status': status, 'x_data': x_data})
