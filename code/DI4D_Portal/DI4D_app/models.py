from django.db import models

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

class User(models.Model):
    userTypeId = models.ForeignKey(UserType, on_delete=models.RESTRICT)
    username = models.CharField(max_length=100)
    password = models.CharField(max_length=100)
    firstname = models.CharField(max_length=100)
    lastname = models.CharField(max_length=100)
    email = models.CharField(max_length=100)
    partnerId = models.ForeignKey(Partner, on_delete=models.RESTRICT)
    profilePicture = models.CharField(null=True, blank=True)
    isActive = models.BooleanField(default=True)

class UserSettings(models.Model):
    settingJson = models.CharField()
    userId = models.ForeignKey(User, on_delete=models.RESTRICT)

class News(models.Model):
    mediaPath = models.CharField()
    isPublic = models.BooleanField(default=False)
    title = models.CharField(max_length=200)
    lastEditDate = models.DateField()
    description = models.CharField()
    author = models.ForeignKey(User, on_delete=models.RESTRICT)
    showAuthor = models.BooleanField(default=False)
    picture = models.CharField()

class Form(models.Model):
    userId = models.ForeignKey(User, on_delete=models.RESTRICT)
    title = models.CharField(max_length=200)
    isActive = models.BooleanField(default=True)
    startDate = models.DateField()
    endDate = models.DateField()

class HistoryStudentApplicationForm(models.Model):
    formId = models.ForeignKey(Form, on_delete=models.RESTRICT)
    year = models.IntegerField()

class ApplicationSetting(models.Model):
    studentApplicationFormId = models.ForeignKey(Form, on_delete=models.RESTRICT)
    startDate = models.DateField()
    endDate = models.DateField()

class DataType(models.Model):
    name = models.CharField(max_length=100)

class Question(models.Model):
    datatype = models.ForeignKey(DataType, on_delete=models.RESTRICT)
    question = models.CharField()
    explanation = models.CharField(null=True, blank=True)
    isActive = models.BooleanField(default=True)
    formId = models.ForeignKey(Form, on_delete=models.RESTRICT)
    isMandatory = models.BooleanField(default=False)

class FormAnswer(models.Model):
    answer = models.CharField()
    questionId = models.ForeignKey(Question, on_delete=models.RESTRICT)
    userId = models.ForeignKey(User, on_delete=models.RESTRICT)
    answerDate = models.DateField()

class TechTalk(models.Model):
    title = models.CharField(max_length=150)
    thubnail = models.CharField()
    videoPath = models.CharField()
    isPublic = models.BooleanField(default=False)
    speaker = models.CharField(max_length=100)
    description = models.CharField()

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
   