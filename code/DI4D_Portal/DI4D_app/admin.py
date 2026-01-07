from django.contrib import admin
from .models import (
    UserType, Country, Partner, User, UserSettings, News, Form,
    HistoryStudentApplicationForm, ApplicationSetting, DataType, Question,
    FormAnswer, TechTalk, UserTechTalk, Event, UserEvent, Webinar, UserWebinar,
    Company, Project, UserProject, LearningPath, LearningGoal, UserLearningGoal,
    CommunicationUserLearningGoal, UserLearningProof, Program, ProgramLearningoal, Course,
    LearninggoalCourse)

# Register your models here.
admin.site.register(UserType)
admin.site.register(Country)
admin.site.register(Partner)
admin.site.register(User)
admin.site.register(UserSettings)
admin.site.register(News)
admin.site.register(Form)
admin.site.register(HistoryStudentApplicationForm)
admin.site.register(ApplicationSetting)
admin.site.register(DataType)
admin.site.register(Question)
admin.site.register(FormAnswer)
admin.site.register(TechTalk)
admin.site.register(UserTechTalk)
admin.site.register(Event)
admin.site.register(UserEvent)
admin.site.register(Webinar)
admin.site.register(UserWebinar)
admin.site.register(Company)
admin.site.register(Project)
admin.site.register(UserProject)
admin.site.register(LearningPath)
admin.site.register(LearningGoal)
admin.site.register(UserLearningGoal)
admin.site.register(CommunicationUserLearningGoal)
admin.site.register(UserLearningProof)
admin.site.register(Program)
admin.site.register(ProgramLearningoal)
admin.site.register(Course)
admin.site.register(LearninggoalCourse)