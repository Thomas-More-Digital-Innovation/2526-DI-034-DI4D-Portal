from django.utils import timezone
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib.auth import authenticate, login
from .models import ApplicationSetting, News, User, TechTalk
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout

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

        # Send email via SMTP
        if len(admin_emails) > 0:
            send_mail(
                subject=f"Contact Form DI4D Portal - Message from {name}",
                message=f"Name : {name}\nEmail: {email}\nMessage:\n{message}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=admin_emails,
                fail_silently=False
            )

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
    data["news"] = News.objects.all().order_by('-lastEditDate')[:2]

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
    return render(request, 'test.jinja')

def tech_talks(request):
    data = {}
    data["techtalks"] = TechTalk.objects.filter(isPublic=True).all()
    return render(request, 'public/techtalks.jinja', data)

@login_required(login_url='login')
def dashboard(request):
    return render(request, 'sharepoint/dashboard.jinja')