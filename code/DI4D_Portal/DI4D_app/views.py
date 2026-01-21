from django.http import HttpResponse
from urllib import request
from django.utils import timezone
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib.auth import authenticate, login
from .models import ApplicationSetting, News, User, Question, FormAnswer, TechTalk, Form, UserType, Partner, LearningGoal, LearninggoalCourse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.crypto import get_random_string
from django.contrib.auth import update_session_auth_hash
import os
from django.core.files.storage import default_storage
import json


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
                    answerDate=today
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
    # User not logged in
    else:
        all_articles = News.objects.filter(isPublic=True).order_by("-lastEditDate")
        total_articles = all_articles.count()
    
    # Check if somebody want to sort by oldest
    if request.POST.get("sort_by") == "oldest":
        all_articles = all_articles.order_by("lastEditDate")

    # Check if somebody searched for something
    if request.method == "POST":
        search_query = request.POST.get("q").strip() or request.GET.get("q").strip()
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
        users = User.objects.filter(partnerId=request.user.partnerId, is_active=True).order_by('firstname', 'lastname')

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
    
    # Get all public tech talks
    all_techtalks = TechTalk.objects.filter(isPublic=True).order_by("-id")
    total_techtalks = all_techtalks.count()
    
    # Check if somebody searched for something
    if request.method == "POST":
        search_query = request.POST.get("q", "").strip()
        # Check if search query is not empty
        if search_query:
            all_techtalks = all_techtalks.filter(Q(title__icontains=search_query) | Q(speaker__icontains=search_query) | Q(description__icontains=search_query))
        # Check if there is HTMX request
        if request.headers.get("HX-Request") == "true":
            return render(request, 'components/techtalks_htmx.jinja', {"all_techtalks": all_techtalks, "total_techtalks": total_techtalks, "search_query": search_query})
    
    return render(request, 'public/techtalks.jinja', {"all_techtalks": all_techtalks, "total_techtalks": total_techtalks, "search_query": search_query})

@login_required(login_url='login')
def settings(request):
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
            firstname = request.POST.get("firstname")
            lastname = request.POST.get("lastname")
            email = request.POST.get("email")
            # Update user info
            request.user.first_name = firstname
            request.user.last_name = lastname
            request.user.email = email
            # Check if there was a profile picture uploaded
            if request.FILES.get("profilepicture"):
                # Image will be automatically saved to the correct location because of the ImageField in the User model (pillow)
                request.user.profilePicture = request.FILES["profilepicture"]
            request.user.save()
            return render(request, 'sharepoint/settings.jinja', {'active_page': active_page, 'success_profile': "Profile updated successfully", 'forms': forms, 'current_application_setting': current_application_setting})
        
        # Check if application settings is changed
        if request.POST.get("applicationsettings"):
            applicationsetting = ApplicationSetting.objects.get(id=1)
            applicationsetting.startDate = None if request.POST.get("startdatestudentregistrationform") == "" else request.POST.get("startdatestudentregistrationform")
            applicationsetting.endDate = None if request.POST.get("enddatestudentregistrationform") == "" else request.POST.get("enddatestudentregistrationform")
            applicationsetting.studentApplicationFormId = None if request.POST.get("studentregistrationform") == "noform" else Form.objects.get(id=request.POST.get("studentregistrationform"))
            applicationsetting.save()
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