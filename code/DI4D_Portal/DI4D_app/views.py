from django.utils import timezone
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib.auth import authenticate, login
from .models import ApplicationSetting, News, User, TechTalk
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.auth import update_session_auth_hash

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
    if application_setting and application_setting.startDate <= today <= application_setting.endDate:
        data["register"] = True
    else:
        data["register"] = False

    # If there is an application setting, give start and end date
    if application_setting:
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

def student_registration(request):
    return render(request, 'test.jinja')

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
        search_query = request.POST.get("q").strip()
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
def dashboard(request):
    active_page = 'dashboard'
    return render(request, 'sharepoint/dashboard.jinja', {'active_page': active_page})

@login_required(login_url='login')
def settings(request):
    active_page = 'settings'
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

                return render(request, 'sharepoint/settings.jinja', {'active_page': active_page, 'success_password': "Password changed successfully"})
            else:
                return render(request, 'sharepoint/settings.jinja', {'active_page': active_page, 'error_password': "Passwords do not match and/or are empty"})
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
            return render(request, 'sharepoint/settings.jinja', {'active_page': active_page, 'success_profile': "Profile updated successfully"})

    return render(request, 'sharepoint/settings.jinja', {'active_page': active_page})
