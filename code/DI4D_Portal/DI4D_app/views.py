from django.utils import timezone
from django.core.mail import send_mail
from django.shortcuts import render
from django.conf import settings

from .models import ApplicationSetting, News, User

# Create your views here.
def hello_world(request):
    return render(request, 'test.jinja')

def home(request):
    data = {}
    today = timezone.now().date() 

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

    return render(request, 'home.jinja',  data)

def student_registration(request):
    return render(request, 'test.jinja')

def news(request):
    return render(request, 'test.jinja')