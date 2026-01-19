from urllib import request
from django.utils import timezone
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib.auth import authenticate, login
from .models import ApplicationSetting, News, User, UserType, Partner
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.crypto import get_random_string

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
