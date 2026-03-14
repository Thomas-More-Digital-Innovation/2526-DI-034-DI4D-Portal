import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.contrib.auth.models import BaseUserManager

# Create your models here.
class UserType(models.Model):
    name = models.CharField(max_length=100)

class Country(models.Model):
    name = models.CharField(max_length=100)

class Partner(models.Model):
    name = models.CharField(max_length=100)
    country = models.ForeignKey(Country, on_delete=models.RESTRICT)
    city = models.CharField(max_length=100)
    isActive = models.BooleanField(default=True)

class UserManager(BaseUserManager):
    def create_user(self, username, email, password=None, **extra_fields):
        if not username:
            raise ValueError("Username is verplicht")
        if not email:
            raise ValueError("Email is verplicht")

        email = self.normalize_email(email)
        user = self.model(
            username=username,
            email=email,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(username, email, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    userTypeId = models.ForeignKey(UserType, on_delete=models.RESTRICT, null=True, blank=True)
    username = models.CharField(max_length=100, unique=True)
    firstname = models.CharField(max_length=100)
    lastname = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    partnerId = models.ForeignKey(Partner, on_delete=models.RESTRICT, null=True, blank=True)
    profilePicture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_alumni = models.BooleanField(default=False, null=True, blank=True)

    objects = UserManager()
    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

    def _has_role(self, role_name):
        if not self.userTypeId or not self.userTypeId.name:
            return False
        return self.userTypeId.name.strip().lower() == role_name

    # Security check methods
    def role_is_admin(self):
        return self._has_role("admin")
    
    def role_is_sharepoint_user(self):
        return self._has_role("sharepoint_user")
    
    def role_is_partner(self):
        return self._has_role("partner")
    
    def role_is_student(self):
        return self._has_role("student")

class UserSettings(models.Model):
    settingJson = models.CharField()
    userId = models.ForeignKey(User, on_delete=models.RESTRICT)

class FileItem(models.Model):
    name = models.CharField(max_length=255)
    isDeleted = models.BooleanField(default=False)
    s3Link = models.CharField(null=False, unique=True)
    parentFolder = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children',
    )
    owner = models.ForeignKey(User, on_delete=models.RESTRICT, related_name='owned_file_items')

class FileShare(models.Model):
    fileItemId = models.ForeignKey(FileItem, on_delete=models.CASCADE, related_name='shares')
    userId = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shared_file_items', null=True, blank=True)
    userTypeId = models.ForeignKey(UserType, on_delete=models.CASCADE, related_name='shared_file_items_by_type', null=True, blank=True)
    canEdit = models.BooleanField(default=False)


class WopiAccessToken(models.Model):
    fileItemId = models.ForeignKey(FileItem, on_delete=models.CASCADE, related_name='wopi_tokens')
    userId = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wopi_tokens')
    tokenHash = models.CharField(max_length=64, unique=True)
    canEdit = models.BooleanField(default=False)
    expiresAt = models.DateTimeField()
    isRevoked = models.BooleanField(default=False)
    createdAt = models.DateTimeField(auto_now_add=True)

def media_path_default():
    return uuid.uuid4().hex[:20]

class News(models.Model):
    mediaPath = models.CharField(max_length=30, unique=True, default=media_path_default)
    isPublic = models.BooleanField(default=False)
    title = models.CharField(max_length=200)
    lastEditDate = models.DateField()
    description = models.CharField()
    author = models.ForeignKey(User, on_delete=models.RESTRICT)
    showAuthor = models.BooleanField(default=False)
    picture = models.ImageField(upload_to='news_pictures/')
    content = models.TextField(blank=True, null=True)

class Form(models.Model):
    userId = models.ForeignKey(User, on_delete=models.RESTRICT)
    title = models.CharField(max_length=200)
    isActive = models.BooleanField(default=True)
    startDate = models.DateField()
    endDate = models.DateField(null=True, blank=True)

class HistoryStudentApplicationForm(models.Model):
    formId = models.ForeignKey(Form, on_delete=models.RESTRICT)
    year = models.IntegerField()

class ApplicationSetting(models.Model):
    studentApplicationFormId = models.ForeignKey(Form, on_delete=models.RESTRICT, null=True, blank=True)
    startDate = models.DateField(null=True, blank=True)
    endDate = models.DateField(null=True, blank=True)

class DataType(models.Model):
    name = models.CharField(max_length=100)

class Question(models.Model):
    datatype = models.ForeignKey(DataType, on_delete=models.RESTRICT)
    question = models.CharField()
    explanation = models.CharField(null=True, blank=True)
    content = models.TextField(null=True, blank=True)  # For storing options (comma-separated)
    isActive = models.BooleanField(default=True)
    formId = models.ForeignKey(Form, on_delete=models.RESTRICT)
    isMandatory = models.BooleanField(default=False)

class FormAnswer(models.Model):
    answer = models.CharField()
    questionId = models.ForeignKey(Question, on_delete=models.RESTRICT)
    userId = models.ForeignKey(User, on_delete=models.RESTRICT, null=True, blank=True)
    answerDate = models.DateField()
    submission_number = models.IntegerField(null=True, blank=True)

class TechTalk(models.Model):
    title = models.CharField(max_length=150)
    thubnail = models.ImageField(upload_to='techtalk/thumbnails/')
    videoPath = models.FileField(upload_to='techtalk/videos/')
    isPublic = models.BooleanField(default=False)
    speaker = models.CharField(max_length=100)
    description = models.CharField()
    date = models.DateField()

class UserTechTalk(models.Model):
    techTalkId = models.ForeignKey(TechTalk, on_delete=models.RESTRICT)
    userId = models.ForeignKey(User, on_delete=models.RESTRICT)
    canEdit = models.BooleanField(default=False)

class Event(models.Model):
    date = models.DateField()
    startTime = models.TimeField()
    endTime = models.TimeField()
    title = models.CharField(max_length=200)
    description = models.CharField()
    location = models.CharField(max_length=200)
    pageLink = models.CharField(null=True, blank=True)

class UserEvent(models.Model):
    eventId = models.ForeignKey(Event, on_delete=models.RESTRICT)
    userId = models.ForeignKey(User, on_delete=models.RESTRICT)
    canEdit = models.BooleanField(default=False)

class Webinar(models.Model):
    title = models.CharField(max_length=200)
    description = models.CharField()
    link = models.CharField()

class UserWebinar(models.Model):
    webinarId = models.ForeignKey(Webinar, on_delete=models.RESTRICT)
    userId = models.ForeignKey(User, on_delete=models.RESTRICT)
    canEdit = models.BooleanField(default=False)
    canGive = models.BooleanField(default=False)

class Company(models.Model):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50)

class Project(models.Model):
    name = models.CharField(max_length=200)
    description = models.CharField()
    contact = models.CharField()
    timing = models.CharField()
    technology = models.CharField()
    workspace = models.CharField()
    projectNumber = models.IntegerField()
    companyId = models.ForeignKey(Company, on_delete=models.RESTRICT)
    publishDate = models.DateField()
    scrumMaster = models.CharField(null=True, blank=True)
    status = models.CharField(max_length=50)
    isActive = models.BooleanField(default=True)

class UserProject(models.Model):
    projectId = models.ForeignKey(Project, on_delete=models.RESTRICT)
    studentId = models.ForeignKey(User, on_delete=models.RESTRICT)
    isInterrested = models.BooleanField(default=False)
    isApproved = models.BooleanField(default=False)

class LearningPath(models.Model):
    name = models.CharField(max_length=200)

class LearningGoal(models.Model):
    objective = models.CharField()
    learningPath = models.ForeignKey(LearningPath, on_delete=models.RESTRICT)
    isActive = models.BooleanField(default=True)

class UserLearningGoal(models.Model):
    studentId = models.ForeignKey(User, on_delete=models.RESTRICT, related_name='studentId')
    isDone = models.BooleanField(default=False)
    defence = models.CharField()
    isVerified = models.BooleanField(default=False)
    teacherId = models.ForeignKey(User, on_delete=models.RESTRICT, null=True, blank=True, related_name='teacherId')
    learningGoalId = models.ForeignKey(LearningGoal, on_delete=models.RESTRICT)
    verifiedDate = models.DateField(null=True, blank=True)

class CommunicationUserLearningGoal(models.Model):
    publisherId = models.ForeignKey(User, on_delete=models.RESTRICT)
    comment = models.CharField()
    UserLearningGoalId = models.ForeignKey(UserLearningGoal, on_delete=models.RESTRICT)
    publishDate = models.DateTimeField()

class UserLearningProof(models.Model):
    userLearningGoalId = models.ForeignKey(UserLearningGoal, on_delete=models.RESTRICT)
    mediaPath = models.CharField()

class Program(models.Model):
    name = models.CharField(max_length=200)

class ProgramLearningoal(models.Model):
    programId = models.ForeignKey(Program, on_delete=models.RESTRICT)
    learningGoalId = models.ForeignKey(LearningGoal, on_delete=models.RESTRICT)
    isMandatory = models.BooleanField(default=False)

class Course(models.Model):
    name = models.CharField(max_length=200)
    zCode = models.CharField(max_length=50)
    credits = models.IntegerField()
    semester = models.IntegerField()
    phase = models.IntegerField()
    isActive = models.BooleanField(default=True)

class LearninggoalCourse(models.Model):
    learningGoalId = models.ForeignKey(LearningGoal, on_delete=models.RESTRICT)
    courseId = models.ForeignKey(Course, on_delete=models.RESTRICT)

class StatusStudentRegistration(models.Model):
    status = models.CharField(max_length=50, default='evaluate')
    submission_number = models.IntegerField()
